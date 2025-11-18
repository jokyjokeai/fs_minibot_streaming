# Scenario Advanced Features Guide

**MiniBotPanel v3 - Architecture Scenario-Driven**

Ce guide explique toutes les nouvelles features rendant les scénarios 100% configurables sans modifier le code.

---

## Table des Matières

1. [Intents Database (Fuzzy Matching)](#1-intents-database)
2. [Steps Terminaux (is_terminal)](#2-steps-terminaux)
3. [Actions Configurables](#3-actions-configurables)
4. [Transfert d'Appel](#4-transfert-dappel)
5. [Fallbacks Configurables](#5-fallbacks-configurables)
6. [Exemple Complet](#6-exemple-complet)

---

## 1. Intents Database

### Qu'est-ce que c'est?

Système de détection d'intents avec **fuzzy matching** (comme `objection_matcher`).

### Structure

```
system/intents_db/
├── __init__.py              # Loader + fuzzy matching
├── intents_basic.py         # affirm, deny, unsure (TOUJOURS chargé)
├── intents_general.py       # question, objection (TOUJOURS chargé)
└── intents_{theme}.py       # Intents spécifiques (optionnel)
```

### Intents de base

| Intent | Description | Exemples keywords |
|--------|-------------|-------------------|
| `affirm` | Réponse positive | "oui", "d'accord", "ok", "absolument" |
| `deny` | Réponse négative | "non", "pas intéressé", "ça va" |
| `unsure` | Hésitation | "peut-être", "je sais pas", "hésiter" |
| `question` | Question client | "qui", "quoi", "comment", "pourquoi" |
| `objection` | Objection | "pas le temps", "trop cher", "rappeler" |
| `silence` | Pas de réponse | (détecté par VAD, pas de keywords) |

### Utilisation

Automatique! Le système essaie **fuzzy matching AVANT** keywords hardcodés.

**Logs:**
```
Intent analysis: 'ouais ouais je suis là...' -> affirm
(conf: 0.85, reason: fuzzy_match 'ouais', latency: 5.2ms)
```

### Ajouter des intents personnalisés (futur)

Créer `system/intents_db/intents_immobilier.py`:

```python
from system.intents_db import IntentEntry

INTENTS_DATABASE = [
    IntentEntry(
        intent="transfer_request",
        keywords=["conseiller", "agent", "humain", "parler à quelqu'un"],
        confidence_base=0.75
    )
]
```

---

## 2. Steps Terminaux

### Avant (hardcodé)

```python
# Code cherchait "bye", "bye_failed", "Bye_*"
if step_name.lower() in ["bye", "bye_failed"]:
    terminate_call()
```

**Problème:** Impossible d'utiliser noms personnalisés!

### Après (configurable)

```json
{
  "steps": {
    "transfer_agent": {
      "is_terminal": true,  ← Propriété JSON!
      "result": "completed",
      "intent_mapping": {"*": "end"}
    }
  }
}
```

### Propriétés terminal steps

| Propriété | Description | Valeurs |
|-----------|-------------|---------|
| `is_terminal` | Termine l'appel | `true` / `false` |
| `result` | Type de résultat | `"completed"`, `"failed"`, `"no_answer"` |

### Compatibilité legacy

Les noms suivants sont **automatiquement** terminaux:
- `bye`
- `bye_failed`
- `end`
- `Bye_*` (tout nom commençant par "Bye_")

**Recommandation:** Utilisez `is_terminal: true` pour nouveaux scénarios.

---

## 3. Actions Configurables

### Qu'est-ce que c'est?

Exécuter des actions (email, webhook, CRM, etc.) **depuis le scénario JSON**.

### Syntaxe

```json
{
  "steps": {
    "qualified_lead": {
      "actions": [
        {
          "type": "send_email",
          "config": {
            "template": "lead_interested",
            "to": "{{client_email}}",
            "subject": "Confirmation - {{project_name}}"
          }
        },
        {
          "type": "webhook",
          "config": {
            "url": "https://crm.example.com/api/leads",
            "method": "POST",
            "data": {
              "source": "cold_call",
              "status": "qualified"
            }
          }
        }
      ]
    }
  }
}
```

### Types d'actions disponibles

| Type | Description | Status |
|------|-------------|--------|
| `send_email` | Envoi email via API | ⚠️ Placeholder (à implémenter) |
| `webhook` | Appel webhook HTTP POST | ⚠️ Placeholder (à implémenter) |
| `transfer` | Transfert d'appel SIP | ✅ Implémenté |
| `update_crm` | Mise à jour CRM | ⚠️ Placeholder (à implémenter) |

### Quand les actions sont-elles exécutées?

**Avant** le `hangup()` dans les steps terminaux:

```
1. Joue audio final
2. Exécute actions ← ICI
3. Raccroche appel
```

---

## 4. Transfert d'Appel

### Configuration

```json
{
  "steps": {
    "transfer_sales": {
      "is_terminal": true,
      "result": "completed",
      "actions": [
        {
          "type": "transfer",
          "config": {
            "destination": "sip:sales@example.com",
            "timeout": 30,
            "on_no_answer": "leave_voicemail"
          }
        }
      ]
    }
  }
}
```

### Destination formats

| Format | Exemple | Description |
|--------|---------|-------------|
| SIP URI | `sip:sales@domain.com` | Transfert SIP |
| Extension | `1234` | Extension interne FreeSWITCH |
| DID | `+33612345678` | Numéro externe (selon dialplan) |

### Logs

```
📞 [db07fd88] Transferring call to: sip:sales@example.com
   Timeout: 30s
✅ [db07fd88] Call transferred successfully to sip:sales@example.com
```

### Fallback si échec

```json
{
  "config": {
    "destination": "sip:sales@example.com",
    "on_no_answer": "leave_voicemail"  ← Step de fallback
  }
}
```

---

## 5. Fallbacks Configurables

### Avant (hardcodé)

```python
# Si silence et pas de mapping → "bye_failed" hardcodé
next_step = intent_mapping.get("silence", "bye_failed")
```

### Après (configurable)

```json
{
  "metadata": {
    "fallbacks": {
      "silence": "retry_question",  ← Personnalisé!
      "unknown": "not_understood",
      "deny": "bye_polite"
    }
  }
}
```

### Fallbacks disponibles

| Fallback | Quand utilisé | Défaut (si non configuré) |
|----------|---------------|---------------------------|
| `silence` | Client ne répond pas | `"bye_failed"` |
| `unknown` | Intent non mappé | `"bye_failed"` |
| `deny` | Refus sans mapping | `"bye_failed"` |

### Exemple use case

**Scénario VIP:** Silence → Transfert agent (au lieu de "bye_failed")

```json
{
  "metadata": {
    "fallbacks": {
      "silence": "transfer_vip_agent",
      "unknown": "transfer_vip_agent"
    }
  }
}
```

---

## 6. Exemple Complet

Voir fichier: `scenarios/example_advanced_features.json`

### Features démontrées

✅ **Intents fuzzy matching** (automatique)
✅ **Steps terminaux** (`is_terminal: true`)
✅ **Actions configurables** (transfer + webhook)
✅ **Fallbacks personnalisés** (metadata.fallbacks)
✅ **MaxTurns** (objection_matcher)
✅ **Transfert d'appel** (SIP)

### Scénario flow

```
intro
  ├─ affirm → qualify_owner
  ├─ deny → bye_not_interested (terminal)
  └─ silence → retry_intro
      ├─ affirm → qualify_owner
      ├─ deny → bye_not_interested (terminal)
      └─ silence → bye_no_answer (terminal + webhook)

qualify_owner
  ├─ affirm → transfer_or_callback (terminal + transfer + webhook)
  ├─ deny → bye_not_qualified (terminal)
  ├─ silence → bye_no_answer (terminal)
  └─ objection → objection_loop (MaxTurns=2)
```

---

## Migration Ancien → Nouveau

### Ancien scénario

```json
{
  "steps": {
    "bye": {
      "audio_file": "bye.wav",
      "result": "completed"
    }
  }
}
```

### Nouveau scénario (recommandé)

```json
{
  "metadata": {
    "fallbacks": {
      "silence": "retry_silence",
      "unknown": "not_understood"
    }
  },
  "steps": {
    "aurevoir": {
      "audio_file": "bye.wav",
      "is_terminal": true,  ← Nouveau
      "result": "completed",
      "actions": [          ← Nouveau
        {
          "type": "webhook",
          "config": {
            "url": "https://crm.example.com/api/call-completed"
          }
        }
      ]
    }
  }
}
```

---

## FAQ

### Q: Les anciens scénarios marchent encore?

**R:** Oui! Compatibilité 100%. Les steps `bye`, `bye_failed` sont auto-détectés comme terminaux.

### Q: Dois-je utiliser intents_db?

**R:** Non obligatoire! Le système fallback sur keywords hardcodés si fuzzy matching échoue. Mais fuzzy matching est plus flexible.

### Q: Comment tester le transfert?

**R:**
1. Créer step avec `is_terminal: true` + `action: transfer`
2. Lancer `test_real_call.py`
3. Vérifier logs: `📞 Transferring call to: ...`

### Q: Les actions email/webhook fonctionnent?

**R:** Actuellement **placeholders** (logs seulement). À implémenter selon vos besoins:
- Email: API Sendgrid, Mailgun, etc.
- Webhook: `requests.post(url, json=data)`

---

## Support

- GitHub Issues: https://github.com/anthropics/claude-code/issues
- Documentation: `/documentation/`
- Exemples: `/scenarios/example_advanced_features.json`

---

**Version:** 3.0
**Date:** 2025-01-18
**Auteur:** Generated with Claude Code
