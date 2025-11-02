# 🎙️ Chatterbox TTS - Guide Complet des Meilleures Pratiques

## 📊 Résumé Recherche (Sources Officielles)

**Sources consultées:**
- GitHub officiel resemble-ai/chatterbox
- Issue #39: Audio clip guidelines
- Issue #97: Gibberish and hallucinations
- knowledge.resemble.ai (documentation officielle)
- Tests communautaires

---

## 🎵 Format Audio OPTIMAL

### Format Fichier
```
✅ RECOMMANDÉ: WAV (RIFF PCM)
   - 16-bit minimum
   - 24-bit idéal pour capture détails

❌ ÉVITER: MP3, AAC, OGG (compression destructive)
```

### Sample Rate (Taux d'échantillonnage)
```
✅ OPTIMAL: 44.1 kHz ou 48 kHz
✅ ACCEPTABLE: 24 kHz (minimum Chatterbox)
⚠️  PASSABLE: 22 kHz, 16 kHz
❌ ÉVITER: <16 kHz (qualité insuffisante)
```

**Notre configuration actuelle:**
```python
TARGET_SAMPLE_RATE = 22050  # Hz
TARGET_CHANNELS = 1         # Mono
TARGET_FORMAT = "wav"
```

**Recommandation:** Passer à 44100 Hz pour qualité optimale.

---

## ⏱️ Durée Audio

### Pour Voice Cloning (Zero-Shot)

#### Durée Minimale
```
✅ MINIMUM ABSOLU: 10 secondes
✅ RECOMMANDÉ: 20-30 secondes
✅ OPTIMAL: 1-3 minutes
⚠️  ACCEPTABLE: 5-10 secondes (qualité réduite)
```

#### Durée Maximale
```
✅ Tests utilisateurs: Jusqu'à 5 minutes fonctionne
⚠️  Note: Qualité ne s'améliore PAS significativement après 1-3 min
💡 Conseil: Mieux vaut QUALITÉ que QUANTITÉ
```

### Pour Production Voice (Resemble AI Pro)
```
✅ MINIMUM: 20 minutes total
✅ OPTIMAL: 30-60 minutes
```

### Découpage Segments

**Pour few-shot (plusieurs fichiers):**
```
✅ OPTIMAL: 1.5 à 15 secondes par segment
✅ RECOMMANDÉ: 4-10 secondes (notre config actuelle)
❌ ÉVITER: <1 seconde (génère gibberish)
```

**Notre configuration actuelle:**
```python
MIN_CHUNK_DURATION_MS = 4000   # 4s ✅
MAX_CHUNK_DURATION_MS = 10000  # 10s ✅
```

---

## 🔢 Nombre de Fichiers

### Zero-Shot (1 fichier)
```
✅ SUFFIT: 1 seul fichier de 10-30 secondes
💡 Format: audio/reference.wav
```

### Few-Shot (plusieurs fichiers)
```
✅ OPTIMAL: Sélection DYNAMIQUE pour 60-150 secondes total
✅ SYSTÈME: Prend meilleurs fichiers jusqu'à atteindre durée cible
⚠️  LIMITE: Maximum 30 fichiers (sécurité)

💡 NOTRE SYSTÈME:
   - Sélection dynamique intelligente (pas fixe)
   - Score chaque fichier (SNR, durée, silence, stabilité)
   - Prend meilleurs jusqu'à 60-150s total
   - Concatène TOUS en 1 seul reference.wav
```

**Tests utilisateurs + Notre implémentation:**
- Sélection dynamique 60-150s = ✅ OPTIMAL
- 10 fichiers × 7s = 70s ✅ (bon)
- 15 fichiers × 7s = 105s ✅ (excellent)
- 20 fichiers × 7s = 140s ✅ (parfait)
- 30 fichiers × 5s = 150s ✅ (limite max)

---

## 🎚️ Paramètres Chatterbox OPTIMAUX

### Paramètres Disponibles

