import runpod
import os
import glob
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import subprocess
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER_ADDRESS = os.getenv("SERVER_ADDRESS", "127.0.0.1")
CLIENT_ID = str(uuid.uuid4())
WORKFLOW_PATH = "/video_ltx2_3_i2v_API.json"
OUTPUT_DIR = "/ComfyUI/output"


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


def find_video_from_history(history):
    """Try to extract a video file path from ComfyUI history output."""
    for node_id, node_output in history.get("outputs", {}).items():
        logger.info(f"[DEBUG] node {node_id} output keys: {list(node_output.keys())}")
        for key in ("videos", "video", "gifs", "output", "saved_files", "files"):
            if key not in node_output:
                continue
            items = node_output[key]
            if not isinstance(items, list):
                items = [items]
            for item in items:
                if not isinstance(item, dict):
                    logger.info(f"[DEBUG] node {node_id} key={key} item is not dict: {item}")
                    continue
                logger.info(f"[DEBUG] node {node_id} key={key} item={item}")
                # Try fullpath first
                fullpath = item.get("fullpath")
                if fullpath and os.path.exists(fullpath):
                    logger.info(f"[DEBUG] found via fullpath: {fullpath}")
                    return fullpath
                # Try subfolder + filename
                filename = item.get("filename", "")
                subfolder = item.get("subfolder", "")
                if filename:
                    candidate = os.path.join(OUTPUT_DIR, subfolder, filename)
                    logger.info(f"[DEBUG] trying candidate: {candidate}")
                    if os.path.exists(candidate):
                        logger.info(f"[DEBUG] found via candidate: {candidate}")
                        return candidate
    return None


def find_video_by_glob(job_start_time):
    """Glob fallback: find the newest video created after job started."""
    patterns = [
        f"{OUTPUT_DIR}/**/*.mp4",
        f"{OUTPUT_DIR}/**/*.webm",
        f"{OUTPUT_DIR}/**/*.mkv",
    ]
    candidates = []
    for pat in patterns:
        candidates.extend(glob.glob(pat, recursive=True))

    logger.info(f"[DEBUG] glob found {len(candidates)} video files total")

    # Filter to files created at or after job start
    fresh = [f for f in candidates if os.path.getmtime(f) >= job_start_time]
    logger.info(f"[DEBUG] glob found {len(fresh)} files newer than job start: {fresh}")

    if fresh:
        newest = max(fresh, key=os.path.getmtime)
        logger.info(f"[DEBUG] returning newest: {newest}")
        return newest

    # Last resort: return absolute newest file regardless of time
    if candidates:
        newest = max(candidates, key=os.path.getmtime)
        logger.info(f"[DEBUG] time-filter found nothing; returning absolute newest: {newest}")
        return newest

    return None


def get_videos(ws, prompt):
    job_start_time = time.time()
    prompt_id = queue_prompt(prompt)["prompt_id"]
    logger.info(f"[DEBUG] queued prompt_id={prompt_id}")

    while True:
        out = ws.recv()
        if isinstance(out, str):
            msg = json.loads(out)
            if msg["type"] == "executing":
                data = msg["data"]
                if data["node"] is None and data["prompt_id"] == prompt_id:
                    logger.info("[DEBUG] ComfyUI execution finished signal received")
                    break

    history_raw = get_history(prompt_id)
    logger.info(f"[DEBUG] history keys: {list(history_raw.keys())}")

    job_history = history_raw.get(prompt_id, {})
    logger.info(f"[DEBUG] job_history top-level keys: {list(job_history.keys())}")

    # Check for ComfyUI-reported errors
    status = job_history.get("status", {})
    if status.get("status_str") == "error" or not status.get("completed", True):
        messages = status.get("messages", [])
        logger.error(f"[ERROR] ComfyUI reported error status. Messages: {messages}")
        raise Exception(f"ComfyUI workflow error: {messages}")

    # Strategy 1: parse history outputs
    video_path = find_video_from_history(job_history)
    if video_path:
        return video_path

    logger.info("[DEBUG] history strategy found nothing, falling back to glob")

    # Strategy 2: glob for new files
    video_path = find_video_by_glob(job_start_time)
    if video_path:
        return video_path

    logger.error("[ERROR] No video found via history or glob")
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

    prompt["269"]["inputs"]["image"] = image_path
    if "prompt" in job_input:
        prompt["320:319"]["inputs"]["value"] = job_input["prompt"]
    prompt["320:328"]["inputs"]["value"] = bool(job_input.get("prompt_enhance", True))
    prompt["320:312"]["inputs"]["value"] = int(job_input.get("width", 1280))
    prompt["320:299"]["inputs"]["value"] = int(job_input.get("height", 720))
    prompt["320:301"]["inputs"]["value"] = int(job_input.get("duration", 5))
    prompt["320:300"]["inputs"]["value"] = int(job_input.get("fps", 25))
    seed = int(job_input.get("seed", 42))
    prompt["320:276"]["inputs"]["noise_seed"] = seed
    prompt["320:277"]["inputs"]["noise_seed"] = seed + 1

    use_transition = bool(job_input.get("use_transition_lora", False))
    transition_strength = float(job_input.get("transition_lora_strength", 0.7))
    if use_transition:
        prompt["320:999"] = {
            "inputs": {
                "lora_name": "ltx2.3-transition.safetensors",
                "strength_model": transition_strength,
                "model": ["320:285", 0]
            },
            "class_type": "LoraLoaderModelOnly",
            "_meta": {"title": "Load Transition LoRA"}
        }
        prompt["320:282"]["inputs"]["model"] = ["320:999", 0]
        prompt["320:314"]["inputs"]["model"] = ["320:999", 0]

    # ── Connect WebSocket ─────────────────────────────────────────────────────
    wait_for_comfyui()

    ws_url = f"ws://{SERVER_ADDRESS}:8188/ws?clientId={CLIENT_ID}"
    ws = websocket.WebSocket()
    for attempt in range(36):
        try:
            ws.connect(ws_url)
            logger.info(f"WebSocket connected (attempt {attempt+1})")
            break
        except Exception as e:
            if attempt == 35:
                raise Exception(f"WebSocket timeout: {e}")
            time.sleep(5)

    try:
        video_path = get_videos(ws, prompt)
    finally:
        ws.close()

    if video_path and os.path.exists(video_path):
        with open(video_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode("utf-8")
        return {"video": f"data:video/mp4;base64,{video_b64}"}

    return {"error": "No video output from ComfyUI."}


runpod.serverless.start({"handler": handler})
