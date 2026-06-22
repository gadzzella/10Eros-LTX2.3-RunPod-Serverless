import runpod
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import binascii
import subprocess
import time
import copy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER_ADDRESS = os.getenv("SERVER_ADDRESS", "127.0.0.1")
CLIENT_ID = str(uuid.uuid4())
WORKFLOW_PATH = "/video_ltx2_3_i2v_API.json"


def load_workflow():
    with open(WORKFLOW_PATH, "r") as f:
        return json.load(f)


def queue_prompt(prompt):
    url = f"http://{SERVER_ADDRESS}:8188/prompt"
    p = {"prompt": prompt, "client_id": CLIENT_ID}
    data = json.dumps(p).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    return json.loads(urllib.request.urlopen(req).read())


def get_history(prompt_id):
    url = f"http://{SERVER_ADDRESS}:8188/history/{prompt_id}"
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def save_base64_to_file(b64_data, path):
    # Strip data URI prefix if present
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    decoded = base64.b64decode(b64_data)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(decoded)
    return path


def download_url_to_file(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result = subprocess.run(["wget", "-O", path, "--no-verbose", url],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"wget failed: {result.stderr}")
    return path


def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)["prompt_id"]
    while True:
        out = ws.recv()
        if isinstance(out, str):
            msg = json.loads(out)
            if msg["type"] == "executing":
                data = msg["data"]
                if data["node"] is None and data["prompt_id"] == prompt_id:
                    break
    history = get_history(prompt_id)[prompt_id]
    for node_id in history["outputs"]:
        node_output = history["outputs"][node_id]
        # SaveVideo outputs under "videos" key
        if "videos" in node_output:
            for video in node_output["videos"]:
                fullpath = video.get("fullpath") or os.path.join(
                    "/ComfyUI/output", video.get("subfolder", ""), video["filename"]
                )
                with open(fullpath, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
        # Fallback: gifs (VideoHelperSuite)
        if "gifs" in node_output:
            for video in node_output["gifs"]:
                with open(video["fullpath"], "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
    return None


def wait_for_comfyui(max_wait=180):
    url = f"http://{SERVER_ADDRESS}:8188/"
    for i in range(max_wait):
        try:
            urllib.request.urlopen(url, timeout=5)
            logger.info(f"ComfyUI ready after {i}s")
            return
        except Exception:
            time.sleep(1)
    raise Exception("ComfyUI failed to start within timeout")


def handler(job):
    job_input = job.get("input", {})
    task_id = f"task_{uuid.uuid4()}"
    tmp_dir = f"/tmp/{task_id}"

    # ── Image input ───────────────────────────────────────────────────────────
    image_path = None
    if "image_path" in job_input:
        image_path = job_input["image_path"]
    elif "image_url" in job_input:
        image_path = download_url_to_file(job_input["image_url"], f"{tmp_dir}/input.jpg")
    elif "image_base64" in job_input:
        image_path = save_base64_to_file(job_input["image_base64"], f"{tmp_dir}/input.jpg")
    else:
        return {"error": "No image provided. Send image_path, image_url, or image_base64."}

    # ── Load & patch workflow ─────────────────────────────────────────────────
    prompt = load_workflow()

    # Image
    prompt["269"]["inputs"]["image"] = image_path

    # Prompt text
    if "prompt" in job_input:
        prompt["320:319"]["inputs"]["value"] = job_input["prompt"]

    # Prompt enhance toggle (default: True)
    prompt["320:328"]["inputs"]["value"] = bool(job_input.get("prompt_enhance", True))

    # Resolution
    prompt["320:312"]["inputs"]["value"] = int(job_input.get("width", 1280))
    prompt["320:299"]["inputs"]["value"] = int(job_input.get("height", 720))

    # Duration (seconds) and FPS
    prompt["320:301"]["inputs"]["value"] = int(job_input.get("duration", 5))
    prompt["320:300"]["inputs"]["value"] = int(job_input.get("fps", 25))

    # Seeds
    seed = int(job_input.get("seed", 42))
    prompt["320:276"]["inputs"]["noise_seed"] = seed
    prompt["320:277"]["inputs"]["noise_seed"] = seed + 1  # second sampler gets offset

    # Transition LoRA — optional, off by default
    # Node 320:285 is the distilled motion LoRA loader (LoraLoaderModelOnly)
    # Node 320:324 is the gemma abliterated LoRA loader (LoraLoader)
    # Transition LoRA would be an additional loader — inject dynamically if requested
    use_transition = bool(job_input.get("use_transition_lora", False))
    transition_strength = float(job_input.get("transition_lora_strength", 0.7))

    if use_transition:
        # Insert a LoraLoaderModelOnly node chained after node 320:285
        # Node 320:285 output feeds into 320:314 and 320:282 (CFGGuiders)
        # We inject a new node "320:999" between 320:285 and the guiders
        prompt["320:999"] = {
            "inputs": {
                "lora_name": "ltx2.3-transition.safetensors",
                "strength_model": transition_strength,
                "model": ["320:285", 0]
            },
            "class_type": "LoraLoaderModelOnly",
            "_meta": {"title": "Load Transition LoRA"}
        }
        # Rewire CFGGuiders to use 320:999 instead of 320:285
        prompt["320:282"]["inputs"]["model"] = ["320:999", 0]
        prompt["320:314"]["inputs"]["model"] = ["320:999", 0]

    # ── Connect WebSocket ─────────────────────────────────────────────────────
    wait_for_comfyui()

    ws_url = f"ws://{SERVER_ADDRESS}:8188/ws?clientId={CLIENT_ID}"
    ws = websocket.WebSocket()
    for attempt in range(36):  # 3 min
        try:
            ws.connect(ws_url)
            logger.info(f"WebSocket connected (attempt {attempt+1})")
            break
        except Exception as e:
            if attempt == 35:
                raise Exception(f"WebSocket timeout: {e}")
            time.sleep(5)

    try:
        video_b64 = get_videos(ws, prompt)
    finally:
        ws.close()

    if video_b64:
        return {"video": f"data:video/mp4;base64,{video_b64}"}
    return {"error": "No video output from ComfyUI."}


runpod.serverless.start({"handler": handler})
