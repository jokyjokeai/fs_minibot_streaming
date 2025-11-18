# 📁 Structure Audio - MiniBotPanel v3

## 🎯 Organisation

L'audio est organisé **par voix** pour supporter plusieurs voix pré-enregistrées:

```
audio/
├── julie/                      # Voix "Julie" (par défaut)
│   ├── base/                   # Fichiers scénario de base
│   │   ├── hello.wav
│   │   ├── q1.wav
│   │   ├── q2.wav
│   │   ├── q3.wav
│   │   ├── confirm.wav
│   │   ├── bye_success.wav
│   │   ├── bye_failed.wav
│   │   ├── retry_silence.wav   # Retry en cas de silence
│   │   ├── not_understood.wav  # Fallback objection non matchée
│   │   └── ...
│   │
│   └── objections/             # Objections/questions database
│       ├── objection_001.wav
│       ├── objection_002.wav
│       └── ...
│
├── marie/                      # Autre voix (exemple)
│   ├── base/
│   └── objections/
│
└── background/                 # Sons d'ambiance (optionnel)
    └── office_noise.wav
```

---

## 🔧 Configuration

### Voix par défaut
Définie dans `.env` ou `system/config.py`:
```python
DEFAULT_VOICE = "julie"  # Nom du dossier voix par défaut
```

### Dans un scénario JSON
```json
{
  "name": "Vente Produit X",
  "voice": "julie",
  "steps": {
    "hello": {
      "audio_type": "audio",
      "audio_file": "hello.wav",
      "voice": "julie"
    }
  }
}
```

---

## 📂 Fichiers de Base Requis

Chaque voix **DOIT** avoir ces fichiers dans `{voix}/base/`:

### Scénario
- `hello.wav` - Message d'accueil
- `q1.wav`, `q2.wav`, `q3.wav` - Questions
- `confirm.wav` - Confirmation
- `bye_success.wav` - Au revoir (succès)
- `bye_failed.wav` - Au revoir (échec)

### Fallbacks Système
- `retry_silence.wav` - Joué au 1er silence du prospect
- `not_understood.wav` - Joué si objection non matchée

---

## 🎙️ Objections Database

Les fichiers d'objections sont dans `{voix}/objections/`:

### Nommage
Format libre, mais recommandé:
```
objection_001.wav
objection_002.wav
finance_prix_trop_cher.wav
crypto_risque_volatilite.wav
```

### Lien avec Database
Dans la table `objections_database`, le champ `audio_path` contient:
```sql
audio_path = "objection_001.wav"  -- Juste le nom du fichier
```

Le système construit automatiquement le chemin complet:
```python
# audio/{voice}/objections/{audio_path}
audio/julie/objections/objection_001.wav
```

---

## 🚀 Utilisation dans le Code

### Robot FreeSWITCH
```python
from system import config

# Récupérer voix du scénario
voice = scenario.get("voice", config.DEFAULT_VOICE)

# Fichier de base
path = config.get_audio_path(voice, "base", "hello.wav")
# → audio/julie/base/hello.wav

# Fichier objection
path = config.get_audio_path(voice, "objections", "objection_001.wav")
# → audio/julie/objections/objection_001.wav
```

### Création Scénario
Lors de la création d'un scénario avec `create_scenario.py`:
1. Choisir la voix (ex: "julie")
2. Enregistrer les fichiers audio dans `audio/julie/base/`
3. Le scénario JSON référence juste le nom: `"audio_file": "hello.wav"`

---

## 📝 Exemple Complet

### Scénario "finance_b2c"
```json
{
  "name": "Finance B2C",
  "voice": "julie",
  "steps": {
    "hello": {
      "audio_file": "hello.wav",
      "audio_type": "audio"
    },
    "q1": {
      "audio_file": "q1.wav",
      "audio_type": "audio"
    }
  }
}
```

### Fichiers Audio Requis
```
audio/julie/base/hello.wav     ✅
audio/julie/base/q1.wav        ✅
audio/julie/base/retry_silence.wav  ✅ (fallback)
audio/julie/base/not_understood.wav ✅ (fallback)
```

### Objections
```sql
INSERT INTO objections_database (objection, response, audio_path, theme)
VALUES ('Le prix est trop cher',
        'Je comprends...',
        'finance_prix.wav',
        'finance');
```

Fichier: `audio/julie/objections/finance_prix.wav` ✅

---

## 🎨 Ajouter une Nouvelle Voix

1. Créer structure:
```bash
mkdir -p audio/marie/base
mkdir -p audio/marie/objections
```

2. Enregistrer tous les fichiers de base dans `audio/marie/base/`

3. Enregistrer objections dans `audio/marie/objections/`

4. Créer scénario avec `"voice": "marie"`

5. Lancer campagne normalement!

---

## ⚠️ Notes Importantes

### Format Audio
- **Format**: WAV 16-bit PCM
- **Sample Rate**: 8000 Hz ou 16000 Hz
- **Channels**: Mono
- **Codec**: ulaw/alaw (FreeSWITCH compatible)

### Conversion
```bash
# Convertir en format FreeSWITCH
ffmpeg -i input.wav -ar 8000 -ac 1 -acodec pcm_s16le output.wav
```

### Taille
Éviter fichiers >10MB (trop long pour appels)
- hello.wav: ~1-2 secondes (~30-50KB)
- q1.wav: ~3-5 secondes (~80-120KB)
- objection: ~5-10 secondes (~150-300KB)

---

## ✅ Checklist Avant Production

- [ ] Voix par défaut définie (`DEFAULT_VOICE`)
- [ ] Tous fichiers `base/` présents pour chaque voix
- [ ] `retry_silence.wav` créé
- [ ] `not_understood.wav` créé
- [ ] Objections audio enregistrés
- [ ] Chemins `audio_path` corrects en DB
- [ ] Format audio validé (8kHz, mono, WAV)
- [ ] Tests appels avec audio OK

---

## 🐛 Troubleshooting

### Erreur "Audio not found"
```
❌ Retry audio not found: audio/julie/base/retry_silence.wav
```

**Solution**: Créer le fichier manquant
```bash
cd audio/julie/base
# Enregistrer ou copier retry_silence.wav
```

### Objection sans audio
```
⚠️ Audio file not found: objection_042.wav
```

**Solution**:
1. Vérifier `audio_path` en DB
2. Créer fichier dans `audio/{voice}/objections/`

### Mauvaise voix jouée
Vérifier dans le scénario JSON:
```json
"voice": "julie"  // ← Doit correspondre au dossier
```

---

**Généré automatiquement** - MiniBotPanel v3
