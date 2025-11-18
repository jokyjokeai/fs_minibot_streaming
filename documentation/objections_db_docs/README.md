# 📚 Objections Database - Structure Modulaire

## 🎯 **Vue d'ensemble**

Système d'objections et FAQ modulaire pour MiniBotPanel v3.

**Structure** : 1 fichier Python = 1 thématique

```
system/objections_db/
├── __init__.py                 # Loader avec auto-include GENERAL
├── objections_general.py       # Objections communes (TOUJOURS chargé)
├── objections_finance.py       # Finance/Banque
├── objections_crypto.py        # Crypto/Trading
├── objections_energie.py       # Énergie/Panneaux solaires
└── README.md                   # Ce fichier
```

---

## 📂 **Structure d'un fichier**

Chaque fichier contient une liste `OBJECTIONS_DATABASE` :

```python
#!/usr/bin/env python3
"""
Objections THÉMATIQUE - MiniBotPanel v3
Description de la thématique.
Audio: audio/{voice}/objections/thematique_*.wav
"""

from typing import List
from system.objections_database import ObjectionEntry

OBJECTIONS_DATABASE: List[ObjectionEntry] = [
    ObjectionEntry(
        keywords=["mot1", "mot2", "mot3"],
        response="Réponse textuelle complète...",
        audio_path="thematique_nom.wav",  # audio/{voice}/objections/
        entry_type="objection"  # ou "faq"
    ),
    # ... autres objections
]
```

---

## 🔧 **Utilisation dans un scénario**

### **Dans le JSON du scénario** :

```json
{
  "name": "Finance B2C",
  "description": "Prospection crédit/épargne",
  "theme_file": "objections_finance",  ← NOM DU FICHIER (sans .py)
  "voice": "julie",
  "steps": {...}
}
```

### **Chargement automatique** :

Le système charge **AUTOMATIQUEMENT** :
1. ✅ `objections_general.py` (20 objections communes)
2. ✅ `objections_finance.py` (20 objections finance)

**Total : 40 objections**

---

## 📊 **Thématiques disponibles**

| Fichier | Thématique | Objections | FAQs | Total |
|---------|------------|------------|------|-------|
| `objections_general.py` | Communes | 10 | 10 | **20** |
| `objections_finance.py` | Finance/Banque | 10 | 10 | **20** |
| `objections_crypto.py` | Crypto/Trading | 5 | 5 | **10** |
| `objections_energie.py` | Énergie/Solaire | 4 | 3 | **7** |

**Exemple** : Scénario Finance charge 40 objections (20 general + 20 finance)

---

## ✍️ **Créer une nouvelle thématique**

### **Étape 1 : Créer le fichier**

```bash
cd system/objections_db/
touch objections_immobilier.py
```

### **Étape 2 : Structure du fichier**

```python
#!/usr/bin/env python3
"""
Objections IMMOBILIER - MiniBotPanel v3

Objections et FAQ spécifiques à l'immobilier:
- Achat, vente, location
- Agences immobilières
- Investissement locatif

Audio: audio/{voice}/objections/immobilier_*.wav
"""

from typing import List
from system.objections_database import ObjectionEntry

OBJECTIONS_DATABASE: List[ObjectionEntry] = [
    # ─────────────────────────────────────────────────────────────────────
    # OBJECTIONS
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "pas le moment acheter", "pas prêt acheter",
            "marché trop cher", "attendre baisse"
        ],
        response="Je comprends votre prudence. Mais le meilleur moment d'acheter c'est quand VOUS êtes prêt. Les taux remontent, attendre peut coûter plus cher. On en parle 10 minutes ?",
        audio_path="immobilier_pas_moment.wav",
        entry_type="objection"
    ),

    ObjectionEntry(
        keywords=[
            "déjà agent", "déjà agence", "en cours",
            "déjà mandaté", "exclusivité"
        ],
        response="Parfait ! Vous êtes combien ? Nous on ne prend pas d'exclusivité. Vous gardez votre agent et on travaille en complément. Double chance de vendre plus vite.",
        audio_path="immobilier_deja_agent.wav",
        entry_type="objection"
    ),

    # ─────────────────────────────────────────────────────────────────────
    # FAQ
    # ─────────────────────────────────────────────────────────────────────
    ObjectionEntry(
        keywords=[
            "commission", "frais agence", "honoraires",
            "combien prenez", "pourcentage"
        ],
        response="Nos honoraires : 3,5% vendeur (vs 5-7% ailleurs). Pas de frais caché. Vous économisez 2000-5000€ sur une vente 200k€. Paiement uniquement à la vente. Ça vous intéresse ?",
        audio_path="immobilier_commission.wav",
        entry_type="faq"
    ),

    # ... autres objections
]
```

### **Étape 3 : Enregistrer les fichiers audio**

Créer les fichiers audio correspondants :

