# Mode Freestyle AI - MiniBotPanel v3

## Vue d'ensemble

Le mode **Freestyle AI** permet au robot de générer des réponses dynamiques et contextuelles aux questions hors-script des prospects, en utilisant Ollama (Mistral 7B) pour générer des réponses naturelles et professionnelles.

---

## 🎯 Fonctionnalités

- ✅ **Génération dynamique** : Réponses créées en temps réel selon le contexte
- ✅ **Cache intelligent** : Questions fréquentes mises en cache (LRU, 100 entrées)
- ✅ **Historique conversationnel** : Prend en compte les 5 derniers échanges
- ✅ **Détection automatique** : Identifie le type de question (objection, prix, info)
- ✅ **Prompts adaptés** : 4 types de prompts selon la situation
- ✅ **Validation stricte** : Limite 150 mots, suppression markdown, détection mentions IA
- ✅ **Intégration TTS** : Génère automatiquement l'audio de la réponse

---

## 🚀 Utilisation dans les scénarios

### Format JSON

Pour activer le mode freestyle dans une étape, utilisez `"audio_type": "freestyle"` :

```json
{
  "freestyle_answer": {
    "audio_type": "freestyle",
    "voice": "julie",
    "barge_in": true,
    "timeout": 10,
    "max_turns": 3,
    "context": {
      "agent_name": "Julie",
      "company": "TechCorp",
      "product": "solution d'automatisation",
      "campaign_context": "Prospection B2B pour solution d'automatisation"
    },
    "intent_mapping": {
      "affirm": "question1",
      "question": "freestyle_answer",
      "deny": "objection",
      "*": "question1"
    }
  }
}
```

### Champs spécifiques au mode freestyle

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `audio_type` | string | ✅ | Doit être `"freestyle"` |
| `voice` | string | ❌ | Voix clonée à utiliser (défaut: "julie") |
| `max_turns` | int | ❌ | Nombre max d'échanges freestyle (défaut: 3) |
| `context` | dict | ❌ | Contexte campagne pour génération |
| `timeout` | int | ❌ | Timeout écoute en secondes (défaut: 10) |
| `barge_in` | bool | ❌ | Autoriser interruption (défaut: true) |
| `intent_mapping` | dict | ✅ | Mapping intentions → étapes suivantes |

**Note importante** : Le champ `message_text` n'est **PAS requis** pour les étapes freestyle (généré dynamiquement par l'IA).

---

## 🎨 Exemple de scénario complet

Voir `documentation/scenarios/exemple_freestyle.json` pour un exemple complet.

### Flow typique avec freestyle

```
Robot: "Allô, bonjour Jean. Je suis Julie de TechCorp."
Client: "C'est pour quoi exactement ?"
  → Intent "question" détecté
  → Bascule vers étape "freestyle_answer"

Robot (IA Freestyle): "Je vous appelle pour vous présenter notre solution
  d'automatisation qui aide les entreprises comme la vôtre à gagner du temps
  sur les tâches répétitives. Seriez-vous disponible pour en discuter ?"

Client: "Combien ça coûte ?"
  → Intent "question" + keywords "combien/prix"
  → Type de prompt "question_price" détecté automatiquement

Robot (IA Freestyle): "Le tarif dépend de vos besoins spécifiques et du nombre
  d'utilisateurs. Puis-je vous proposer une démo gratuite de 15 minutes pour
  vous montrer comment ça fonctionne et établir un devis personnalisé ?"

Client: "D'accord, pourquoi pas."
  → Intent "affirm"
  → Retour vers étape scriptée "question1"
```

---

## 🧠 Types de prompts automatiques

Le service FreestyleAI détecte automatiquement le meilleur type de prompt selon les mots-clés :

### 1. **default** (par défaut)
Question générale ou réponse normale.

