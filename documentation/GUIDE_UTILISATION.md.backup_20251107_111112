# MiniBotPanel v3 - Guide d'Utilisation

## 📖 Table des Matières

1. [Introduction](#introduction)
2. [Démarrage Rapide](#démarrage-rapide)
3. [Gestion des Contacts](#gestion-des-contacts)
4. [Création de Scénarios v3](#création-de-scénarios-v3)
5. [Mode Freestyle AI](#mode-freestyle-ai)
6. [Personnalités d'Agent](#personnalités-dagent)
7. [Objections et Matching](#objections-et-matching)
8. [Clonage Vocal](#clonage-vocal)
9. [Gestion des Campagnes](#gestion-des-campagnes)
10. [Monitoring en Temps Réel](#monitoring-en-temps-réel)
11. [Exports et Rapports](#exports-et-rapports)
12. [API REST](#api-rest)
13. [Workflows Complets](#workflows-complets)
14. [Troubleshooting](#troubleshooting)
15. [FAQ](#faq)

---

## 🚀 Introduction

Ce guide vous accompagne dans l'utilisation quotidienne de MiniBotPanel v3 pour créer et gérer vos campagnes d'appels automatisés avec **IA Freestyle**, **matching d'objections** et **personnalités configurables**.

### 🆕 Nouveautés v3

✅ **Freestyle AI** : Réponses dynamiques générées par Ollama (Mistral 7B)
✅ **Objection Matching** : Détection fuzzy de 153 objections pré-enregistrées
✅ **7 Personnalités** : Agent configurable (Professionnel, Doux, Dynamique, etc.)
✅ **9 Thématiques** : Or, Vin, Crypto, Finance, Immobilier, etc.
✅ **Sélection interactive** : Menu coloré pour choix scénarios

### Prérequis

Avant de commencer, assurez-vous que :
- ✅ Le système est installé (voir `GUIDE_INSTALLATION.md`)
- ✅ PostgreSQL est démarré
- ✅ FreeSWITCH est démarré
- ✅ **Ollama service est démarré** (`ollama serve`) ← NOUVEAU v3
- ✅ **Modèle Ollama téléchargé** (`ollama pull mistral:7b`) ← NOUVEAU v3
- ✅ L'API REST est démarrée (`uvicorn system.api.main:app`)

### Vérification Rapide

```bash
# 1. Vérifier l'API (avec Ollama check)
curl http://localhost:8000/health

# Réponse attendue (v3):
# {
#   "status": "healthy",
#   "components": {
#     "database": {"status": "healthy"},
#     "freeswitch": {"status": "healthy"},
#     "vosk": {"status": "healthy"},
#     "ollama": {"status": "healthy", "model": "mistral:7b"},  ← NOUVEAU
#     "objection_matcher": {"total_objections": 153}  ← NOUVEAU
#   }
# }

# 2. Vérifier Ollama directement
curl http://localhost:11434/api/tags

# 3. Vérifier la base de données
psql -U minibot -d minibot_freeswitch -c "SELECT COUNT(*) FROM contacts;"
```

---

## ⚡ Démarrage Rapide

### Workflow Basique v3 (6 étapes)

```bash
# 1. Importer contacts
python import_contacts.py contacts.csv

# 2. Créer un scénario (MODE INTERACTIF v3)
python create_scenario.py --interactive
# → Choix thématique: Or Investissement
# → Choix objectif: Prise de RDV
# → Choix personnalité: Professionnel

# 3. Cloner une voix
python clone_voice.py voices/commercial.wav

# 4. Lancer campagne (MODE INTERACTIF v3)
python launch_campaign.py --interactive
# → Menu coloré avec liste scénarios disponibles

# 5. Monitorer en temps réel
python monitor_campaign.py --campaign-id 1

# 6. Exporter résultats
python export_campaign.py --campaign-id 1 --format excel
```

### Exemple Complet A-Z avec Freestyle AI

```bash
# Étape 1: Préparer fichier contacts
cat > contacts_test.csv << EOF
phone,first_name,last_name,company,email
+33612345678,Jean,Dupont,ACME Corp,jean@acme.com
+33698765432,Marie,Martin,Tech Inc,marie@tech.com
EOF

# Étape 2: Importer contacts
python import_contacts.py contacts_test.csv
# ✅ Imported 2 contacts

# Étape 3: Créer scénario avec Freestyle AI (mode interactif)
python create_scenario.py --interactive

# Assistant interactif v3:
# ┌────────────────────────────────────────────────┐
# │ 🎬 Création Scénario MiniBotPanel v3           │
# └────────────────────────────────────────────────┘
#
# 1️⃣ Nom du scénario: Vente Or Investissement
#
# 2️⃣ Thématique:
#    1. Standard
#    2. Finance
#    3. Trading Crypto
#    4. Or Investissement  ← NOUVEAU v3
#    5. Vin Investissement  ← NOUVEAU v3
#    ...
# Choix: 4
#
# 3️⃣ Objectif de campagne:
#    1. Prise de RDV
#    2. Génération de lead
#    3. Transfert d'appel
# Choix: 1
#
# 4️⃣ Personnalité de l'agent:
#    1. Professionnel (neutre, courtois, expert)
#    2. Doux (chaleureux, empathique)
#    3. Dynamique (énergique, motivant)
#    4. Assertif (direct, confiant)
#    5. Expert (technique, pédagogue)
#    6. Commercial (opportuniste, conversion)
#    7. Consultative (collaboratif, questionnant)
# Choix: 1
#
# ✅ Scénario créé: scenarios/scenario_or_investissement.json
# ✅ 153 objections chargées pour thématique "or"
# ✅ Contexte Freestyle AI configuré

# Étape 4: Cloner voix
python clone_voice.py voices/commercial.wav --name "Voix Pro"
# ✅ Voice cloned: ID 1

# Étape 5: Lancer campagne (mode interactif v3)
python launch_campaign.py --interactive

# Menu coloré:
# ╔════════════════════════════════════════════════════════════════╗
# ║  📋 Scénarios disponibles (3 trouvés)                          ║
# ╚════════════════════════════════════════════════════════════════╝
#
# 1. Vente Or Investissement
#    Prospection pour investissement en or physique
#    📅 Objectif: appointment | 7 étapes
#
# 2. Test Démo Freestyle
#    Scénario de test pour valider le mode Freestyle AI
#    📅 Objectif: appointment | 9 étapes
#
# 3. Vin Grands Crus
#    Prospection investissement vin
#    📞 Objectif: lead_generation | 6 étapes
#
# Choisissez un scénario [1-3]: 1
#
# ✅ Scénario sélectionné: Vente Or Investissement
# 🚀 Campaign launched: ID 1

# Étape 6: Monitorer
python monitor_campaign.py --campaign-id 1 --refresh 5
```

---

## 👥 Gestion des Contacts

### 1. Import depuis CSV

**Format CSV requis** :
```csv
phone,first_name,last_name,company,email,tags
+33612345678,Jean,Dupont,ACME Corp,jean@acme.com,"prospect,vip"
+33698765432,Marie,Martin,Tech Inc,marie@tech.com,"client,actif"
```

**Champs obligatoires** :
- `phone` : Numéro au format international (+33...) ✅ **OBLIGATOIRE**

**Import** :
```bash
python import_contacts.py contacts.csv

# Options avancées
python import_contacts.py contacts.csv \
  --skip-duplicates \
  --validate-phones \
  --add-tags "campagne_janvier,segment_A"

# Output:
# ✅ Valid: 150 contacts
# ⚠️ Duplicates: 5 contacts (skipped)
# ❌ Invalid phones: 3 contacts (skipped)
# 📊 Total imported: 150 contacts
```

### 2. Gestion via API

```bash
# Créer contact
curl -X POST "http://localhost:8000/api/contacts?password=your_password" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+33612345678",
    "first_name": "Jean",
    "last_name": "Dupont"
  }'

# Lister contacts
curl "http://localhost:8000/api/contacts?password=your_password"

# Blacklister contact
curl -X PATCH "http://localhost:8000/api/contacts/1?password=your_password" \
  -d '{"blacklist": true}'
```

---

## 📝 Création de Scénarios v3

### 1. Mode Interactif (NOUVEAU v3)

```bash
python create_scenario.py --interactive
```

**Workflow création** :

1. **Nom du scénario**
2. **Choix thématique** (9 disponibles) ← NOUVEAU v3
   - Standard
   - Finance / Banque
   - Trading Crypto
   - Énergie Renouvelable
   - Immobilier
   - Assurance
   - SaaS B2B
   - **Or Investissement** ← NOUVEAU v3
   - **Vin Investissement** ← NOUVEAU v3

3. **Choix objectif campagne** ← NOUVEAU v3
   - Prise de RDV
   - Génération de lead
   - Transfert d'appel

4. **Choix personnalité agent** ← NOUVEAU v3
   - Professionnel
   - Doux
   - Dynamique
   - Assertif
   - Expert
   - Commercial
   - Consultative

5. **Configuration étapes** (avec support Freestyle AI)

### 2. Structure Scénario JSON v3

**Exemple avec Freestyle AI** :

```json
{
  "name": "Investissement Or - RDV Expert",
  "description": "Prospection pour investissement en or physique",
  "campaign_objective": "appointment",
  "steps": {
    "hello": {
      "message_text": "Bonjour {{first_name}}, je suis Julie de GoldInvest. Avez-vous 2 minutes ?",
      "audio_type": "tts_cloned",
      "voice": "julie",
      "barge_in": true,
      "timeout": 15,
      "intent_mapping": {
        "affirm": "pitch",
        "question": "freestyle_answer",
        "deny": "objection",
        "*": "retry"
      }
    },

    "freestyle_answer": {
      "audio_type": "freestyle",
      "voice": "julie",
      "barge_in": true,
      "timeout": 10,
      "max_turns": 3,
      "context": {
        "agent_name": "Julie",
        "company": "GoldInvest",
        "product": "investissement en or physique",
        "campaign_context": "Prospection pour investissement en or (lingots, pièces). Marché 2025 : +110% depuis 2020, protection inflation, tangible.",
        "campaign_objective": "L'objectif est d'obtenir un rendez-vous avec un expert en investissement or pour présenter nos solutions d'achat de lingots et pièces. Proposer des créneaux cette semaine ou la suivante.",
        "agent_tone": "professionnel, courtois, posé, crédible",
        "agent_style": "Phrases claires et structurées. Vouvoiement. Arguments factuels et chiffrés (ROI, historique or, comparaisons crypto/actions)."
      },
      "intent_mapping": {
        "affirm": "pitch",
        "question": "freestyle_answer",
        "deny": "objection",
        "*": "pitch"
      }
    },

    "pitch": {
      "message_text": "L'or a pris +110% depuis 2020. C'est le moment idéal pour diversifier. Seriez-vous disponible mardi pour un RDV de 30 minutes ?",
      "audio_type": "tts_cloned",
      "voice": "julie",
      "intent_mapping": {
        "affirm": "confirm_lead",
        "deny": "objection",
        "*": "bye_not_sure"
      }
    },

    "objection": {
      "message_text": "Je comprends votre hésitation. Justement, nos clients avaient les mêmes questions au début.",
      "audio_type": "tts_cloned",
      "voice": "julie",
      "intent_mapping": {
        "affirm": "pitch",
        "question": "freestyle_answer",
        "deny": "bye_not_interested"
      }
    }
  }
}
```

### 3. Types de Steps v3

#### **message** : Robot parle (classique)
```json
{
  "message_text": "Bonjour {{first_name}}",
  "audio_type": "tts_cloned",
  "voice": "julie"
}
```

#### **freestyle** : IA génère réponse ← NOUVEAU v3
```json
{
  "audio_type": "freestyle",
  "voice": "julie",
  "max_turns": 3,
  "context": {
    "agent_name": "Julie",
    "campaign_objective": "Prise de RDV",
    "agent_tone": "professionnel, courtois",
    "agent_style": "Phrases courtes. Vouvoiement."
  }
}
```

### 4. Variables Dynamiques

**Variables disponibles** :
- `{{first_name}}` : Prénom contact
- `{{last_name}}` : Nom contact
- `{{company}}` : Entreprise
- `{{email}}` : Email
- `{{phone}}` : Téléphone

---

## 🎯 Mode Freestyle AI

### 1. Qu'est-ce que le Freestyle AI ?

Le **Freestyle AI** permet au robot de générer des réponses dynamiques adaptées aux questions hors-script du prospect, en utilisant **Ollama** (Mistral 7B).

**Avantages** :
- ✅ Réponses contextuelles intelligentes
- ✅ Adaptées au produit/service
- ✅ Cohérentes avec la personnalité de l'agent
- ✅ Fallback vers objections pré-enregistrées si matching

**Workflow Freestyle** :
```
1. Prospect pose question hors-script
   ↓
2. ObjectionMatcher : Fuzzy matching (153 objections)
   ↓
3a. Match trouvé (score ≥ 0.5)
    → Play audio pré-enregistré (~50ms)
   ↓
3b. Pas de match (score < 0.5)
    → Freestyle AI génère réponse via Ollama (~1-2s)
   ↓
4. TTS génère audio → Play au prospect
   ↓
5. Continue conversation (max_turns limite)
```

### 2. Configuration Freestyle dans Scénario

**Step freestyle minimal** :
```json
{
  "freestyle_answer": {
    "audio_type": "freestyle",
    "voice": "julie",
    "max_turns": 3,
    "timeout": 10,
    "context": {
      "agent_name": "Julie",
      "company": "TechCorp",
      "product": "solution d'automatisation",
      "campaign_objective": "Obtenir un rendez-vous"
    }
  }
}
```

**Context complet (recommandé)** :
```json
{
  "context": {
    "agent_name": "Julie",
    "company": "GoldInvest",
    "product": "investissement en or physique (lingots, pièces)",
    "campaign_context": "Prospection B2B/B2C pour investissement or. Marché 2025 : +110% depuis 2020, protection inflation, AMF régulé.",
    "campaign_objective": "L'objectif est d'obtenir un rendez-vous avec un expert. Proposer créneaux cette semaine.",
    "agent_tone": "professionnel, courtois, posé, crédible",
    "agent_style": "Phrases claires et structurées. Vouvoiement. Arguments factuels : chiffres ROI, comparaisons crypto/actions, réglementations AMF."
  }
}
```

### 3. Paramètres Freestyle (.env)

```bash
# Modèle Ollama à utiliser
OLLAMA_MODEL=mistral:7b  # ou llama3.2:1b, llama3.2:3b

# Température (créativité) : 0.0 = strict, 1.0 = créatif
OLLAMA_TEMPERATURE=0.7

# Nombre max de tokens par réponse
OLLAMA_MAX_TOKENS=150

# Nombre max de tours Freestyle avant fallback
FREESTYLE_MAX_TURNS=3

# Timeout génération (secondes)
FREESTYLE_TIMEOUT=10
```

**Recommandations par cas d'usage** :

| Cas d'usage | TEMPERATURE | MAX_TOKENS | MAX_TURNS |
|-------------|-------------|------------|-----------|
| Strict (script proche) | 0.3 | 100 | 2 |
| Équilibré (recommandé) | 0.7 | 150 | 3 |
| Créatif (vente conseil) | 0.9 | 200 | 5 |

### 4. Exemple Conversation Freestyle

```
Robot: "Bonjour Jean, je suis Julie de GoldInvest. Nous proposons des solutions d'investissement en or physique."

Prospect: "L'or c'est pas un peu risqué ça ?"

  ↓ ObjectionMatcher (fuzzy)
  ✅ Match trouvé: "C'est risqué" (score: 0.72)
  → Audio pré-enregistré (50ms):

Robot: "Risqué ? L'or existe depuis 5000 ans et n'a JAMAIS valu zéro ! En fait c'est l'inverse : l'or protège de l'inflation. +110% depuis 2020."

Prospect: "Ouais mais avec les cryptos maintenant, c'est pas mieux ?"

  ↓ ObjectionMatcher (fuzzy)
  ❌ Pas de match (score: 0.42 < 0.5)
  → Freestyle AI (Ollama génération 1.5s):

Robot: "Les cryptos sont volatiles : +50% un jour, -40% le lendemain. L'or lui, monte stable depuis 2020. Et surtout, l'or est tangible - vous pouvez le tenir dans vos mains, pas le Bitcoin."

Prospect: "D'accord, et combien faut investir minimum ?"

  ↓ Freestyle AI (question ouverte):

Robot: "Vous pouvez commencer dès 1000€. Nos clients investissent en moyenne entre 5000€ et 15000€. Vous préférez quel montant pour démarrer ?"

Prospect: "5000€ ça me semble bien"

  ↓ Intent: positive
  → Transition vers "confirm_lead"

Robot: "Parfait ! Je vous propose un rendez-vous mardi à 14h avec notre expert. Ça vous convient ?"
```

---

## 🎭 Personnalités d'Agent

### 1. Les 7 Personnalités (NOUVEAU v3)

| Personnalité | Ton | Style | Cas d'usage |
|--------------|-----|-------|-------------|
| **Professionnel** | Neutre, courtois, expert | Phrases structurées, vouvoiement, chiffres | B2B, Finance, Immobilier |
| **Doux** | Chaleureux, empathique, rassurant | Écoute active, reformulation, apaisant | Senior, Assurance, Santé |
| **Dynamique** | Énergique, enthousiaste, motivant | Rythme rapide, exclamations | B2C, Sport, Événementiel |
| **Assertif** | Direct, confiant, persuasif | Affirmations claires, challenges | Trading, Crypto, Coaching |
| **Expert** | Technique, pédagogue, précis | Exemples concrets, chiffres | SaaS B2B, Tech, Consulting |
| **Commercial** | Engageant, opportuniste, conversion | Call-to-action, urgence | Vente directe, Télévente |
| **Consultative** | Collaboratif, questionnant, analytique | Questions ouvertes, besoins | Conseil, Audit, Solutions |

### 2. Comment ça influence le Freestyle AI ?

La personnalité est **injectée dans le prompt system** Ollama :

```python
# Exemple: Personnalité "Professionnel"
system_prompt = f"""
Tu es Julie de GoldInvest.

TON ET STYLE:
- Ton: professionnel, courtois, posé, crédible
- Style: Phrases claires et structurées. Vouvoiement. Arguments factuels et chiffrés.

RÈGLES:
1. MAX 2-3 phrases (≤150 mots)
2. Réponds DIRECTEMENT à la question
3. Utilise des chiffres et faits (ex: "+110% depuis 2020")
4. Ramène vers l'objectif (prise de RDV)

QUESTION: {user_input}

Réponds maintenant:
"""
```

**Comparaison réponses selon personnalité** :

**Question prospect** : "Pourquoi investir maintenant ?"

**Professionnel** :
> "Le contexte est favorable : l'or a pris +110% depuis 2020 et les banques centrales accumulent. Avec l'inflation à 5%, l'or protège votre patrimoine. Nos clients diversifient avec 10-15% de leur épargne. Vous seriez disponible mardi pour en discuter ?"

**Doux** :
> "Je comprends votre questionnement. Beaucoup de nos clients se posaient la même question au début. L'or c'est rassurant : ça existe depuis 5000 ans, c'est tangible. Et aujourd'hui, avec l'inflation, c'est vraiment le bon moment pour protéger votre épargne. On pourrait en parler ensemble mardi ?"

**Assertif** :
> "Parce que l'or monte MAINTENANT. +110% depuis 2020. Chaque mois que vous attendez, c'est de l'argent perdu. Les smart money investissent déjà. Vous voulez être dans le bon wagon ou regarder le train partir ? Mardi 14h, ça vous va ?"

**Commercial** :
> "Excellente question ! L'or c'est MAINTENANT ou jamais : +110% depuis 2020, et les experts prévoient encore +20% cette année. Imaginez : 10000€ investis aujourd'hui = 12000€ dans 12 mois. MAIS attention, nos derniers lingots partent vite. Je vous bloque un créneau mardi 14h ?"

### 3. Choisir la Personnalité

**Mode interactif** :
```bash
python create_scenario.py --interactive
# → Étape 4: Choix personnalité (menu)
```

**Mode programmatique** :
```python
from create_scenario import ScenarioCreator

creator = ScenarioCreator()
creator.set_personality("professionnel")
creator.set_campaign_objective("appointment")
scenario = creator.build()
```

---

## 🎯 Objections et Matching

### 1. Base de Données Objections (NOUVEAU v3)

**153 objections** réparties sur **9 thématiques** :

| Thématique | Nb Objections | Exemples |
|------------|---------------|----------|
| Standard | 18 | "Pas le temps", "Pas intéressé", "Trop cher" |
| Finance/Banque | 15 | "J'ai déjà une banque", "Frais trop élevés" |
| Trading Crypto | 17 | "C'est risqué", "Je ne connais pas" |
| Énergie Renouvelable | 16 | "Travaux trop longs", "Rentabilité ?" |
| Immobilier | 15 | "Pas d'apport", "Marché instable" |
| Assurance | 17 | "Déjà assuré", "Loi Hamon résiliation" |
| SaaS B2B | 19 | "Déjà un outil", "Intégration compliquée" |
| **Or Investissement** | 16 | "C'est risqué", "Trop cher", "Où stocker ?" ← NOUVEAU
| **Vin Investissement** | 15 | "Je connais rien au vin", "Conservation ?" ← NOUVEAU

### 2. Système de Matching Fuzzy

**Algorithme hybride** :
- 70% similarité textuelle (SequenceMatcher)
- 30% chevauchement mots-clés

**Exemples de matching** :

```python
# Input prospect → Match trouvé (score)

"Désolé mais j'ai vraiment pas le temps là"
→ "Je n'ai pas le temps" (score: 0.54)

"Ça coûte combien votre truc ?"
→ "C'est trop cher" (score: 0.68)

"Je suis déjà client chez Boursorama"
→ "J'ai déjà une banque" (score: 0.61)

"L'or c'est trop risqué non ?"
→ "C'est risqué" (score: 0.72) ← Thématique Or

"Quel temps fait-il aujourd'hui ?"
→ Aucun match (score: 0.18 < 0.5)
→ Fallback Freestyle AI
```

### 3. Configuration Matching (.env)

```bash
# Score minimum pour considérer un match (0.0-1.0)
OBJECTION_MIN_SCORE=0.5

# Utiliser audio pré-enregistré si match trouvé
OBJECTION_USE_PRERECORDED=true

# Fallback vers Freestyle AI si pas de match
OBJECTION_FALLBACK_TO_FREESTYLE=true
```

**Ajustement seuil** :

| Seuil | Comportement | Cas d'usage |
|-------|-------------|-------------|
| 0.3-0.4 | Très permissif (beaucoup de matchs) | Phase test, validation base objections |
| **0.5** | **Équilibré (recommandé)** | **Production standard** |
| 0.6-0.7 | Strict (peu de matchs) | Haute précision requise |

### 4. Tester le Matching

```bash
# Test unitaire
python system/objection_matcher.py

# Output:
# 🧪 Test ObjectionMatcher - MiniBotPanel v3
#
# Test 1: Match exact
#   Input: 'Je n'ai pas le temps'
#   Match: Je n'ai pas le temps
#   Score: 1.00
#   ✅ PASS
#
# Test 2: Variante proche
#   Input: 'Désolé mais j'ai vraiment pas le temps là'
#   Match: Je n'ai pas le temps
#   Score: 0.54
#   ✅ PASS
#
# ...
```

**Test manuel** :
```python
from system.objections_database import ALL_OBJECTIONS
from system.objection_matcher import ObjectionMatcher

# Charger objections d'une thématique
matcher = ObjectionMatcher(ALL_OBJECTIONS["or"])

# Tester un input
result = matcher.find_best_match(
    "C'est pas un peu risqué l'or ?",
    min_score=0.5
)

if result:
    print(f"Match: {result['objection']}")
    print(f"Score: {result['score']}")
    print(f"Réponse: {result['response']}")
else:
    print("Pas de match → Freestyle AI")
```

---

## 🎙️ Clonage Vocal

### 1. Préparer Enregistrement

**Recommandations** :
- **Durée** : 10-15 secondes minimum
- **Format** : WAV 16-bit, 22050 Hz
- **Qualité** : Peu de bruit de fond
- **Contenu** : Phrases naturelles avec variation tonale

**Exemple texte** :
```
"Bonjour, je m'appelle Julie et je travaille pour GoldInvest.
Nous proposons des solutions innovantes pour protéger votre patrimoine.
N'hésitez pas à me contacter pour plus d'informations."
```

### 2. Cloner la Voix

```bash
python clone_voice.py voices/commercial.wav \
  --name "Voix Julie" \
  --description "Voix féminine professionnelle"

# Output:
# 🎙️ Processing: voices/commercial.wav
# ⏱️ Duration: 12.3s
# 🔊 Sample rate: 22050 Hz
# 🧠 Generating embeddings with Coqui XTTS...
# ✅ Voice cloned successfully!
# 📊 Voice ID: 1
```

### 3. Tester la Voix

```bash
python test_voice.py 1 \
  --text "Bonjour, ceci est un test de clonage vocal."

# ✅ Audio generated: audio/test_voice_1.wav
```

---

## 📞 Gestion des Campagnes

### 1. Lancer Campagne (Mode Interactif v3)

```bash
python launch_campaign.py --interactive
```

**Menu de sélection scénario** :

```
╔════════════════════════════════════════════════════════════════╗
║  📋 Scénarios disponibles (5 trouvés)                          ║
╚════════════════════════════════════════════════════════════════╝

1. Vente Or Investissement
   Prospection pour investissement en or physique
   📅 Objectif: appointment | 7 étapes

2. Test Démo Freestyle
   Scénario de test pour valider le mode Freestyle AI
   📅 Objectif: appointment | 9 étapes

3. Vin Grands Crus Bordeaux
   Prospection investissement vin (Château Margaux, Pétrus)
   📞 Objectif: lead_generation | 6 étapes

4. Trading Crypto BTC/ETH
   Prospection trading crypto avec accompagnement
   ☎️ Objectif: call_transfer | 8 étapes

5. Assurance Habitation
   Souscription assurance habitation
   📅 Objectif: appointment | 5 étapes

Choisissez un scénario [1-5] (ou 'q' pour annuler):
```

### 2. Créer Campagne (API)

```bash
curl -X POST "http://localhost:8000/api/campaigns?password=your_password" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Campagne Or Janvier 2025",
    "scenario_name": "scenario_or_investissement",
    "contacts": [
      {"phone": "+33612345678", "first_name": "Jean", "last_name": "Dupont"}
    ],
    "max_concurrent_calls": 5,
    "retry_enabled": true
  }'
```

### 3. Monitorer Campagne

```bash
python monitor_campaign.py --campaign-id 1 --refresh 5

# Interface:
# ╔══════════════════════════════════════════════════════════════╗
# ║    MiniBotPanel v3 - Campaign Monitor (ID: 1)                ║
# ║       Campagne Or Investissement Janvier 2025                ║
# ╚══════════════════════════════════════════════════════════════╝
#
# 📊 Status: RUNNING | Duration: 01:23:45 | Updated: 14:35:12
#
# ┌─ Progress ──────────────────────────────────────────────────┐
# │ [████████████████░░░░░░░░░░] 32/50 (64%)                    │
# └─────────────────────────────────────────────────────────────┘
#
# ┌─ Freestyle AI Stats (NOUVEAU v3) ───────────────────────────┐
# │ Total Freestyle turns: 47                                   │
# │ Objections matched: 18 (38%)                                │
# │ Freestyle generated: 29 (62%)                               │
# │ Avg response time: 1.2s                                     │
# └─────────────────────────────────────────────────────────────┘
#
# ┌─ Results ───────────────────────────────────────────────────┐
# │ QUALIFIED:        12 (38%) ████████                         │
# │ NOT_INTERESTED:   15 (47%) ██████████                       │
# │ NO_ANSWER:        3 (9%)   ██                               │
# │ ANSWERING_MACHINE: 2 (6%)  █                                │
# └─────────────────────────────────────────────────────────────┘
```

---

## 📊 Exports et Rapports

### 1. Export CSV

```bash
python export_campaign.py --campaign-id 1 --format csv

# Colonnes exportées:
# - call_id, contact_phone, contact_name
# - status, result, duration
# - freestyle_turns (NOUVEAU v3)
# - objections_matched (NOUVEAU v3)
# - started_at, ended_at
```

### 2. Export Excel

```bash
python export_campaign.py --campaign-id 1 --format excel

# Feuilles générées:
# - Summary: Stats globales + Freestyle AI metrics
# - Calls: Détail appels
# - Objections: Top objections rencontrées (NOUVEAU v3)
# - Freestyle: Analyse réponses générées (NOUVEAU v3)
```

---

## 🌐 API REST

### 1. Health Check v3

```bash
curl http://localhost:8000/health

# Response v3:
{
  "status": "healthy",
  "components": {
    "database": {"status": "healthy"},
    "freeswitch": {"status": "healthy"},
    "vosk": {"status": "healthy"},
    "ollama": {
      "status": "healthy",
      "model": "mistral:7b",
      "url": "http://localhost:11434"
    },
    "objection_matcher": {
      "status": "healthy",
      "total_objections": 153,
      "thematiques": 9
    }
  }
}
```

### 2. Créer Campagne avec Scénario

```bash
curl -X POST "http://localhost:8000/api/campaigns?password=your_password" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Campagne Or",
    "scenario_name": "scenario_or_investissement",
    "contacts": [{"phone": "+33612345678"}]
  }'
```

---

## 🔄 Workflows Complets

### Workflow: Campagne Or Investissement avec Freestyle AI

```bash
# 1. Préparer contacts prospects
cat > prospects_or.csv << EOF
phone,first_name,last_name,company,email
+33612345678,Jean,Dupont,Entreprise A,jean@example.com
+33698765432,Marie,Martin,Entreprise B,marie@example.com
EOF

# 2. Importer
python import_contacts.py prospects_or.csv
# ✅ Imported 2 contacts

# 3. Créer scénario Or (mode interactif)
python create_scenario.py --interactive
# → Thématique: Or Investissement
# → Objectif: Prise de RDV
# → Personnalité: Professionnel
# ✅ Scénario créé avec 16 objections Or chargées

# 4. Cloner voix (si pas déjà fait)
python clone_voice.py voices/julie_commercial.wav --name "Julie Pro"

# 5. Lancer campagne (mode interactif)
python launch_campaign.py --interactive
# → Sélectionner scénario Or
# ✅ Campaign launched: ID 1

# 6. Monitorer en temps réel
python monitor_campaign.py --campaign-id 1 --refresh 5
# → Voir Freestyle turns, objections matched, etc.

# 7. Exporter résultats
python export_campaign.py --campaign-id 1 --format excel
# ✅ Export: exports/campaign_1.xlsx
#    - Feuille "Freestyle": Analyse réponses AI
#    - Feuille "Objections": Top objections détectées
```

---

## 🐛 Troubleshooting

### Problème: Ollama not available

**Symptômes** :
```
ERROR: Ollama not available at http://localhost:11434
```

**Solutions** :
```bash
# 1. Vérifier Ollama installé
which ollama

# 2. Démarrer service
ollama serve &

# 3. Vérifier modèle
ollama list
# Si vide: ollama pull mistral:7b

# 4. Tester
curl http://localhost:11434/api/tags
```

### Problème: Objection Matcher ne trouve pas de match

**Symptômes** :
```
Tous les inputs → Freestyle AI (aucun match objections)
```

**Solutions** :
```bash
# 1. Baisser seuil dans .env
OBJECTION_MIN_SCORE=0.4  # Au lieu de 0.5

# 2. Vérifier thématique chargée
python -c "
from system.objections_database import ALL_OBJECTIONS
print(f'Thématiques: {list(ALL_OBJECTIONS.keys())}')
print(f'Objections Or: {len(ALL_OBJECTIONS[\"or\"])}')
"

# 3. Tester manuellement
python system/objection_matcher.py
```

### Problème: Freestyle répond lentement

**Symptômes** :
```
WARNING: Freestyle generation took 5.2s (>3s threshold)
```

**Solutions** :
```bash
# 1. Utiliser modèle plus rapide
ollama pull llama3.2:1b
# .env: OLLAMA_MODEL=llama3.2:1b

# 2. Réduire tokens
# .env: OLLAMA_MAX_TOKENS=80

# 3. Vérifier CPU/RAM
top
htop
```

---

## ❓ FAQ

### Q1: Comment choisir entre pré-enregistré et Freestyle ?

**R:** Le système décide automatiquement :
1. **Objection matching** (fuzzy) → Si score ≥ 0.5 → Audio pré-enregistré (~50ms)
2. **Pas de match** → Freestyle AI génère réponse (~1-2s)

### Q2: Peut-on désactiver Freestyle pour forcer pré-enregistré uniquement ?

**R:** Oui, dans `.env` :
```bash
OBJECTION_FALLBACK_TO_FREESTYLE=false
```

Si aucune objection ne match, le robot dira "Je n'ai pas compris, pouvez-vous répéter ?"

### Q3: Quelle personnalité choisir pour quel produit ?

**R:** Recommandations :

| Produit | Personnalité | Pourquoi |
|---------|--------------|----------|
| Finance, Immobilier, Or | Professionnel | Arguments factuels, crédibilité |
| Assurance Senior | Doux | Empathie, réassurance |
| Trading, Crypto | Assertif | Direct, challenges objections |
| SaaS B2B, Tech | Expert | Technique, pédagogue |
| Promo, Sport, Événement | Dynamique | Énergique, motivant |

### Q4: Combien d'objections sont pré-chargées pour chaque thématique ?

**R:** Total **153 objections** :
- Standard: 18
- Finance: 15
- Crypto: 17
- Énergie: 16
- Immobilier: 15
- Assurance: 17
- SaaS B2B: 19
- **Or: 16** ← NOUVEAU v3
- **Vin: 15** ← NOUVEAU v3

### Q5: Peut-on ajouter ses propres objections ?

**R:** Oui, éditer `system/objections_database.py` :
```python
OBJECTIONS_CUSTOM = {
    "Mon objection perso": "Ma réponse experte personnalisée",
    # ...
}

# Ajouter dans ALL_OBJECTIONS
ALL_OBJECTIONS["custom"] = OBJECTIONS_CUSTOM
```

### Q6: Quelle RAM minimum pour Freestyle AI ?

**R:** Dépend du modèle Ollama :
- **Mistral 7B** : 8 GB RAM minimum (recommandé: 12 GB)
- **Llama 3.2 3B** : 4 GB RAM minimum
- **Llama 3.2 1B** : 2 GB RAM minimum

### Q7: Comment analyser les réponses Freestyle générées ?

**R:** Export Excel :
```bash
python export_campaign.py --campaign-id 1 --format excel
```

Feuille "Freestyle" contient :
- Toutes les questions prospects
- Réponses générées par AI
- Temps de génération
- Score objection matching (si applicable)

---

## 📞 Support

Pour toute question :

1. **Documentation** :
   - `GUIDE_INSTALLATION.md` : Installation + Ollama
   - `BRIEF_PROJET.md` : Architecture v3
   - `FREESTYLE_MODE.md` : Guide complet Freestyle AI

2. **Health check** :
   ```bash
   curl http://localhost:8000/health
   ```

3. **Logs** :
   ```bash
   tail -f logs/system/minibot.log
   tail -f logs/freestyle/  # Logs Freestyle AI
   ```

---

## 🎯 Conclusion

MiniBotPanel v3 apporte des capacités d'IA conversationnelle avancées avec **Freestyle AI**, **objection matching** et **personnalités configurables**.

**Quick Start v3** :
```bash
# 1. Vérifier Ollama
ollama list  # Doit afficher mistral:7b

# 2. Créer scénario
python create_scenario.py --interactive

# 3. Lancer campagne
python launch_campaign.py --interactive

# 4. Monitorer
python monitor_campaign.py --campaign-id 1
```

**Bonne utilisation ! 🚀**

---

**Version du guide** : v3.0.0
**Dernière mise à jour** : 2025-01-29
