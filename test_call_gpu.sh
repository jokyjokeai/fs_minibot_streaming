#!/bin/bash
# Wrapper pour lancer test_call.py avec GPU (cuDNN configuré)

# Export cuDNN libs pour faster-whisper GPU
export LD_LIBRARY_PATH="$PWD/venv/lib/python3.10/site-packages/nvidia/cudnn/lib:$PWD/venv/lib/python3.10/site-packages/nvidia/cublas/lib:$LD_LIBRARY_PATH"

echo "🚀 Lancement avec GPU (cuDNN configuré)"
echo "   LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
echo ""

# Lancer test
./venv/bin/python test_call.py