### 2. **objection**
Détecté si présence de :
- "pas le temps", "pas intéressé", "trop cher"
- "déjà", "pas besoin", "ça va"
- "je réfléchis", "rappeler", "pas maintenant"

**Style de réponse** : Empathique, reconnaît l'objection, propose solution.

### 3. **question_price**
Détecté si présence de :
- "prix", "coût", "combien", "tarif"
- "budget", "cher"

**Style de réponse** : Évite prix précis, explique personnalisation, propose RDV.

### 4. **question_info**
Détecté si présence de :
- "comment", "pourquoi", "quoi"
- "c'est quoi", "qu'est-ce"

**Style de réponse** : Réponse claire et précise, mentionne bénéfice, propose RDV.

---

## 📊 Statistiques disponibles

Le service FreestyleAI collecte des statistiques accessibles via :

```python
stats = robot.freestyle_service.get_stats()
```

**Métriques retournées** :
- `total_requests` : Nombre total de requêtes freestyle
- `successful_generations` : Générations réussies
- `cache_hits` / `cache_misses` : Performance du cache
- `cache_hit_rate_pct` : Taux de hit du cache en %
- `avg_generation_time_ms` : Temps moyen de génération (ms)
- `avg_response_length_words` : Longueur moyenne des réponses (mots)
- `success_rate_pct` : Taux de succès en %
- `cache_size` : Taille actuelle du cache
- `active_conversations` : Nombre de conversations actives
- `model` : Modèle Ollama utilisé

---

## ⚙️ Configuration

### Variables d'environnement

```bash
# Ollama (requis pour freestyle)
OLLAMA_MODEL=mistral:7b
OLLAMA_URL=http://localhost:11434
OLLAMA_TIMEOUT=10

# TTS (requis pour audio freestyle)
COQUI_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
COQUI_USE_GPU=false
PRELOAD_MODELS=true
```

### Paramètres par défaut (modifiables dans le code)

`system/services/freestyle_ai.py` :

```python
self.config = {
    "model": config.OLLAMA_MODEL,
    "max_response_words": 150,       # Max mots par réponse
    "max_context_messages": 5,       # Historique conversationnel
    "temperature": 0.7,              # Créativité (0.0 = déterministe, 1.0 = créatif)
    "cache_size": 100                # Nombre questions en cache
}
```

---

## 🔧 API du service FreestyleAI

### Génération de réponse

```python
response = freestyle_service.generate_response(
    call_uuid="abc-123",
    user_input="C'est pour quoi exactement ?",
    context={
        "agent_name": "Julie",
        "company": "TechCorp",
        "product": "solution CRM",
        "campaign_context": "Prospection B2B"
    },
    prompt_type="default"  # ou "objection", "question_price", "question_info"
)
```

### Détection automatique du type

```python
prompt_type = freestyle_service.detect_prompt_type("Combien ça coûte ?")
# → "question_price"
```

### Nettoyage de l'historique

```python
# Nettoyer historique d'un appel spécifique
freestyle_service.clear_conversation(call_uuid)

# Nettoyer tout le cache
freestyle_service.clear_all_cache()

# Nettoyer tous les historiques
freestyle_service.clear_all_conversations()
```

---

## 🚨 Limites et fallback

### Règles de validation strictes

1. **Maximum 150 mots** : Les réponses trop longues sont tronquées
2. **Suppression markdown** : `**`, `*`, `#`, `` ` `` automatiquement retirés
3. **Détection mentions IA** : Si "en tant qu'IA" détecté → réponse générique
4. **Timeout Ollama** : 10 secondes (configurable)

### Fallback automatique

Si génération échoue, réponse générique :

> "Je n'ai pas toutes les informations pour répondre précisément. Puis-je vous proposer un rendez-vous avec un expert qui pourra vous renseigner en détail ?"

---

## 🎯 Bonnes pratiques

### ✅ DO

- **Mapper "question" → freestyle** dans intent_mapping
- **Limiter max_turns** pour éviter conversations trop longues
- **Fournir contexte riche** (agent_name, company, product)
- **Tester avec vraies questions** de prospects
- **Monitorer cache_hit_rate** pour optimiser prompts

### ❌ DON'T

- **Ne pas utiliser freestyle pour TOUTES les étapes** (coûteux en ressources)
- **Ne pas oublier intent_mapping** (sinon boucle infinie)
- **Ne pas laisser max_turns illimité** (prévoir sortie de secours)
- **Ne pas surcharger le contexte** (trop d'infos = réponses vagues)

---

## 🧪 Tests

### Test unitaire du service

```python
from system.services.freestyle_ai import FreestyleAI

