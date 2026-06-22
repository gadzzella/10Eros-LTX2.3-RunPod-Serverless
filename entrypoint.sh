#!/bin/bash
set -e

echo "Starting ComfyUI..."
python /ComfyUI/main.py --listen --use-sage-attention &

echo "Waiting for ComfyUI to be ready..."
max_wait=180
count=0
while [ $count -lt $max_wait ]; do
    if curl -s http://127.0.0.1:8188/ > /dev/null 2>&1; then
        echo "ComfyUI ready!"
        break
    fi
    sleep 2
    count=$((count + 2))
done

if [ $count -ge $max_wait ]; then
    echo "ERROR: ComfyUI failed to start within ${max_wait}s"
    exit 1
fi

echo "Starting handler..."
exec python /handler.py
