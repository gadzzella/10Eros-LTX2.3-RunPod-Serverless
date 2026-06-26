FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV HF_HUB_ENABLE_HF_TRANSFER=1

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev \
    git wget curl ffmpeg libgl1 libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/bin/python

RUN pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

RUN pip install --no-cache-dir \
    runpod websocket-client \
    huggingface_hub hf_transfer \
    numpy pillow

RUN pip install --no-cache-dir sageattention --no-build-isolation

# ── ComfyUI ──────────────────────────────────────────────────────────────────
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /ComfyUI && \
    cd /ComfyUI && pip install --no-cache-dir -r requirements.txt

# ── Custom Nodes ──────────────────────────────────────────────────────────────
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git && \
    cd ComfyUI-LTXVideo && pip install --no-cache-dir -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-KJNodes.git && \
    cd ComfyUI-KJNodes && pip install --no-cache-dir -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && pip install --no-cache-dir -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/TenStrip/10S-Comfy-nodes.git && \
    cd 10S-Comfy-nodes && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git && \
    cd ComfyUI-VideoHelperSuite && pip install --no-cache-dir -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/rgthree/rgthree-comfy.git && \
    cd rgthree-comfy && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/yolain/ComfyUI-Easy-Use.git && \
    cd ComfyUI-Easy-Use && pip install --no-cache-dir -r requirements.txt

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/jamesWalker55/comfyui-various.git && \
    cd comfyui-various && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/MaxOfLondon/comfyui-mxtoolkit.git && \
    cd comfyui-mxtoolkit && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/ExponentialML/ComfyUI-ComfyMath.git && \
    cd ComfyUI-ComfyMath && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# ── Model directories ─────────────────────────────────────────────────────────
RUN mkdir -p \
    /ComfyUI/models/checkpoints \
    /ComfyUI/models/text_encoders \
    /ComfyUI/models/loras \
    /ComfyUI/models/latent_upscale_models

# ── Download models ───────────────────────────────────────────────────────────
ARG HF_TOKEN
COPY download_models.py /download_models.py
RUN HF_TOKEN=${HF_TOKEN} python /download_models.py

# ── Copy repo files ───────────────────────────────────────────────────────────
COPY handler.py /handler.py
COPY 10Eros_10SNodes_I2V_v3_TiledSampler_API.json /10Eros_10SNodes_I2V_v3_TiledSampler_API.json
COPY extra_model_paths.yaml /ComfyUI/extra_model_paths.yaml
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