```python
model.generate(
    text,
    language_id="fr",           # Code langue
    audio_prompt_path="ref.wav", # Fichier référence
    exaggeration=0.5,           # Émotion/expressivité
    cfg_weight=0.5,             # Adhérence locuteur + pacing
    temperature=0.7,            # Variabilité (si supporté)
    speed_factor=1.0,           # Vitesse parole (si supporté)
    seed=42                     # Reproductibilité (si supporté)
)
```

### Paramètres Testés et Validés

#### 1. `exaggeration` (0.0 - 1.0+)
**Fonction:** Contrôle intensité émotionnelle et expressivité

```
0.0 = Voix très plate, monotone
0.3 = Naturel, peu expressif ✅ (pour voix neutre)
0.5 = Default, équilibré ✅ (recommandé général)
0.7 = Expressif, émotionnel ⚠️  (peut sonner exagéré)
1.0+ = Très exagéré ❌ (risque de sur-jeu)
```

**Recommandations par usage:**
```
Actualités/Narration: 0.3-0.4 ✅
Conversation naturelle: 0.4-0.5 ✅
Audiobook/Storytelling: 0.5-0.6 ✅
Personnage émotionnel: 0.6-0.8 ⚠️
```

**Notre config actuelle:**
```python
exag = 0.4  # Moins expressif = plus naturel ✅
```

#### 2. `cfg_weight` (0.0 - 1.0)
**Fonction:** Adhérence au locuteur référence + contrôle pacing (vitesse)

```
0.0 = Ignore référence, pacing lent ❌
0.3 = Locuteurs rapides, réduit pacing ✅
0.5 = Default équilibré ✅
0.7 = Adhérence forte, pacing normal ✅
1.0 = Adhérence maximale ⚠️  (risque rigidité)
```

**Cas spécifiques:**
```
Accent canadien/transfer: cfg_weight=0.0 ✅ (mitigation)
Locuteur rapide: cfg_weight=0.3 ✅ (meilleur pacing)
Voix neutre/standard: cfg_weight=0.5 ✅
Clone précis: cfg_weight=0.7 ✅
```

**Notre config actuelle:**
```python
cfg = 0.55  # Légèrement plus lent ✅
```

#### 3. `temperature` (0.0 - 1.0+)
**Fonction:** Variabilité sortie (pas documenté officiellement)

```
⚠️  NON CONFIRMÉ pour Chatterbox open-source
💡 Si supporté:
   0.7 = Variabilité modérée (standard TTS)
   0.8-1.0 = Plus naturel, moins répétitif
   0.5-0.6 = Plus déterministe
```

#### 4. `speed_factor` (0.5 - 2.0)
**Fonction:** Vitesse parole (pas documenté officiellement)

```
⚠️  NON CONFIRMÉ pour Chatterbox open-source
💡 Si supporté:
   0.8 = 20% plus lent
   1.0 = Vitesse normale
   1.2 = 20% plus rapide
```

#### 5. `language_id`
**CRITIQUE:** Doit correspondre à la langue de `audio_prompt_path`

```python
"en" = Anglais
"fr" = Français ✅
"es" = Espagnol
"de" = Allemand
# ... etc (multilingue)
```

**⚠️  ATTENTION:**
```
Si reference clip ≠ language_id:
→ Accent transfer (voix hérite accent langue référence)
→ Solution: cfg_weight=0 pour mitiger
```

---

## 🎤 Qualité Audio Source

### Environnement Recording

#### Microphone
```
✅ OPTIMAL: Unidirectionnel (cardioïde)
   - Fréquences: 20 Hz - 20 kHz
   - Exemples: Shure SM7B, Rode NT1-A, Audio-Technica AT2020

❌ ÉVITER: Omnidirectionnel (capture trop bruit ambiant)
```

#### Acoustique Pièce
```
✅ MATÉRIAUX:
   - Dry-wall
   - Gypsum board
   - MDF (Medium Density Fiberboard)
   - Bois non poli

❌ ÉVITER:
   - Surfaces réfléchissantes (verre, carrelage)
   - Pièces vides (echo)

💡 Distance murs: Minimum 2 pieds (60 cm)
```

