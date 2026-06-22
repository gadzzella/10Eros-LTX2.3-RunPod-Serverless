# LTX-2.3 · 10Eros i2v — RunPod Serverless Endpoint

Image-to-video generation via LTX-2.3 on RunPod serverless, built on ComfyUI.

---

## Models Baked Into the Image

| File | Size | Destination |
|------|------|-------------|
| `10Eros_v1.2_fp8mixed_learned.safetensors` | 34.3 GB | `models/checkpoints/` |
| `gemma_3_12B_it_fp4_mixed.safetensors` | 9.45 GB | `models/text_encoders/` |
| `ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors` | 2.74 GB | `models/loras/` |
| `gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors` | 0.63 GB | `models/loras/` |
| `ltx2.3-transition.safetensors` | 0.39 GB | `models/loras/` |
| `ltx-2.3-spatial-upscaler-x2-1.1.safetensors` | 1.00 GB | `models/latent_upscale_models/` |
| `LTX23_audio_vae_bf16.safetensors` | 0.37 GB | `models/vae/` |

**Total: ~49 GB**

---

## Custom Nodes

- [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) — core LTX-2.3 nodes + `SaveVideo` / `CreateVideo`
- [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) — utility nodes used in workflow
- [ComfyUI-Manager](https://github.com/Comfy-Org/ComfyUI-Manager) — optional, for debugging

---

## Build & Push

This image is too large (~80 GB uncompressed) for GitHub free runners. Build is done via a **self-hosted runner on a RunPod pod**.

### One-time RunPod pod setup

1. Deploy a RunPod pod: **64 GB RAM, 200 GB disk**, Ubuntu template with Docker pre-installed (`runpod/ubuntu-clean-docker` or equivalent).
2. SSH into the pod.
3. Install Docker if not present:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   newgrp docker
   ```
4. Register the GitHub Actions self-hosted runner:
   ```bash
   sudo apt-get update && sudo apt-get install -y curl tar libicu-dev
   mkdir actions-runner && cd actions-runner
   curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
     https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
   tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz
   ./config.sh --url https://github.com/YOUR_USER/YOUR_REPO --token YOUR_GITHUB_TOKEN
   ./run.sh
   ```
5. Once the runner shows `Listening for Jobs`, trigger the workflow from GitHub Actions.

### GitHub Secrets required

| Secret | Value |
|--------|-------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | Your Docker Hub access token |
| `HF_TOKEN` | HuggingFace token (for gated model downloads) |

---

## RunPod Endpoint Configuration

- **Container image:** `yourdockerhubuser/ltx23-10eros:latest`
- **Container disk:** 120 GB
- **GPU:** A48 (48 GB) or A100 (80 GB) recommended
- **CUDA:** 12.4

---

## API Reference

### Input

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image_base64` | string | yes* | — | Base64-encoded input image |
| `image_url` | string | yes* | — | URL to input image |
| `image_path` | string | yes* | — | Path on network volume |
| `prompt` | string | no | `"gentle motion..."` | Motion description |
| `negative_prompt` | string | no | `""` | Negative descriptors |
| `prompt_enhance` | bool | no | `true` | Use built-in Gemma prompt enhancer |
| `duration` | int | no | `5` | Duration in seconds |
| `fps` | int | no | `25` | Frames per second |
| `width` | int | no | `1280` | Output width |
| `height` | int | no | `720` | Output height |
| `seed` | int | no | `42` | Random seed |
| `use_transition_lora` | bool | no | `false` | Enable transition LoRA |
| `transition_lora_strength` | float | no | `0.7` | Transition LoRA strength (0–1) |

*One of `image_base64`, `image_url`, or `image_path` is required.

### Output

**Success:**
```json
{ "video": "data:video/mp4;base64,..." }
```

**Error:**
```json
{ "error": "description" }
```

### Example request

```json
{
  "input": {
    "image_base64": "<base64 string>",
    "prompt": "She slowly turns her head, hair moving with the motion, soft cinematic light.",
    "duration": 5,
    "fps": 25,
    "width": 1280,
    "height": 720,
    "seed": 42,
    "prompt_enhance": true,
    "use_transition_lora": false
  }
}
```

---

## Frontend

Open `ltx23_studio.html` in any browser. Edit the hardcoded `endpointId` and `apiKey` values at the top of the `<script>` block before use.

Features: image upload, VLM prompt enhancer (OpenRouter), generation parameters, transition LoRA toggle, frame chaining, download, purge queue.

---

## Credits

- [LTX-2.3 by Lightricks](https://github.com/Lightricks/LTX-Video)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo)
- 10Eros checkpoint: [TenStrip/LTX2.3-10Eros](https://huggingface.co/TenStrip/LTX2.3-10Eros)
- Distilled LoRA + Audio VAE: [Kijai/LTX2.3_comfy](https://huggingface.co/Kijai/LTX2.3_comfy)
- Transition LoRA: [joyfox/LTX-2.3-Transition-LORA](https://huggingface.co/joyfox/LTX-2.3-Transition-LORA)
