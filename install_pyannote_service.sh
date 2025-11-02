#!/bin/bash
#
# Installation du service Pyannote isolé
#
# Ce script crée un environnement virtuel séparé pour pyannote.audio
# avec ses dépendances (numpy 2.x, torch 2.9) qui sont incompatibles
# avec le venv principal du projet.
#
# Usage:
#   bash install_pyannote_service.sh
#

set -e  # Exit on error

echo "============================================================"
echo "🎤 Installation Pyannote Service (isolé)"
echo "============================================================"

# Détecter le répertoire du projet
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="/root/pyannote_service"

echo "📁 Project root: $PROJECT_ROOT"
echo "📁 Service will be installed in: $SERVICE_DIR"
echo ""

# Créer dossier du service
echo "📂 Creating service directory..."
mkdir -p "$SERVICE_DIR"
cd "$SERVICE_DIR"

# Créer venv Python 3.11
echo "🐍 Creating isolated Python 3.11 venv..."
python3.11 -m venv venv_pyannote

# Activer venv
source venv_pyannote/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Installer PyTorch (GPU ou CPU selon disponibilité)
echo "🔥 Installing PyTorch..."
if command -v nvidia-smi &> /dev/null; then
    echo "   GPU detected - installing CUDA version"
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
else
    echo "   No GPU detected - installing CPU version"
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

# Installer pyannote.audio
echo "🎤 Installing pyannote.audio..."
pip install pyannote.audio

# Installer FastAPI + dependencies
echo "🚀 Installing FastAPI service dependencies..."
pip install fastapi uvicorn[standard] python-multipart aiofiles

# Créer le serveur FastAPI
echo "📝 Creating FastAPI server..."
cat > "$SERVICE_DIR/server.py" << 'PYTHON_EOF'
"""
Pyannote Diarization Service
API REST pour diarization de locuteurs

Endpoints:
- POST /diarize: Diarize audio file
- GET /health: Service health check
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pyannote.audio import Pipeline
import tempfile
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pyannote Diarization Service")

# Global pipeline (loaded once at startup)
pipeline = None


@app.on_event("startup")
async def load_pipeline():
    """Load pyannote pipeline at startup"""
    global pipeline

    logger.info("🎤 Loading pyannote speaker-diarization pipeline...")

    # Check for HuggingFace token
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        logger.warning("⚠️  HF_TOKEN not found in environment")
        logger.warning("   Set it with: export HF_TOKEN='your_token'")
        logger.warning("   Using public model (may have limitations)")

    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        logger.info("✅ Pipeline loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load pipeline: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if pipeline else "loading",
        "service": "pyannote-diarization",
        "version": "3.1"
    }


@app.post("/diarize")
async def diarize_audio(file: UploadFile = File(...)):
    """
    Diarize speaker in audio file

    Args:
        file: Audio file (WAV format recommended)

    Returns:
        JSON with speaker segments
    """
    if not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not loaded")

    # Validate file type
    if not file.filename.endswith(('.wav', '.mp3', '.m4a', '.flac')):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Use WAV, MP3, M4A, or FLAC"
        )

    logger.info(f"📥 Processing file: {file.filename}")

    try:
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        logger.info(f"🎵 Running diarization...")

        # Run diarization
        diarization = pipeline(temp_path)

        # Format results
        segments = []
        speaker_stats = {}

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segment = {
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": speaker,
                "duration": float(turn.end - turn.start)
            }
            segments.append(segment)

            # Track speaker stats
            if speaker not in speaker_stats:
                speaker_stats[speaker] = 0.0
            speaker_stats[speaker] += segment["duration"]

        # Clean up temp file
        os.unlink(temp_path)

        logger.info(f"✅ Diarization complete: {len(segments)} segments, {len(speaker_stats)} speakers")

        return {
            "segments": segments,
            "speakers": speaker_stats,
            "total_segments": len(segments),
            "num_speakers": len(speaker_stats)
        }

    except Exception as e:
        logger.error(f"❌ Diarization failed: {e}")
        # Clean up temp file if exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
PYTHON_EOF

# Créer script de démarrage
echo "📝 Creating startup script..."
cat > "$SERVICE_DIR/start_service.sh" << 'BASH_EOF'
#!/bin/bash
# Start pyannote service

cd "$(dirname "$0")"
source venv_pyannote/bin/activate

# Check for HF token
if [ -z "$HF_TOKEN" ]; then
    echo "⚠️  Warning: HF_TOKEN not set"
    echo "   Using public model (may have rate limits)"
fi

echo "🚀 Starting Pyannote Diarization Service on http://127.0.0.1:8001"
python -m uvicorn server:app --host 127.0.0.1 --port 8001
BASH_EOF

chmod +x "$SERVICE_DIR/start_service.sh"

# Tester l'installation
echo ""
echo "🧪 Testing installation..."
python -c "import pyannote.audio; print('✅ pyannote.audio imported successfully')"
python -c "import fastapi; print('✅ fastapi imported successfully')"

echo ""
echo "============================================================"
echo "✅ Pyannote Service Installation Complete!"
echo "============================================================"
echo ""
echo "📁 Service installed in: $SERVICE_DIR"
echo ""
echo "🔑 IMPORTANT: Set your HuggingFace token:"
echo "   export HF_TOKEN='hf_your_token_here'"
echo "   Add to ~/.bashrc for persistence"
echo ""
echo "🚀 Manual start (optional, for testing):"
echo "   cd $SERVICE_DIR"
echo "   bash start_service.sh"
echo ""
echo "📝 The service will be auto-started by youtube_extract.py"
echo "   when needed (transparent integration)"
echo ""
echo "============================================================"