#### Bruit Ambiant
```
✅ AVANT RECORDING:
   - Éteindre climatisation
   - Fermer fenêtres
   - Identifier "flanking paths" (bruit externe)
   - Tester niveau plancher bruit

❌ PENDANT RECORDING:
   - Pas de ventilateurs
   - Pas de bruits électroniques
   - Pas de mouvements brusques
```

### Niveaux Recording

#### Gain Preamp
```
✅ OPTIMAL: -6 dB à -3 dB (volume maximum parole)
⚠️  ATTENTION: Éviter clipping (>0 dB)
❌ ÉVITER: Trop faible (<-20 dB, nécessite boost = bruit)
```

**Notre normalisation actuelle:**
```python
# Peak normalize à -3dB ✅
target_dbfs = -3.0
change_in_dbfs = target_dbfs - audio.max_dBFS
normalized = audio.apply_gain(change_in_dbfs)
```

### Post-Processing

#### ✅ AUTORISÉ
```
✅ UVR (Ultimate Vocal Remover) - extraction vocale
✅ Noise reduction léger (noisereduce)
✅ Normalisation volume (-3 dB peak)
✅ Conversion format (WAV 24kHz+, mono)
```

#### ❌ INTERDIT
```
❌ Compresseurs (réduisent dynamique naturelle)
❌ Equalizers (altèrent caractéristiques vocales)
❌ Analogue emulation / exciters
❌ Reverb / delay
❌ Pitch correction
```

**💡 RÈGLE D'OR:** Audio original non traité = meilleur résultat

---

## 🔧 Résolution Problèmes

### Gibberish / Hallucinations

**Symptômes:**
```
❌ Texte court (<5 mots) génère audio distordu
❌ "Hi!", "Why?", "Yes", "No" = problèmes
❌ Lettres/chiffres isolés = incompréhensible
```

**Causes:**
```
1. Training data limité sur segments courts
2. Architecture modèle (problème général TTS)
3. Texte sans ponctuation
4. Segments incomplets
```

**Solutions:**

#### Preprocessing Text
```python
# ✅ Fusionner segments courts
if len(segment) < 20:
    segment = merge_with_next(segment)

# ✅ Assurer ponctuation finale
if not segment.endswith(('.', '!', '?')):
    segment += '.'

# ✅ Taille chunks
optimal_chunk_size = 200  # caractères
```

#### Post-Generation Validation
```python
# ✅ Whisper transcription validation
transcription = whisper.transcribe(generated_audio)
if similarity(transcription, original_text) < 0.8:
    regenerate()

# ✅ Durée audio (artifacts = plus long)
expected_duration = len(text) * 0.1  # rough estimate
if actual_duration > expected_duration * 1.5:
    regenerate()
```

#### Paramètres
```
⚠️  cfg, temperature, exaggeration: Effet minimal sur gibberish
💡 Meilleure solution: Preprocessing text + validation
```

### Accent Canadien / Transfer

**Problème:**
```
Voix clonée hérite accent langue différente de language_id
Exemple: Reference FR avec canadian accent → output garde accent
```

**Solutions:**
```python
# Solution 1: cfg_weight=0 (ignore partiellement référence)
cfg_weight = 0.0  # ⚠️  Mais perd qualité clone

# Solution 2: UVR + meilleur audio source
use_uvr = True  # Nettoie artifacts pouvant causer accent

# Solution 3: Reference clip DOIT matcher language_id
assert reference_language == language_id  # ✅

# Solution 4: Plusieurs fichiers (dilue accent)
few_shot_files = 10  # Au lieu de 1 ✅
```

### Voix Rapide / Pacing

**Problème:**
```
Locuteur parle trop vite ou trop lent
```

**Solutions:**
```python
# Locuteur trop rapide:
cfg_weight = 0.3  # ✅ Ralentit pacing

# Locuteur trop lent:
cfg_weight = 0.7  # ✅ Accélère pacing

# Alternative (si supporté):
speed_factor = 1.2  # 20% plus rapide
```

---

## 📋 Workflow Optimal (Nos Recommendations)

### 1. Préparation Audio Source