```
audio/
└── julie/
    └── objections/
        ├── immobilier_pas_moment.wav
        ├── immobilier_deja_agent.wav
        └── immobilier_commission.wav
```

### **Étape 4 : Utiliser dans un scénario**

```json
{
  "name": "Prospection Immobilier",
  "theme_file": "objections_immobilier",  ← Nouveau fichier
  "voice": "julie",
  "steps": {...}
}
```

✅ **Le système chargera automatiquement** :
- `objections_general.py` (20 objections)
- `objections_immobilier.py` (vos nouvelles objections)

---

## 🎤 **Conventions de nommage audio**

### **Format** :
```
{thematique}_{sujet}.wav
```

### **Exemples** :
```
general_pas_temps.wav           # Objection générale
general_trop_cher.wav
general_bloctel.wav

finance_deja_banque.wav         # Objection finance
finance_frais.wav
finance_courtier.wav

crypto_risque.wav               # Objection crypto
crypto_securite.wav
crypto_impots.wav

energie_prix.wav                # Objection énergie
energie_arnaque.wav

immobilier_pas_moment.wav       # Votre nouvelle thématique
immobilier_commission.wav
```

---

## 💡 **Bonnes pratiques**

### **Keywords** :
✅ **BON** : Liste exhaustive de variantes
```python
keywords=[
    "pas le temps", "pas de temps", "pas le temps là",
    "occupé", "débordé", "surchargé", "submergé",
    "pas maintenant", "moment pas bon", "pas disponible"
]
```

❌ **MAUVAIS** : Trop peu de keywords
```python
keywords=["pas le temps"]  # Ratera "je suis occupé"
```

### **Réponses** :
- ✅ 2-3 phrases maximum
- ✅ Ton naturel, conversationnel
- ✅ Question fermée à la fin (relance conversation)
- ❌ Pas de jargon technique
- ❌ Pas de phrases trop longues

### **Audio** :
- ✅ Format WAV 16-bit PCM
- ✅ Sample rate 8000 Hz ou 16000 Hz
- ✅ Mono
- ✅ Durée : 5-15 secondes max
- ✅ Ton professionnel mais chaleureux

---

## 🧪 **Tester vos objections**

### **Test 1 : Charger le fichier**

```python
from system.objections_db import load_objections

objections = load_objections("objections_immobilier")
print(f"Loaded {len(objections)} objections")
# Output: Loaded 25 objections (20 general + 5 immobilier)
```

### **Test 2 : Matcher une phrase**

```python
from system.objection_matcher import ObjectionMatcher

matcher = ObjectionMatcher.load_objections_from_file("objections_immobilier")
match = matcher.find_best_match("C'est pas le moment d'acheter")

if match:
    print(f"Match: {match['objection']}")
    print(f"Score: {match['score']:.2f}")
    print(f"Audio: {match['audio_path']}")
```

### **Test 3 : Vérifier audio**

```bash
# Vérifier que les fichiers audio existent
ls -lh audio/julie/objections/immobilier_*.wav
```

---

## 📈 **Statistiques**

Utiliser l'API pour voir les objections les plus matchées :

```bash
GET /api/objections/stats?theme_file=objections_finance&top=10
```

Réponse :
```json
{
  "theme_file": "objections_finance",
  "total_objections": 40,
  "top_matches": [
    {"objection": "déjà une banque", "count": 127, "avg_score": 0.82},
    {"objection": "trop cher", "count": 89, "avg_score": 0.75},
    {"objection": "frais bancaires", "count": 64, "avg_score": 0.78}
  ]
}
```

---

## 🔄 **Migration depuis ancien système**

Si tu as un scénario avec `"theme": "finance"` (ancien système) :

```json
{
  "theme": "finance"  ← ANCIEN
}
```

**Pas de panique !** Le système convertit automatiquement :
- `"theme": "finance"` → `"theme_file": "objections_finance"`

Mais pour les nouveaux scénarios, utilise directement :
```json
{
  "theme_file": "objections_finance"  ← NOUVEAU
}
```

---

## ❓ **FAQ**

### **Q: Puis-je avoir plusieurs fichiers pour une même thématique ?**
Non. 1 thématique = 1 fichier. Si tu as beaucoup d'objections, organise-les en sections dans le même fichier.

### **Q: Que se passe-t-il si je ne mets pas theme_file dans mon scénario ?**
Le système charge `objections_general.py` par défaut (20 objections communes).

### **Q: Puis-je charger 2 thématiques en même temps ?**
Non. Pour l'instant 1 scénario = 1 thématique. Si besoin, crée un fichier hybride.

### **Q: Les fichiers audio sont obligatoires ?**
Non. Si `audio_path` est vide ou fichier manquant, le système joue `not_understood.wav` en fallback.

### **Q: Combien d'objections par fichier ?**
Recommandé : 20-40 objections par thématique. Au-delà, le matching devient moins précis.

---

**Créé par MiniBotPanel v3** - Système d'objections modulaire 🚀
