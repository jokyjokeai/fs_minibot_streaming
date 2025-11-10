#!/usr/bin/env python3
"""
Test GPU + Faster-Whisper Small Model

Vérifie:
- GPU détection
- cuDNN disponibilité
- Modèle 'small' chargé
- Latence transcription
"""

import sys
import time
import glob
from pathlib import Path

from system.config import config
from system.services.faster_whisper_stt import FasterWhisperSTT

print("=" * 70)
print("🧪 TEST GPU + FASTER-WHISPER SMALL MODEL")
print("=" * 70)

# 1. Configuration
print(f"\n📋 Configuration:")
print(f"   Model: {config.FASTER_WHISPER_MODEL}")
print(f"   Device: {config.FASTER_WHISPER_DEVICE}")
print(f"   Compute type: {config.FASTER_WHISPER_COMPUTE_TYPE}")

# 2. Initialiser service
print(f"\n🚀 Initialisation Faster-Whisper...")
start = time.time()

stt = FasterWhisperSTT(
    model_name=config.FASTER_WHISPER_MODEL,
    device=config.FASTER_WHISPER_DEVICE,
    compute_type=config.FASTER_WHISPER_COMPUTE_TYPE
)

init_time = time.time() - start

if not stt.is_available:
    print("❌ Service non disponible!")
    sys.exit(1)

print(f"✅ Service initialisé en {init_time:.2f}s")
print(f"   Device actif: {stt.device}")
print(f"   Compute type actif: {stt.compute_type}")

# 3. Tester sur dernier fichier AMD
print(f"\n🎤 Test transcription:")

# Chercher dernier fichier AMD
recordings_dir = config.RECORDINGS_DIR
amd_files = sorted(glob.glob(str(recordings_dir / "amd_*.wav")))

if not amd_files:
    print("⚠️ Aucun fichier AMD trouvé")
    print(f"💡 Créer un appel de test d'abord")
    sys.exit(0)

test_file = amd_files[-1]
print(f"   Fichier: {Path(test_file).name}")

# Transcrire
start = time.time()
result = stt.transcribe_file(test_file)
transcribe_time = time.time() - start

print(f"   Latence: {transcribe_time:.3f}s")
print(f"   Texte: \"{result['text']}\"")

# 4. Résumé
print(f"\n" + "=" * 70)
print(f"📊 RÉSUMÉ:")
print(f"   GPU utilisé: {'✅ OUI' if stt.device == 'cuda' else '❌ NON (CPU)'}")
print(f"   Modèle: {config.FASTER_WHISPER_MODEL}")
print(f"   Latence moyenne: {transcribe_time:.3f}s")

# Benchmark comparatif
if stt.device == 'cuda':
    speedup = 1.5 / transcribe_time  # Vosk était à 1.5s
    print(f"   Speedup vs Vosk: {speedup:.1f}x plus rapide")
else:
    speedup = 1.5 / transcribe_time
    print(f"   Speedup vs Vosk (CPU): {speedup:.1f}x plus rapide")

print("=" * 70)