```bash
# Télécharger YouTube
python3 youtube_extract.py --url "..." --voice nom_voix

# OU enregistrer audio studio
# Format: WAV 44.1kHz mono, -6 à -3 dB peak
```

### 2. Nettoyage UVR (Recommandé)

```python
from audio_separator.separator import Separator

separator = Separator()
separator.load_model("UVR-MDX-NET-Voc_FT")
vocals_file = separator.separate("audio.wav")
# → Extrait voix pure, retire musique/bruit
```

### 3. Normalisation & Conversion

```python
# Convertir 44.1kHz mono
audio = audio.set_frame_rate(44100)  # ✅ Upgrade de 22050
audio = audio.set_channels(1)

# Normaliser -3dB
target_dbfs = -3.0
change = target_dbfs - audio.max_dBFS
audio = audio.apply_gain(change)
```

### 4. Few-Shot Concatenation

```python
# Concaténer 5-15 fichiers de 4-10s
# Total: 40-150 secondes idéal
combined = concatenate_audio_files(files)  # ✅
torchaudio.save("reference.wav", combined, 44100)
```

### 5. Voice Cloning

```python
wav = model.generate(
    text,
    language_id="fr",
    audio_prompt_path="reference.wav",
    exaggeration=0.4,   # ✅ Naturel
    cfg_weight=0.55,    # ✅ Pacing équilibré
)
```

### 6. Validation Qualité

```python
# Écoute humaine
# Vérifier:
# - Pas de gibberish
# - Accent correct
# - Pacing naturel
# - Émotions appropriées
```

---

## 📊 Résumé Configuration OPTIMALE

### Audio Source
```yaml
Format: WAV
Sample Rate: 44100 Hz (upgrade recommandé)
Bit Depth: 16-bit minimum, 24-bit idéal
Channels: Mono (1)
Durée totale: 40-150 secondes
Nombre fichiers: 5-15 segments × 4-10s
Volume: -6 à -3 dB peak
Qualité: Single speaker, pas de bruit, studio si possible
```

### Preprocessing
```yaml
UVR: OUI (extraction vocale)
Normalisation: -3 dB peak
Noise reduction: Léger acceptable
Conversion: 44.1kHz mono WAV
Concatenation: OUI (few-shot)
```

### Paramètres Chatterbox
```yaml
language_id: "fr"
exaggeration: 0.4 (naturel) à 0.5 (équilibré)
cfg_weight: 0.5 (standard) à 0.55 (pacing contrôlé)
temperature: 0.7 (si supporté)
speed_factor: 1.0 (si supporté)
```

### Text Preprocessing
```yaml
Min segment length: 20 caractères
Chunk size optimal: ~200 caractères
Ponctuation finale: Obligatoire
Fusion segments courts: OUI
```

---

## 🔬 Tests à Effectuer

### A. Upgrade Sample Rate
```python
# Tester impact 22050Hz → 44100Hz
TARGET_SAMPLE_RATE = 44100  # Au lieu de 22050
```

### B. Paramètres Émotions
```python
# Tester range exaggeration
for exag in [0.3, 0.4, 0.5, 0.6]:
    test_generation(exaggeration=exag)
```

### C. Few-Shot Dynamique (IMPLÉMENTÉ)
```python
# Sélection dynamique automatique
# Prend meilleurs fichiers jusqu'à 60-150s
# Plus besoin de tester manuellement !
python clone_voice.py --voice nom_voix  # Auto 60-150s
```

### D. UVR Impact
```python
# Comparer avec/sans UVR
test_clone(use_uvr=True)
test_clone(use_uvr=False)
```

---

## 📚 Sources

1. **GitHub officiel:** https://github.com/resemble-ai/chatterbox
2. **Issue #39:** Audio clip guidelines
3. **Issue #97:** Gibberish and hallucinations
4. **Resemble AI Docs:** https://knowledge.resemble.ai/
5. **Tests communautaires:** GitHub issues, Reddit, Medium

---

**Dernière mise à jour:** 2025-11-02
**Version:** 1.0
**Testé avec:** Chatterbox 0.5B (MIT), Python 3.10/3.11
