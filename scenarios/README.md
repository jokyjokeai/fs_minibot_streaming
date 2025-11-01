# Dossier Scenarios - MiniBotPanel v3

Ce dossier contient tous les scénarios conversationnels générés pour vos campagnes.

## 📁 Structure

Chaque scénario est un fichier JSON nommé selon le pattern : `scenario_<nom>.json`

Exemple:
```
scenarios/
├── scenario_finance_prospect_2024.json
├── scenario_crypto_trading.json
├── scenario_energie_solaire.json
└── README.md
```

## 🚀 Utilisation

### 1. Création d'un scénario

Utilisez le script interactif pour générer un nouveau scénario :

```bash
python3 create_scenario.py
```

Le fichier JSON sera automatiquement sauvegardé dans ce dossier.

### 2. Lancer une campagne avec un scénario

Lorsque vous lancez une campagne, le système vous demandera de choisir parmi les scénarios disponibles dans ce dossier :

```bash
python3 launch_campaign.py
```

Le script listera tous les fichiers `scenario_*.json` et vous permettra de sélectionner celui à utiliser.

## 📊 Format JSON

Structure minimale d'un scénario :

```json
{
  "name": "Nom du scénario",
  "description": "Description courte",
  "steps": {
    "hello": {
      "message_text": "Allô, bonjour {{first_name}}...",
      "audio_type": "tts_cloned",
      "voice": "julie",
      "barge_in": true,
      "timeout": 15,
      "intent_mapping": {
        "affirm": "question1",
        "*": "retry"
      }
    },
    "retry": { ... },
    "question1": { ... },
    ...
  },
  "qualification_rules": {
    "lead": {
      "required_steps": ["question1"],
      "required_intents": {
        "question1": "affirm"
      }
    }
  }
}
```

## 🎯 Thématiques disponibles

Les scénarios peuvent être créés pour les thématiques suivantes :

- **Finance / Banque** : Crédits, épargne, produits bancaires
- **Trading / Crypto** : Plateformes crypto, investissement blockchain
- **Énergie Renouvelable** : Panneaux solaires, pompes à chaleur
- **Immobilier** : Vente, estimation, mandats
- **Assurance** : Auto, habitation, optimisation contrats
- **SaaS B2B** : Solutions logicielles pour entreprises
- **Investissement Or** : Or physique, diversification patrimoine
- **Investissement Vin** : Grands crus, placement alternatif
- **Personnalisé** : Configuration manuelle complète

## 🔧 Modification manuelle

Vous pouvez éditer manuellement les fichiers JSON pour :
- Ajuster les messages textuels
- Modifier les intent_mapping
- Ajouter/supprimer des étapes
- Configurer les timeouts

⚠️  **Important** : Respectez la structure JSON et validez avec un linter avant utilisation.

## 🗑️ Suppression

Pour supprimer un scénario, effacez simplement le fichier JSON correspondant.

---

**Version** : MiniBotPanel v3
**Documentation complète** : `documentation/FREESTYLE_MODE.md`
