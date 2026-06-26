import os
import shutil
from huggingface_hub import hf_hub_download, login

token = os.environ.get("HF_TOKEN")
if token:
    login(token=token, add_to_git_credential=False)
    print("Authenticated with HuggingFace.")
else:
    print("No HF_TOKEN — downloading public models only.")

MODELS = [
    # (repo_id, filename_in_repo, destination_path)

    # Main checkpoint — fp8 safetensors, CheckpointLoaderSimple compatible
    (
        "TenStrip/LTX2.3-10Eros",
        "10Eros_v1.2_fp8mixed_learned.safetensors",
        "/ComfyUI/models/checkpoints/10Eros_v1.2_fp8mixed_learned.safetensors",
    ),

    # Text encoder (Gemma 3 12B fp4)
    (
        "Comfy-Org/ltx-2",
        "split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors",
        "/ComfyUI/models/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors",
    ),

    # Distilled LoRA
    (
        "TenStrip/LTX2.3_Distilled_Lora_1.1_Experiments",
        "ltx-2.3-22b-distilled-lora-1.1_fro90_ceil72_condsafe.safetensors",
        "/ComfyUI/models/loras/ltx-2.3-22b-distilled-lora-1.1_fro90_ceil72_condsafe.safetensors",
    ),

    # Spatial upscaler
    (
        "Lightricks/LTX-2.3",
        "ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
        "/ComfyUI/models/latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
    ),
]

for repo_id, filename, dest in MODELS:
    print(f"Downloading {filename} ...")
    try:
        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            token=token,
            local_dir="/tmp/hf_downloads",
            local_dir_use_symlinks=False,
        )
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(path, dest)
        print(f"  -> {dest} [OK]")
    except Exception as e:
        print(f"  -> FAILED: {e}")
        raise

print("All models downloaded.")
