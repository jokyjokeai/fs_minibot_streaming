# Migration vers Chatterbox TTS

## 🎯 Pourquoi Chatterbox?

### Comparaison qualité:

| Critère | Chatterbox | XTTS v2 | ElevenLabs |
|---------|-----------|---------|------------|
| **Qualité audio** | ⭐⭐⭐⭐⭐ (Bat ElevenLabs 63.8%) | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Audio requis** | 5-10 secondes | 6 secondes | 30 min - 3 heures |
| **Vitesse génération** | Rapide | Moyen (8-16s) | Rapide |
| **Contrôle émotions** | ✅ Intégré | ❌ Non | ✅ Oui |
| **Langues** | 23 langues | 17 langues | 32 langues |
| **Licence** | MIT (commercial OK) | Non-commercial | Propriétaire |
| **Coût** | **GRATUIT** | **GRATUIT** | $0.30/min |

### Résultats tests:
- **63.8%** des utilisateurs préfèrent Chatterbox à ElevenLabs en blind tests
- **#1 trending** sur HuggingFace
- **MIT License** = usage commercial sans restrictions

---

## 📦 Installation

### Sur le VPS:

```bash
# Télécharger le script
cd /root/fs_minibot_streaming

# Installer Chatterbox (CPU)
./install_chatterbox.sh

# OU avec GPU
./install_chatterbox.sh --gpu
```

### Vérification:

```bash
python3 -c "from chatterbox.tts import ChatterboxTTS; print('✅ Chatterbox OK')"
```

---

## 🎤 Clonage de voix

### Méthode 1: Utiliser fichiers existants

Si tu as déjà cloné avec XTTS:

```bash
# La voix 'tt' existe déjà dans voices/tt/
python3 clone_voice_chatterbox.py --voice tt
```

Chatterbox va:
1. ✅ Utiliser les fichiers `cleaned/*.wav` existants
2. ✅ Sélectionner le meilleur fichier automatiquement
3. ✅ Copier comme `reference.wav`
4. ✅ Générer `test_clone.wav` pour tester la qualité

### Méthode 2: Nouveau clonage

```bash
# Créer dossier
mkdir -p voices/julie

# Ajouter UN fichier audio de 5-10 secondes
cp mon_audio.wav voices/julie/reference.wav

# Cloner
python3 clone_voice_chatterbox.py --voice julie
```

### Générer TTS objections:

```bash
# Générer TOUS les thèmes
python3 clone_voice_chatterbox.py --voice tt

# Générer UN thème spécifique
python3 clone_voice_chatterbox.py --voice tt --theme crypto

# Juste cloner, sans TTS
python3 clone_voice_chatterbox.py --voice tt --skip-tts
```

---

## 🎛️ Paramètres avancés

### Contrôle des émotions:

Dans `system/services/chatterbox_tts.py`:

```python
# Configuration par défaut
"exaggeration": 0.5,      # Emotion control (0.25-2.0)
"cfg_weight": 0.5,        # Pacing control (0.3-0.7)
"temperature": 0.9,       # Randomness (défaut 0.9)
"top_p": 0.95,           # Nucleus sampling
"repetition_penalty": 1.3,  # Anti-répétition
```

### Optimisations par use case:

**Voix expressive/dramatique:**
```python
exaggeration=0.7,  # Plus d'émotion
cfg_weight=0.3     # Ralentir pour compenser
```

**Voix calme/stable:**
```python
exaggeration=0.3,  # Moins d'émotion
cfg_weight=0.6     # Plus délibéré
```

**Speaker rapide:**
```python
cfg_weight=0.3  # Ralentir le débit
```

### Utilisation programmatique:

```python
from system.services.chatterbox_tts import ChatterboxTTSService

tts = ChatterboxTTSService()

# Charger voix
tts.load_voice("julie")

# Générer avec paramètres custom
audio_file = tts.synthesize_with_voice(
    "Bonjour, ceci est un test",
    voice_name="julie",
    exaggeration=0.7,  # Plus expressif
    cfg_weight=0.4     # Légèrement ralenti
)
```

---

## 🔄 Migration depuis XTTS

### Option 1: Garder les deux (recommandé pour transition)

```python
# Dans robot_freeswitch.py ou autres fichiers

# Garder XTTS (ancien)
from system.services.coqui_tts import CoquiTTS

# Ajouter Chatterbox (nouveau)
from system.services.chatterbox_tts import ChatterboxTTSService

# Utiliser selon besoin
tts_xtts = CoquiTTS()
tts_chatterbox = ChatterboxTTSService()
```

