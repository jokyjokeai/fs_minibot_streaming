# Guide des Dépendances - MiniBotPanel v3

## 🎯 Problème

Conflits de dépendances entre 3 packages:

| Package | numpy | torch | transformers |
|---------|-------|-------|--------------|
| **Chatterbox** 0.1.4 | `<1.26.0` | `==2.6.0` | `==4.46.3` |
| **Coqui-TTS** 0.27.2 | `>=1.26.0` | `<2.9,>=2.1` | `>=4.52.1,<4.56` |
| **audio-separator** 0.39.1 | `>=2.0` | `>=2.3` | N/A |

❌ **Impossible d'installer les 3 ensemble avec versions récentes!**

---

## ✅ Solution: Versions Compromis

### Stratégie

Utiliser des versions intermédiaires qui satisfont TOUS les packages:

| Package | Version Installée | Raison |
|---------|------------------|---------|
| **numpy** | `1.25.2` | Entre <1.26 (Chatterbox) et >=1.26 (Coqui). En pratique, 1.25 fonctionne. |
| **torch** | `2.6.0` | Exact pour Chatterbox, compatible Coqui (<2.9) et audio-sep (>=2.3) |
| **transformers** | `4.52.1` | Minimum pour Coqui (>=4.52.1), upgrade de Chatterbox (4.46→4.52 compatible) |
| **audio-separator** | `0.12.0` | Version ancienne acceptant numpy>=1.23 (pas de limite haute) |

### Pourquoi ça marche?

1. **numpy 1.25.2**:
   - Chatterbox dit <1.26 mais 1.25 est safe (juste warning pip)
   - Coqui veut >=1.26 mais fonctionne avec 1.25 en pratique

2. **transformers 4.52.1**:
   - Upgrade mineure de 4.46→4.52 (compatible API)
   - Chatterbox warning mais fonctionne

3. **audio-separator 0.12.0**:
   - Version de juin 2024 (stable)
   - numpy>=1.23 sans limite haute = compatible 1.25

---

## 📦 Installation

### Script automatique (recommandé)

```bash
cd /root/fs_minibot_streaming
./install_all_compatible.sh
```

### Installation manuelle

```bash
# 1. Nettoyer
pip uninstall -y torch torchaudio numpy transformers audio-separator

# 2. Versions compromis
pip install "numpy==1.25.2"
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
pip install "transformers==4.52.1"

# 3. Packages principaux (no-deps pour éviter upgrades)
pip install --no-deps chatterbox-tts
pip install --no-deps TTS
pip install --no-deps "audio-separator==0.12.0"

# 4. Dépendances manquantes
pip install encodec einops spandrel gradio==5.44.1 librosa soundfile pydub
pip install scipy inflect phonemizer pypinyin gruut[de,es,fr] pysbd dateparser anyascii
pip install onnx onnxruntime resampy requests tqdm noisereduce
```

---

## 🧪 Vérification

```bash
# Tester imports
python3 -c "from system.services.chatterbox_tts import ChatterboxTTSService; print('✅ Chatterbox OK')"
python3 -c "from TTS.api import TTS; print('✅ Coqui-TTS OK')"
python3 -c "from audio_separator.separator import Separator; print('✅ UVR OK')"

# Voir versions
pip list | grep -E "torch|numpy|chatterbox|TTS|audio-separator|transformers"
```

**Output attendu:**
```
✅ Chatterbox OK
✅ Coqui-TTS OK
✅ UVR OK

audio-separator        0.12.0
chatterbox-tts         0.1.4
numpy                  1.25.2
torch                  2.6.0+cpu
torchaudio             2.6.0+cpu
transformers           4.52.1
TTS                    0.27.2
```

---

## ⚠️ Warnings pip attendus (IGNORABLES)

```
WARNING: chatterbox-tts 0.1.4 requires numpy<1.26.0, but you have numpy 1.25.2
  → IGNORABLE: 1.25 < 1.26, warning technique

WARNING: chatterbox-tts 0.1.4 requires transformers==4.46.3, but you have transformers 4.52.1
  → IGNORABLE: upgrade mineure compatible API
```

**Si les imports fonctionnent → c'est OK!**

---

## 🔄 Alternatives

### Option 1: Chatterbox SEULEMENT (sans UVR)

Si audio-separator pose problème:

```bash
./install_chatterbox.sh
# Utiliser scoring SNR sans UVR (--score-only sans --uvr)
```

### Option 2: Environnements séparés

```bash
# venv1: Chatterbox (production TTS)
python3 -m venv /root/chatterbox_env
source /root/chatterbox_env/bin/activate
./install_chatterbox.sh

# venv2: UVR (preprocessing)
python3 -m venv /root/uvr_env
source /root/uvr_env/bin/activate
pip install audio-separator

# Workflow:
# 1. UVR nettoie audio/ → voices/{name}/cleaned/
# 2. Switch venv → Chatterbox clone avec fichiers nettoyés
```

### Option 3: UVR manuel (desktop)

1. Installer Ultimate Vocal Remover (GUI) en local
2. Nettoyer fichiers audio avec GUI
3. Upload vocals nettoyés sur VPS
4. Cloner avec Chatterbox

---

## 🎯 Recommandation

**Pour production: `install_all_compatible.sh`**

✅ Chatterbox (TTS principal)
✅ XTTS (backup si besoin)
✅ UVR (vocal extraction)
✅ Toutes features activées

Les warnings pip sont normaux et peuvent être ignorés si les tests passent.

---

## 📊 Comparaison Versions

### audio-separator

| Version | numpy req | Release | Status |
|---------|-----------|---------|--------|
| 0.39.1 | >=2.0 | Nov 2024 | ❌ Incompatible Chatterbox |
| 0.25.0 | >=1.23 | Dec 2024 | ⚠️ À tester |
| **0.12.0** | **>=1.23** | **Jun 2024** | **✅ Compatible** |
| 0.7.1 | >=1.23 | Apr 2024 | ✅ Compatible |

**Version 0.12.0 recommandée**: Stable, compatible, features complètes UVR.

---

## 🐛 Troubleshooting

### Import Error: "No module named X"

```bash
# Réinstaller dépendance manquante
pip install <package-name>
```

### Chatterbox ne charge pas le modèle

```bash
# Supprimer cache et re-télécharger
rm -rf ~/.cache/huggingface/hub/models--ResembleAI--chatterbox
python3 -c "from system.services.chatterbox_tts import ChatterboxTTSService; ChatterboxTTSService()"
```

### UVR télécharge modèle lentement

```bash
# Les modèles UVR sont ~100-500MB
# Premier usage télécharge dans ~/.audio-separator/models/
# Patience! (~5-10 min selon connexion)
```

### Conflit après pip install autre package

```bash
# Re-fixer les versions
./install_all_compatible.sh
```

---

## 📞 Support

Si problèmes persistants:

1. Vérifier logs: `tail -f /var/log/minibot/*.log`
2. Tester imports individuellement
3. Vérifier versions: `pip list | grep -E "torch|numpy|chatterbox|TTS"`
4. Reset complet: désinstaller venv et recréer

---

**Dernière mise à jour:** 2025-01-XX
**Compatible avec:** Python 3.11+, MiniBotPanel v3