freestyle = FreestyleAI()

# Test question simple
response = freestyle.generate_response(
    call_uuid="test-123",
    user_input="C'est quoi votre solution ?",
    context={"product": "CRM", "company": "TechCorp"}
)

print(response)
# → "Notre solution CRM aide les entreprises à..."
```

### Test de détection

```python
# Objections
assert freestyle.detect_prompt_type("Pas le temps") == "objection"
assert freestyle.detect_prompt_type("Trop cher") == "objection"

# Prix
assert freestyle.detect_prompt_type("Combien ça coûte ?") == "question_price"
assert freestyle.detect_prompt_type("Quel est le tarif ?") == "question_price"

# Info
assert freestyle.detect_prompt_type("Comment ça marche ?") == "question_info"
```

---

## 📈 Performances

### Benchmarks typiques (VPS 4 CPU, Ollama CPU mode)

- **Première génération** : ~2-3 secondes
- **Cache hit** : ~50-100 ms (instantané)
- **Taille moyenne réponse** : 80-120 mots
- **Taux cache hit** : 15-30% (après warm-up)

### Optimisations possibles

1. **GPU** : Activer `COQUI_USE_GPU=true` (génération 5-10x plus rapide)
2. **Modèle plus petit** : `mistral:7b` → `mistral:3b` (2x plus rapide)
3. **Cache Redis** : Implémenter cache partagé entre instances
4. **Pré-génération** : Pré-générer réponses pour top 50 questions

---

## 🐛 Dépannage

### Freestyle ne fonctionne pas

1. **Vérifier Ollama actif** :
```bash
curl http://localhost:11434/api/tags
```

2. **Vérifier logs** :
```bash
tail -f logs/minibot.log | grep Freestyle
```

3. **Tester service directement** :
```python
python3 -c "from system.services.freestyle_ai import FreestyleAI; f = FreestyleAI(); print(f.is_available)"
```

### Réponses incohérentes

- **Augmenter température** : `0.7` → `0.9` (plus créatif)
- **Diminuer température** : `0.7` → `0.3` (plus déterministe)
- **Améliorer prompts** dans `system/services/freestyle_ai.py`
- **Enrichir contexte** dans le scénario JSON

### Cache ne fonctionne pas

- Vérifier hash des questions (case-insensitive, trim)
- Cache est LRU (100 entrées max par défaut)
- Cache est en mémoire (perdu au redémarrage)

---

## 📚 Ressources

- **Code source** : `system/services/freestyle_ai.py`
- **Exemple scénario** : `documentation/scenarios/exemple_freestyle.json`
- **Architecture** : `documentation/BRIEF_PROJET.md` (lignes 163-209)
- **Ollama docs** : https://ollama.com/docs

---

## 🔮 Évolutions futures

- [ ] Cache Redis distribué
- [ ] Modèles fine-tunés par industrie
- [ ] Détection émotions (joie, frustration)
- [ ] Pré-génération top questions
- [ ] Métriques Prometheus/Grafana
- [ ] A/B testing prompts
- [ ] Support GPT-4o (API OpenAI)
- [ ] Voice cloning temps réel (streaming TTS)

---

**Version** : MiniBotPanel v3
**Date** : Octobre 2024
**Auteur** : Claude Code + User