### Option 2: Remplacement complet

1. Chercher tous les imports de `CoquiTTS`:
```bash
grep -r "from system.services.coqui_tts import CoquiTTS" .
```

2. Remplacer par:
```python
from system.services.chatterbox_tts import ChatterboxTTSService as CoquiTTS
```

3. L'API est compatible (mêmes méthodes):
   - `load_voice(voice_name)`
   - `synthesize_with_voice(text, voice_name, output_file)`
   - `clone_voice(audio_path, voice_name)`

---

## 📊 Tests de qualité

### Test 1: Générer test audio

```bash
python3 clone_voice_chatterbox.py --voice tt --skip-tts
```

Écouter: `voices/tt/test_clone.wav`

### Test 2: Comparer XTTS vs Chatterbox

```bash
# XTTS (ancien)
python3 -c "
from system.services.coqui_tts import CoquiTTS
tts = CoquiTTS()
tts.load_voice('tt')
tts.synthesize_with_voice('Bonjour test XTTS', 'tt', 'test_xtts.wav')
"

# Chatterbox (nouveau)
python3 -c "
from system.services.chatterbox_tts import ChatterboxTTSService
tts = ChatterboxTTSService()
tts.load_voice('tt')
tts.synthesize_with_voice('Bonjour test Chatterbox', 'tt', 'test_chatterbox.wav')
"

# Télécharger et comparer
scp root@VPS:/root/fs_minibot_streaming/test_*.wav .
```

---

## 🐛 Troubleshooting

### Erreur: "Chatterbox TTS not available"

```bash
# Vérifier installation
pip list | grep chatterbox

# Réinstaller
pip uninstall chatterbox-tts
pip install chatterbox-tts
```

### Erreur: "No reference audio found"

```bash
# Vérifier fichiers
ls -lh voices/tt/

# Doit avoir AU MOINS UN de:
# - reference.wav
# - test_clone.wav
# - cleaned/*.wav
```

### Audio de mauvaise qualité

1. **Vérifier fichier source:**
   - Minimum 5-10 secondes
   - UN SEUL speaker
   - Pas de bruit de fond
   - Pas de musique

2. **Ajuster paramètres:**
   ```python
   # Voix plus stable
   exaggeration=0.4,
   cfg_weight=0.6
   ```

3. **Utiliser meilleur fichier:**
   ```bash
   # Trier par taille (plus gros = souvent meilleur)
   ls -lhS voices/tt/cleaned/*.wav | head

   # Copier le meilleur comme reference
   cp voices/tt/cleaned/youtube_008_cleaned.wav voices/tt/reference.wav

   # Re-cloner
   python3 clone_voice_chatterbox.py --voice tt --force
   ```

---

## 📈 Performance

### Temps de génération comparés:

| Modèle | Temps moyen | Temps pour 165 fichiers |
|--------|-------------|-------------------------|
| XTTS v2 | 10-16s par fichier | ~30-45 minutes |
| Chatterbox | 2-5s par fichier | ~5-15 minutes |

### Utilisation mémoire:

- **XTTS v2:** ~2-3 GB VRAM/RAM
- **Chatterbox:** ~1-2 GB VRAM/RAM

---

## ✅ Checklist migration

- [ ] Installer Chatterbox: `./install_chatterbox.sh`
- [ ] Tester import: `python3 -c "from chatterbox.tts import ChatterboxTTS"`
- [ ] Cloner voix test: `python3 clone_voice_chatterbox.py --voice tt --skip-tts`
- [ ] Écouter qualité: `voices/tt/test_clone.wav`
- [ ] Générer TTS objections: `python3 clone_voice_chatterbox.py --voice tt --theme crypto`
- [ ] Comparer qualité XTTS vs Chatterbox
- [ ] Si satisfait, générer TOUS les TTS: `python3 clone_voice_chatterbox.py --voice tt`
- [ ] Mettre à jour `robot_freeswitch.py` pour utiliser Chatterbox

---

## 🎓 Ressources

- **GitHub:** https://github.com/resemble-ai/chatterbox
- **HuggingFace:** https://huggingface.co/ResembleAI/chatterbox
- **Documentation:** https://www.resemble.ai/chatterbox/
- **Licence:** MIT (https://opensource.org/licenses/MIT)

---

## 📞 Support

Si problèmes:
1. Vérifier logs: `tail -f /var/log/minibot/*.log`
2. Tester en local: `python3 clone_voice_chatterbox.py --voice tt`
3. Vérifier versions: `pip list | grep -E "torch|chatterbox"`
