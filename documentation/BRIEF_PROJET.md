# MiniBotPanel v3 - Brief Projet

## 📋 Vue d'ensemble

**MiniBotPanel v3** est une plateforme avancée de robotisation d'appels téléphoniques conversationnels basée sur FreeSWITCH et l'intelligence artificielle. Le système permet de lancer des campagnes d'appels automatisées avec conversations naturelles en temps réel, détection de répondeur, analyse de sentiment et génération de réponses dynamiques **Freestyle AI** via Ollama.

### 🎯 Objectifs du projet

- **Automatisation intelligente** : Remplacer les opérateurs humains pour appels sortants massifs
- **Conversations naturelles** : IA conversationnelle avec Vosk STT, Ollama NLP et Coqui TTS
- **Freestyle AI** : Réponses dynamiques adaptatives sans script pré-défini
- **Matching objections** : Détection rapide et réponse instantanée aux objections communes
- **Scalabilité** : Gérer jusqu'à 10 appels simultanés avec queue management
- **Conformité légale** : Respect des horaires légaux français (Lun-Ven 10h-20h)
- **Monitoring temps réel** : Dashboard API REST + métriques Prometheus

### 🆕 Nouveautés v3

✅ **Freestyle AI** : Réponses générées dynamiquement par Ollama (Mistral 7B)
✅ **Objection Matching** : Détection fuzzy (153 objections pré-enregistrées)
✅ **7 Personnalités d'agent** : Professionnel, Doux, Dynamique, Assertif, Expert, Commercial, Consultative
✅ **9 Thématiques métier** : Standard, Finance, Crypto, Énergie, Immobilier, Assurance, SaaS B2B, Or, Vin
✅ **3 Objectifs de campagne** : Prise de RDV, Génération de lead, Transfert d'appel
✅ **Scenarios Manager** : Gestion centralisée dans `scenarios/` avec sélection interactive

---

## 🏗️ Architecture Système

```
┌─────────────────────────────────────────────────────────────────┐
│                    MINIBOT PANEL v3                              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 │               │               │
        ┌────────▼────────┐ ┌───▼────┐ ┌────────▼────────┐
        │   FastAPI REST  │ │  CLI   │ │  WebSocket ASR  │
        │   API (8000)    │ │ Tools  │ │   Server (8080) │
        └────────┬────────┘ └───┬────┘ └────────┬────────┘
                 │               │               │
                 └───────────────┼───────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Campaign Manager       │
                    │  - Queue Management     │
                    │  - Retry Logic          │
                    │  - Legal Hours Check    │
                    │  - Scenario Loader      │ ← NOUVEAU v3
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Robot FreeSWITCH       │
                    │  - ESL Control (8021)   │
                    │  - Call Orchestration   │
                    │  - Thread-per-call      │
                    │  - Freestyle Handler    │ ← NOUVEAU v3
                    │  - Objection Matcher    │ ← NOUVEAU v3
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────▼────────┐  ┌───────────▼────────┐  ┌───────────▼────────┐
│  FreeSWITCH    │  │   AI Services      │  │   PostgreSQL DB    │
│  - SIP Gateway │  │   - Vosk STT       │  │   - Campaigns      │
│  - Dialplan    │  │   - Ollama NLP     │  │   - Contacts       │
│  - RTP Streams │  │   - Coqui TTS      │  │   - Calls          │
└────────────────┘  │   - AMD Dual Layer │  │   - CallEvents     │
                    │   - WebRTC VAD     │  └────────────────────┘
                    │   - Ollama 11434   │ ← NOUVEAU v3
                    └────────────────────┘
```

### 🔄 Flux d'appel complet (avec Freestyle AI)

```
1. [API/CLI] → Créer campagne + Import contacts
2. [CampaignManager] → Démarrage campagne → Chargement queue + scénario
3. [BatchCaller] → Récupération batch (5 appels) → Vérif horaires légaux
4. [RobotFreeSWITCH] → Originate call via ESL → FreeSWITCH dial
5. [FreeSWITCH] → RINGING → ANSWER
6. [AMD Dual Layer] → Détection répondeur (FreeSWITCH + Python Vosk)
   ├─ Si répondeur → Hangup + status=ANSWERING_MACHINE
   └─ Si humain → Continue
7. [StreamingASR] → WebSocket connection établie (RTP stream)
8. [Conversation Loop avec Freestyle AI] ← NOUVEAU v3
   ├─ Robot: Play audio TTS (message scénario)
   ├─ StreamingASR: Transcription temps réel (Vosk)
   ├─ Ollama NLP: Analyse intent + sentiment
   ├─ Decision:
   │   ├─ Intent "positive" → Transition scénario
   │   ├─ Intent "negative" → End call
   │   ├─ Intent "question" →
   │   │   ├─ 1. ObjectionMatcher fuzzy matching (score > 0.5)
   │   │   ├─ 2a. Si match trouvé → Play audio pré-enregistré (~50ms) ← NOUVEAU v3
   │   │   └─ 2b. Si pas de match → Freestyle AI (génération Ollama ~1-2s) ← NOUVEAU v3
   │   └─ Intent "objection" → Play audio objection
   └─ Loop jusqu'à fin scénario ou hangup (max_turns configurable)
9. [Call End] → Save recording + transcription + stats → Update DB
10. [Retry Logic] → Si NO_ANSWER/BUSY → Re-queue avec délai
```

---

## 🚀 Fonctionnalités Principales

### 1. 🎙️ **IA Conversationnelle Complète**

| Composant | Technologie | Fonction |
|-----------|-------------|----------|
| **STT** | Vosk (vosk-model-small-fr-0.22) | Transcription audio → texte en temps réel |
| **NLP** | Ollama (mistral:7b ou llama3.2:1b/3b) | Analyse intent + sentiment des réponses |
| **TTS** | Coqui XTTS v2 | Synthèse vocale avec clonage de voix |
| **AMD** | Dual Layer (FreeSWITCH + Vosk) | Détection répondeur (16 patterns français) |
| **VAD** | WebRTC VAD | Détection de parole dans flux RTP |
| **Freestyle** | Ollama Mistral 7B | Génération réponses dynamiques ← NOUVEAU v3 |
| **Objections** | ObjectionMatcher (fuzzy) | Matching rapide 153 objections ← NOUVEAU v3 |

**Exemple de conversation avec Freestyle AI** :
```
Robot: "Bonjour, je vous appelle concernant notre solution d'investissement en or..."
User: "L'or, c'est pas trop risqué ça ?"

  ↓ Objection Matching (fuzzy score)
  ✅ Match trouvé: "C'est risqué" (score: 0.72)
  → Play audio pré-enregistré (50ms latency)

Robot: "Risqué ? L'or existe depuis 5000 ans et n'a JAMAIS valu zéro !
        En fait, c'est l'inverse : l'or protège de l'inflation..."

User: "Oui mais bon, avec les cryptos maintenant..."

  ↓ Objection Matching (fuzzy score)
  ❌ Pas de match (meilleur score: 0.42 < 0.5)
  → Freestyle AI (Ollama génération 1.5s)

Robot: "Les cryptos sont volatiles, +50% un jour, -40% le lendemain.
        L'or, lui, a pris +110% depuis 2020 de façon stable.
        Et surtout, l'or est tangible - vous pouvez le tenir dans vos mains."

User: "Ah d'accord, et combien il faut investir minimum ?"

  ↓ Freestyle AI (question ouverte)

Robot: "Vous pouvez commencer dès 1000€. Nos clients investissent en moyenne
        entre 5000€ et 15000€ pour bien diversifier. Vous préférez quel montant ?"
```

### 2. 📞 **Gestion Campagnes Avancée**

- **Import contacts** : CSV, Excel, JSON (validation phone numbers)
- **Scénarios JSON** : Machine à états avec transitions intent-based
- **Sélection scénario interactive** : Menu coloré avec emojis ← NOUVEAU v3
- **Clonage vocal** : TTS avec voix personnalisée (fichier référence 10-15s)
- **Queue management** : Batch processing (5 appels/batch par défaut)
- **Retry automatique** :
  - NO_ANSWER → Retry après 30 min (max 2 fois)
  - BUSY → Retry après 5 min (max 2 fois)
- **Horaires légaux** : Lun-Ven 10h-20h, Sam 10h-13h (configurable)
- **Limites concurrence** : Max 10 appels simultanés (configurable)

### 3. 🔍 **AMD Dual Layer (Détection Répondeur)**

**Layer 1 - FreeSWITCH** (rapide, 5 secondes) :
```xml
<action application="amd" data="5000"/>
```

**Layer 2 - Python Vosk** (précis, analyse transcription) :
```python
AMD_MACHINE_KEYWORDS = [
    "bonjour vous êtes bien",
    "laissez un message",
    "veuillez laisser",
    "vous êtes sur la messagerie",
    "en ce moment je ne peux pas",
    "rappeler plus tard",
    "bienvenue sur la boite vocale",
    "après le bip sonore",
    "actuellement indisponible",
    "merci de votre appel",
    "nous ne sommes pas disponibles",
    "contactez nous par email",
    "notre standard est fermé",
    "vous pouvez nous joindre",
    "réessayer ultérieurement",
    "horaires d'ouverture"
]
```

**Logique décision** :
```python
if freeswitch_amd == "MACHINE" and (
    any(keyword in transcription for keyword in AMD_MACHINE_KEYWORDS) or
    speech_duration > 3.0 seconds
):
    → Hangup + status=ANSWERING_MACHINE
else:
    → Continue call (humain détecté)
```

### 4. 🎯 **IA Freestyle (Réponses Dynamiques) - NOUVEAU v3**

**Problème résolu** : Questions hors-script du prospect nécessitant réponses personnalisées

**Architecture** :
```python
class RobotFreeSWITCH:
    def _handle_freestyle_step(self, call_uuid, step_config):
        # 1. Vérifier limite tours Freestyle
        if self.freestyle_turns >= step_config.get("max_turns", 3):
            return self._fallback_to_script(call_uuid)

        # 2. Récupérer input utilisateur (StreamingASR)
        user_input = self.get_user_input(call_uuid, timeout=10)

        # 3. Essayer Objection Matching d'abord (rapide ~50ms)
        match = self.objection_matcher.find_best_match(
            user_input,
            min_score=0.5
        )

        if match and match["score"] >= 0.7:
            # 3a. Match fort → Audio pré-enregistré
            audio_path = self._generate_prerecorded_audio(match["response"])
            self.play_audio(call_uuid, audio_path)
            logger.info(f"Objection matched: {match['objection']} (score: {match['score']})")
        else:
            # 3b. Pas de match → Freestyle AI
            response = self._generate_freestyle_response(
                user_input=user_input,
                context=step_config.get("context", {}),
                conversation_history=self.get_conversation_history(call_uuid, limit=5)
            )

            audio_path = self.tts_service.synthesize(response)
            self.play_audio(call_uuid, audio_path)
            logger.info(f"Freestyle AI response generated ({len(response)} chars)")

        # 4. Incrémenter compteur tours
        self.freestyle_turns += 1

        # 5. Analyser intent de la nouvelle réponse
        next_intent = self.nlp_service.detect_intent(user_input)

        # 6. Transition basée sur intent_mapping
        return self._transition_to_step(call_uuid, next_intent, step_config["intent_mapping"])
```

**Système de Prompt Engineering** :
```python
def _build_freestyle_prompt(self, user_input, context, history):
    system_prompt = f"""
Tu es {context.get("agent_name", "un assistant")} de {context.get("company", "l'entreprise")}.

CONTEXTE CAMPAGNE:
{context.get("campaign_context", "Prospection commerciale")}

OBJECTIF:
{context.get("campaign_objective", "Qualifier le prospect")}

TON ET STYLE:
- Ton: {context.get("agent_tone", "professionnel et courtois")}
- Style: {context.get("agent_style", "Phrases courtes et claires. Vouvoiement.")}

RÈGLES STRICTES:
1. MAX 2-3 phrases (≤150 mots)
2. Réponds DIRECTEMENT à la question posée
3. Utilise des arguments factuels et chiffrés quand possible
4. Ramène TOUJOURS vers l'objectif de campagne
5. Reste naturel, ne sonne pas comme un robot
6. Utilise "vous" (vouvoiement)
7. NE PAS répéter les 5 derniers échanges

HISTORIQUE CONVERSATION:
{self._format_history(history)}

QUESTION ACTUELLE:
{user_input}

Réponds maintenant (MAX 150 mots):
"""

    return system_prompt
```

**Avantages** :
- ✅ Réponses contextuelles intelligentes adaptées au produit/service
- ✅ Fallback rapide vers audio pré-enregistré (objections communes)
- ✅ Limite 150 mots pour conversations naturelles
- ✅ Historique conversationnel (contexte des 5 derniers échanges)
- ✅ Personnalisation via 7 personnalités d'agent
- ✅ Objectif de campagne intégré au prompt

### 5. 🎯 **Objection Matching (Fuzzy) - NOUVEAU v3**

**Problème** : Détecter rapidement les objections même si formulées différemment

**Solution** : Système de matching hybride (70% similarité textuelle + 30% mots-clés)

**Architecture** (`system/objection_matcher.py`) :
```python
class ObjectionMatcher:
    def __init__(self, objections_dict: Dict[str, str]):
        self.objections = objections_dict  # {objection: response}
        self.keywords_map = {}  # Pré-calculé à l'init

        # Pré-calculer mots-clés pour chaque objection
        for objection in objections_dict.keys():
            self.keywords_map[objection] = self._extract_keywords(objection)

    def _extract_keywords(self, text: str) -> List[str]:
        """Extrait mots-clés significatifs (retire stopwords français)"""
        stopwords = {
            'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du',
            'je', 'tu', 'il', 'que', 'qui', 'et', 'ou', 'mais', ...
        }
        words = re.findall(r'\b[a-zàâäéèêëïîôùûüÿçæœ]{3,}\b', text.lower())
        return [w for w in words if w not in stopwords]

    def _hybrid_score(self, input_text: str, objection_text: str) -> float:
        """Score hybride: 70% similarité + 30% mots-clés"""
        # Similarité textuelle (SequenceMatcher)
        text_similarity = SequenceMatcher(
            None,
            input_text.lower(),
            objection_text.lower()
        ).ratio()

        # Chevauchement mots-clés
        input_keywords = self._extract_keywords(input_text)
        objection_keywords = self.keywords_map[objection_text]

        common = set(input_keywords) & set(objection_keywords)
        max_len = max(len(input_keywords), len(objection_keywords))
        keyword_overlap = len(common) / max_len if max_len > 0 else 0.0

        # Pondération finale
        return (0.7 * text_similarity) + (0.3 * keyword_overlap)

    def find_best_match(self, user_input: str, min_score: float = 0.5):
        """Trouve meilleure objection correspondante"""
        scores = [
            (objection, self._hybrid_score(user_input, objection))
            for objection in self.objections.keys()
        ]
        scores.sort(key=lambda x: x[1], reverse=True)

        best_objection, best_score = scores[0]

        if best_score >= min_score:
            return {
                "objection": best_objection,
                "response": self.objections[best_objection],
                "score": best_score,
                "confidence": "high" if best_score >= 0.8 else "medium"
            }
        return None
```

**Exemples de matching** :
```python
# Input: "Désolé mais j'ai vraiment pas le temps là"
# → Match: "Je n'ai pas le temps" (score: 0.54)

# Input: "Ça coûte combien votre truc ?"
# → Match: "C'est trop cher" (score: 0.68)

# Input: "Je suis déjà client chez un concurrent"
# → Match: "J'ai déjà une banque" (score: 0.61)
```

**Base de données objections** (`system/objections_database.py`) :
- **9 thématiques** : Standard, Finance, Crypto, Énergie, Immobilier, Assurance, SaaS B2B, Or, Vin
- **153 objections totales** avec réponses professionnelles
- **Format** : `{"objection": "réponse expert"}`

**Performance** :
- Matching : ~10-20ms pour 153 objections
- Précision : ~85% de détection sur variantes proches
- Fallback : Si score < 0.5 → Freestyle AI

### 6. 🎭 **Personnalités d'Agent - NOUVEAU v3**

7 profils de personnalité configurables pour influencer le ton et style du Freestyle AI :

| Personnalité | Ton | Style | Cas d'usage |
|--------------|-----|-------|-------------|
| **Professionnel** | Neutre, courtois, expert | Phrases structurées, vouvoiement, arguments factuels | B2B, Finance, Immobilier |
| **Doux** | Chaleureux, empathique, rassurant | Écoute active, reformulation, ton apaisant | Senior, Assurance, Santé |
| **Dynamique** | Énergique, enthousiaste, motivant | Rythme rapide, exclamations, storytelling | B2C, Sport, Événementiel |
| **Assertif** | Direct, confiant, persuasif | Affirmations claires, challenges objections | Trading, Crypto, Coaching |
| **Expert** | Technique, pédagogue, précis | Exemples concrets, chiffres, comparaisons | SaaS B2B, Tech, Consulting |
| **Commercial** | Engageant, opportuniste, focalisé conversion | Call-to-action fréquents, urgence, bénéfices | Vente directe, Télévente |
| **Consultative** | Collaboratif, questionnant, analytique | Questions ouvertes, reformulation besoins | Conseil, Audit, Solutions |

**Implémentation** :
```python
# Dans create_scenario.py
AGENT_PERSONALITIES = {
    "professionnel": {
        "tone": "professionnel, courtois, posé, crédible",
        "style": "Phrases claires et structurées. Vouvoiement. Arguments factuels et chiffrés.",
        "example": "Je comprends votre questionnement. Nos solutions ont fait leurs preuves auprès de 500+ clients."
    },
    "doux": {
        "tone": "chaleureux, bienveillant, empathique, rassurant",
        "style": "Écoute active. Reformulation. Ton apaisant. Vouvoiement.",
        "example": "Je vous comprends tout à fait. Beaucoup de nos clients avaient les mêmes hésitations au début..."
    },
    # ... 5 autres personnalités
}

# Injection dans contexte Freestyle
freestyle_context = {
    "agent_tone": AGENT_PERSONALITIES[personality]["tone"],
    "agent_style": AGENT_PERSONALITIES[personality]["style"],
    # ...
}
```

### 7. 🎯 **Objectifs de Campagne - NOUVEAU v3**

3 objectifs configurables qui influencent le comportement du Freestyle AI :

| Objectif | Description | Prompt System Adjustment |
|----------|-------------|--------------------------|
| **Prise de RDV** | Fixer rendez-vous avec expert/commercial | "L'objectif est d'obtenir un rendez-vous. Propose des créneaux concrets." |
| **Génération de lead** | Qualifier prospect pour rappel conseiller | "L'objectif est de qualifier le prospect pour un rappel par un conseiller." |
| **Transfert d'appel** | Transfert immédiat si intéressé | "L'objectif est de transférer l'appel immédiatement si le prospect est intéressé." |

**Implémentation dans scénario** :
```json
{
  "name": "Prise de RDV Investissement Or",
  "campaign_objective": "appointment",
  "steps": {
    "freestyle_answer": {
      "audio_type": "freestyle",
      "context": {
        "campaign_objective": "L'objectif est d'obtenir un rendez-vous avec un expert pour discuter de l'investissement en or. Propose des créneaux cette semaine ou la suivante."
      }
    }
  }
}
```

### 8. 📡 **Streaming ASR (Real-time Transcription)**

**Architecture WebSocket** :
```
FreeSWITCH RTP → [WebSocket Server :8080] → Vosk → Transcription
```

**Implémentation** :
```python
# WebSocket server (asyncio)
async def handle_websocket(websocket, path):
    call_uuid = extract_uuid_from_path(path)

    # Init Vosk recognizer
    recognizer = vosk.KaldiRecognizer(model, 16000)

    # VAD init (WebRTC)
    vad = webrtcvad.Vad(mode=3)  # Aggressive mode

    async for audio_chunk in websocket:
        # VAD check
        if vad.is_speech(audio_chunk, 16000):
            # Feed to Vosk
            if recognizer.AcceptWaveform(audio_chunk):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")

                # Broadcast transcription
                broadcast_transcription(call_uuid, text)
```

**Features** :
- **Real-time** : Latence < 500ms
- **WebRTC VAD** : Filtre silences et bruits
- **Vosk streaming** : Transcription incrémentale
- **Automatic reconnect** : Si WebSocket déconnecté

### 9. 📊 **API REST Complete (FastAPI)**

**Base URL** : `http://localhost:8000`

**Authentication** : Simple password
```bash
# Méthode 1: Header
curl -H "X-API-Key: your_password" http://localhost:8000/api/campaigns

# Méthode 2: Query param
curl http://localhost:8000/api/campaigns?password=your_password
```

**Endpoints principaux** :

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Infos système + uptime |
| `/health` | GET | Health check (DB, FreeSWITCH, IA, Ollama) ← NOUVEAU v3 |
| `/metrics` | GET | Métriques Prometheus |
| `/api/campaigns` | GET | Liste campagnes |
| `/api/campaigns` | POST | Créer campagne (avec scenario_name) ← NOUVEAU v3 |
| `/api/campaigns/{id}/start` | POST | Démarrer campagne |
| `/api/campaigns/{id}/stop` | POST | Arrêter campagne |
| `/api/campaigns/{id}/stats` | GET | Stats détaillées |
| `/api/stats/system` | GET | Stats globales système |
| `/api/exports/{id}/csv` | GET | Export CSV campagne |
| `/api/exports/{id}/excel` | GET | Export Excel campagne |

**Exemple création campagne avec scénario** :
```bash
curl -X POST "http://localhost:8000/api/campaigns?password=your_password" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Campagne Investissement Or",
    "scenario_name": "scenario_or_investissement",
    "contacts": [
      {"phone": "+33612345678", "first_name": "Jean", "last_name": "Dupont"}
    ],
    "max_concurrent_calls": 5,
    "retry_enabled": true
  }'
```

### 10. 🛠️ **Outils CLI**

| Script | Usage | Description |
|--------|-------|-------------|
| `import_contacts.py` | `python import_contacts.py contacts.csv` | Import CSV/Excel vers DB |
| `create_scenario.py` | `python create_scenario.py --interactive` | Assistant création scénario JSON ← AMÉLIORÉ v3 |
| `clone_voice.py` | `python clone_voice.py voice.wav` | Clonage vocal (XTTS embeddings) |
| `launch_campaign.py` | `python launch_campaign.py --interactive` | Lancer campagne avec menu ← AMÉLIORÉ v3 |
| `monitor_campaign.py` | `python monitor_campaign.py --campaign-id 1` | Monitoring temps réel |
| `export_campaign.py` | `python export_campaign.py --campaign-id 1 --format excel` | Export résultats |

**NOUVEAU v3 - Création scénario interactive** :
```bash
python create_scenario.py --interactive

# Workflow:
# 1. Nom du scénario
# 2. Choix thématique (Standard/Finance/Crypto/Or/Vin...)
# 3. Choix objectif (RDV/Lead/Transfert)
# 4. Choix personnalité (Professionnel/Doux/Dynamique...)
# 5. Configuration étapes (avec Freestyle AI support)
# → Génère scenarios/scenario_*.json
```

**NOUVEAU v3 - Lancement campagne interactive** :
```bash
python launch_campaign.py --interactive

# Menu coloré avec emojis:
# ╔════════════════════════════════════════╗
# ║  📋 Scénarios disponibles (5 trouvés)  ║
# ╚════════════════════════════════════════╝
#
# 1. Prise de RDV Investissement Or
#    📅 Objectif: appointment | 7 étapes
#
# 2. Génération Lead Crypto Trading
#    📞 Objectif: lead_generation | 5 étapes
# ...
# Choisissez un scénario [1-5]:
```

### 11. 💾 **Base de Données (PostgreSQL)**

**Schéma** :
```sql
-- Contacts (prospects à appeler)
CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    company VARCHAR(255),
    tags TEXT[],
    blacklist BOOLEAN DEFAULT FALSE,
    opt_out BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Campagnes
CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    scenario VARCHAR(255),  -- ← NOUVEAU v3: scenario filename
    voice_id INTEGER REFERENCES voices(id),
    status VARCHAR(20) DEFAULT 'DRAFT',
    max_concurrent_calls INTEGER DEFAULT 10,
    retry_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Appels (un appel = une tentative)
CREATE TABLE calls (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    contact_id INTEGER REFERENCES contacts(id),
    call_uuid VARCHAR(100) UNIQUE,
    status VARCHAR(20) DEFAULT 'PENDING',
    result VARCHAR(30),
    direction VARCHAR(20) DEFAULT 'OUTBOUND',
    duration INTEGER,
    recording_path TEXT,
    transcription_path TEXT,
    freestyle_turns INTEGER DEFAULT 0,  -- ← NOUVEAU v3
    objections_matched JSONB,  -- ← NOUVEAU v3: [{objection, score, timestamp}]
    started_at TIMESTAMP,
    answered_at TIMESTAMP,
    ended_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    notes TEXT
);

-- Événements d'appel (logs détaillés)
CREATE TABLE call_events (
    id SERIAL PRIMARY KEY,
    call_id INTEGER REFERENCES calls(id),
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

**Statuts campagne** :
- `DRAFT` : Brouillon
- `READY` : Prête à démarrer
- `RUNNING` : En cours
- `PAUSED` : En pause
- `COMPLETED` : Terminée
- `CANCELLED` : Annulée

**Statuts appel** :
- `PENDING` : En attente
- `CALLING` : Numérotation en cours
- `RINGING` : Sonnerie
- `IN_PROGRESS` : Conversation en cours
- `COMPLETED` : Terminé
- `FAILED` : Échec
- `NO_ANSWER` : Pas de réponse
- `BUSY` : Occupé
- `ANSWERING_MACHINE` : Répondeur détecté
- `CANCELLED` : Annulé

**Résultats appel** :
- `QUALIFIED` : Contact qualifié (intéressé)
- `NOT_INTERESTED` : Pas intéressé
- `NOT_QUALIFIED` : Non qualifié
- `CALLBACK_REQUESTED` : Rappel demandé
- `APPOINTMENT_SCHEDULED` : RDV fixé
- `TECHNICAL_ERROR` : Erreur technique

---

## 🔧 Stack Technique

### Backend
- **Python 3.11+** : Langage principal (3.11 recommandé)
- **FastAPI 0.109** : Framework API REST asynchrone
- **SQLAlchemy 2.0** : ORM base de données
- **PostgreSQL 14+** : Base de données relationnelle
- **FreeSWITCH 1.10+** : Serveur téléphonie VoIP
- **python-esl** : Client ESL Python pour FreeSWITCH

### Intelligence Artificielle
- **Vosk 0.3.45** : Speech-to-Text (STT) offline
- **Ollama** : NLP (LLM local - Mistral 7B / Llama 3.2) ← NOUVEAU v3
- **Coqui TTS 0.22** : Text-to-Speech avec clonage vocal
- **WebRTC VAD 2.0** : Voice Activity Detection
- **librosa 0.10** : Analyse audio
- **difflib** : Fuzzy matching objections ← NOUVEAU v3

### Communication
- **WebSocket** : Streaming audio temps réel
- **asyncio** : Programmation asynchrone
- **threading** : Architecture thread-per-call

### Monitoring & Logging
- **prometheus-client** : Métriques Prometheus
- **python-json-logger** : Logs structurés JSON
- **colorama** : Logs colorés CLI

### Utilities
- **phonenumbers** : Validation numéros téléphone
- **openpyxl** : Import/Export Excel
- **python-dotenv** : Gestion variables environnement
- **click** : CLI framework

---

## 📁 Structure Projet

```
fs_minibot_streaming/
│
├── system/                          # Core système
│   ├── __init__.py
│   ├── config.py                    # Configuration centralisée
│   ├── database.py                  # SQLAlchemy engine + session
│   ├── models.py                    # ORM models (Contact, Campaign, Call)
│   ├── robot_freeswitch.py          # Robot appels (core) ← AMÉLIORÉ v3
│   ├── campaign_manager.py          # Gestion campagnes ← AMÉLIORÉ v3
│   ├── batch_caller.py              # Batch processing appels
│   ├── objections_database.py       # 153 objections (9 thématiques) ← NOUVEAU v3
│   ├── objection_matcher.py         # Fuzzy matching objections ← NOUVEAU v3
│   │
│   ├── services/                    # Services IA
│   │   ├── __init__.py
│   │   ├── vosk_stt.py              # Speech-to-Text (Vosk)
│   │   ├── ollama_nlp.py            # NLP Intent + Sentiment (Ollama) ← AMÉLIORÉ v3
│   │   ├── coqui_tts.py             # Text-to-Speech (Coqui)
│   │   ├── amd_detector.py          # AMD Dual Layer
│   │   └── streaming_asr.py         # WebSocket ASR server
│   │
│   └── api/                         # API REST
│       ├── __init__.py
│       ├── main.py                  # FastAPI app + middlewares
│       ├── campaigns.py             # Endpoints campagnes ← AMÉLIORÉ v3
│       ├── stats.py                 # Endpoints statistiques
│       └── exports.py               # Endpoints exports

├── scenarios/                       # Scénarios JSON ← NOUVEAU v3
│   ├── README.md                    # Guide scénarios
│   ├── scenario_test_demo.json      # Scénario de test Freestyle
│   ├── scenario_or_investissement.json
│   ├── scenario_vin_investissement.json
│   └── scenario_*.json

├── scripts/                         # Scripts CLI
│   ├── import_contacts.py           # Import CSV/Excel
│   ├── create_scenario.py           # Assistant création scénario ← AMÉLIORÉ v3
│   ├── clone_voice.py               # Clonage vocal
│   ├── launch_campaign.py           # Lancer campagne ← AMÉLIORÉ v3
│   ├── monitor_campaign.py          # Monitoring temps réel
│   └── export_campaign.py           # Export résultats

├── freeswitch/                      # Configuration FreeSWITCH
│   ├── dialplan/
│   │   └── minibot_outbound.xml     # Dialplan appels sortants
│   ├── autoload_configs/
│   │   └── event_socket.conf.xml    # Config ESL
│   └── sip_profiles/
│       └── external.xml              # Profil SIP (provider)

├── voices/                          # Fichiers clonage vocal
│   ├── voice1.wav
│   └── voice2.wav

├── audio/                           # Fichiers audio TTS générés
├── recordings/                      # Enregistrements appels
├── transcriptions/                  # Transcriptions texte
├── exports/                         # Exports CSV/Excel
├── logs/                            # Logs système
│   ├── system/
│   ├── campaigns/
│   ├── calls/
│   ├── services/
│   └── freestyle/                   # ← NOUVEAU v3
├── models/                          # Modèles IA (Vosk, Coqui cache)
│
├── documentation/                   # Documentation
│   ├── GUIDE_INSTALLATION.md        # Guide installation ← MIS À JOUR v3
│   ├── BRIEF_PROJET.md              # Ce fichier ← MIS À JOUR v3
│   ├── GUIDE_UTILISATION.md         # Guide utilisation
│   └── FREESTYLE_MODE.md            # Guide Freestyle AI ← NOUVEAU v3
│
├── requirements.txt                 # Dépendances Python ← MIS À JOUR v3
├── .env.example                     # Template configuration ← MIS À JOUR v3
├── .env                             # Configuration (git ignored)
├── .gitignore
└── README.md                        # ← MIS À JOUR v3
```

---

## 🔐 Sécurité & Authentification

### Protection API Simple

**Méthode** : Mot de passe unique dans `.env`

**Configuration** :
```bash
# .env
API_PASSWORD=your_secure_password_here
```

**Utilisation** :
```bash
# Méthode 1: Header (recommandé)
curl -H "X-API-Key: your_secure_password_here" http://localhost:8000/api/campaigns

# Méthode 2: Query parameter
curl "http://localhost:8000/api/campaigns?password=your_secure_password_here"
```

**Chemins publics** (pas de mot de passe requis) :
- `/` : Infos système
- `/health` : Health check
- `/metrics` : Métriques Prometheus
- `/docs` : Documentation Swagger
- `/redoc` : Documentation ReDoc

**Tous les autres endpoints** (`/api/*`) nécessitent le mot de passe.

### Recommandations Production

1. **Changez le mot de passe par défaut** :
```bash
API_PASSWORD=votre_mot_de_passe_tres_complexe_et_long_min_32_caracteres
```

2. **Utilisez HTTPS** (reverse proxy nginx/Caddy) :
```nginx
server {
    listen 443 ssl http2;
    server_name api.votredomaine.com;

    ssl_certificate /etc/letsencrypt/live/api.votredomaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.votredomaine.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. **Filtrage IP** (firewall) :
```bash
# UFW (Ubuntu)
sudo ufw allow from 192.168.1.0/24 to any port 8000
sudo ufw deny 8000
```

4. **Rate limiting** (nginx) :
```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

location /api/ {
    limit_req zone=api burst=20 nodelay;
    proxy_pass http://localhost:8000;
}
```

---

## 📈 Métriques & Monitoring

### Endpoint `/health` ← AMÉLIORÉ v3

**Composants vérifiés** :
- PostgreSQL (connection test)
- FreeSWITCH (ESL connection)
- Vosk STT (model loaded)
- **Ollama NLP** (service available) ← NOUVEAU v3
- **Objection Matcher** (loaded objections count) ← NOUVEAU v3

**Réponse exemple** :
```json
{
  "status": "healthy",
  "timestamp": "2025-01-29T10:30:00Z",
  "components": {
    "database": {"status": "healthy"},
    "freeswitch": {"status": "healthy", "esl_port": 8021},
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

### Endpoint `/metrics` (Prometheus)

**Métriques exposées** :
```prometheus
# Campagnes actives
minibot_campaigns_active 3

# Appels actifs (en cours)
minibot_calls_active 7

# Total appels complétés
minibot_calls_completed_total 1523

# Freestyle AI turns total ← NOUVEAU v3
minibot_freestyle_turns_total 342

# Objections matched total ← NOUVEAU v3
minibot_objections_matched_total 127

# Uptime (secondes)
minibot_uptime_seconds 3600
```

---

## 🚦 Conformité Légale (France)

### Horaires Légaux d'Appel

**Configuration** (`system/config.py`) :
```python
LEGAL_HOURS = {
    "weekdays": [(10, 13), (14, 20)],  # Lundi-Vendredi
    "saturday": [(10, 13)],             # Samedi
    "sunday": []                        # Dimanche interdit
}
```

**Validation automatique** :
- Vérification avant chaque appel dans `campaign_manager.py`
- Appels hors horaires → Status `PENDING` (re-schedulé)
- Timezone : Europe/Paris (configurable)

### Opt-out & Blacklist

**Contact.opt_out** : Contact ayant demandé à ne plus être appelé
**Contact.blacklist** : Contact blacklisté manuellement

**Gestion** :
```python
# Dans campaign_manager.py
if contact.blacklist or contact.opt_out:
    call.status = CallStatus.CANCELLED
    call.result = CallResult.NOT_QUALIFIED
    call.notes = "Contact in blocklist"
    # → Pas d'appel effectué
```

### Enregistrement Appels

**Légalité** : Information préalable obligatoire (message d'accueil)

**Implémentation** :
```json
// Dans scénario JSON
{
  "id": "intro",
  "type": "message",
  "text": "Bonjour, cet appel est enregistré à des fins de formation. [...]",
  "audio_file": "intro_recorded.wav"
}
```

**Stockage** :
- Enregistrements : `recordings/campaign_{id}/call_{uuid}.wav`
- Transcriptions : `transcriptions/campaign_{id}/call_{uuid}.txt`
- Durée conservation : 30 jours (configurable)

---

## 🐛 Limitations & Améliorations Futures

### Limitations Actuelles

1. **Scalabilité** :
   - Architecture thread-per-call (limite ~10-20 appels simultanés)
   - Pour 100+ appels : nécessite architecture asynchrone ou multi-processus

2. **IA Freestyle** :
   - Réponses limitées à 150 mots (peut être trop court pour questions complexes)
   - Latence 1-2s pour génération Ollama (vs 50ms audio pré-enregistré)
   - Pas de cache sémantique (uniquement hash MD5)

3. **Objection Matching** :
   - Précision ~85% sur variantes proches
   - Limité au français (pas de support multilingue)
   - Seuil fixe 0.5 (pas d'auto-tuning)

4. **AMD** :
   - Détection répondeur ~85-90% précision (patterns français uniquement)
   - Pas de support multilingue

5. **TTS Latence** :
   - Génération TTS Coqui : 2-5 secondes par phrase
   - Solution actuelle : Cache + pré-génération audio statique

6. **Tests** :
   - Tests unitaires incomplets (~40% couverture)
   - Pas de tests end-to-end automatisés pour Freestyle AI

### Améliorations Futures (Roadmap)

#### Phase 1 (Court terme - 1-2 mois)
- [ ] Tests unitaires complets (>80% couverture) + tests Freestyle AI
- [ ] Dashboard web React (monitoring temps réel Freestyle turns + objections)
- [ ] Cache sémantique Freestyle (embeddings similarité au lieu de MD5)
- [ ] Support multilingue AMD (anglais, espagnol)
- [ ] Documentation API OpenAPI complète avec exemples Freestyle

#### Phase 2 (Moyen terme - 3-6 mois)
- [ ] Architecture asyncio (scaling 50+ appels)
- [ ] IA Freestyle avec RAG (Retrieval Augmented Generation sur docs produit)
- [ ] TTS cache intelligent (pré-génération phrases fréquentes par thématique)
- [ ] Sentiment analysis temps réel (graphes WebSocket émotions prospect)
- [ ] Intégration CRM (Salesforce, HubSpot) avec injection contexte Freestyle
- [ ] Auto-tuning objection matcher (machine learning sur historique)

#### Phase 3 (Long terme - 6-12 mois)
- [ ] Multi-tenant (plusieurs organisations avec objections personnalisées)
- [ ] A/B testing scénarios + personnalités (optimisation conversion)
- [ ] Voice biometrics (détection émotions avancée via tonalité voix)
- [ ] Freestyle AI multi-LLM (GPT-4, Claude, Llama 3.1 70B)
- [ ] Déploiement Kubernetes (haute disponibilité + auto-scaling)

---

## 🤝 Contribution & Support

### Contact Développeurs

**Projet** : MiniBotPanel v3
**Version** : 3.0.0
**Licence** : Propriétaire
**Dernière mise à jour** : 29 Janvier 2025

### Rapports de Bugs

**Format** :
1. **Description** : Que se passe-t-il ?
2. **Étapes reproduction** : Comment reproduire le bug ?
3. **Comportement attendu** : Que devrait-il se passer ?
4. **Logs** : Extrait de `logs/system/minibot.log` et `logs/freestyle/`
5. **Environnement** : OS, Python version, FreeSWITCH version, Ollama model

### Demandes Fonctionnalités

**Template** :
```markdown
## Feature Request

**Problème** : Quel problème cette fonctionnalité résout ?
**Solution proposée** : Comment devrait-elle fonctionner ?
**Alternatives** : Avez-vous considéré d'autres solutions ?
**Impact** : Qui bénéficiera de cette feature ?
```

---

## 📚 Ressources

### Documentation Officielle

- **FreeSWITCH** : https://freeswitch.org/confluence/
- **Vosk** : https://alphacephei.com/vosk/
- **Ollama** : https://ollama.com/ ← NOUVEAU v3
- **Coqui TTS** : https://github.com/coqui-ai/TTS
- **FastAPI** : https://fastapi.tiangolo.com/

### Guides Internes

- `GUIDE_INSTALLATION.md` : Installation complète du système (avec Ollama)
- `GUIDE_UTILISATION.md` : Guide utilisateur CLI + API + Freestyle AI
- `BRIEF_PROJET.md` : Ce document (architecture & fonctionnalités v3)
- `FREESTYLE_MODE.md` : Guide complet mode Freestyle AI

### Fichiers Clés v3

| Fichier | Description | Lignes |
|---------|-------------|--------|
| `system/robot_freeswitch.py` | Cœur du robot appels + Freestyle handler | 1350+ |
| `system/campaign_manager.py` | Gestion campagnes + queue + scenarios loader | 580+ |
| `system/objection_matcher.py` | Fuzzy matching objections ← NOUVEAU | 307 |
| `system/objections_database.py` | 153 objections (9 thématiques) ← NOUVEAU | 432 |
| `create_scenario.py` | Assistant création scénario interactif ← AMÉLIORÉ | 420+ |
| `launch_campaign.py` | Lancement campagne avec menu ← AMÉLIORÉ | 262 |
| `system/services/streaming_asr.py` | WebSocket ASR server | 432 |
| `system/api/main.py` | FastAPI app + middlewares | 418 |
| `system/config.py` | Configuration centralisée | 230 |

---

## ✅ Checklist Pré-Production

Avant déploiement production, vérifiez :

### Configuration
- [ ] `.env` configuré (copie depuis `.env.example`)
- [ ] `API_PASSWORD` changé (mot de passe fort)
- [ ] `DATABASE_URL` pointe vers PostgreSQL production
- [ ] `FREESWITCH_ESL_PASSWORD` changé (depuis "ClueCon")
- [ ] `FREESWITCH_GATEWAY` configuré (provider SIP valide)
- [ ] `OLLAMA_MODEL` configuré (mistral:7b ou llama3.2) ← NOUVEAU v3
- [ ] `OBJECTION_MIN_SCORE` ajusté (0.5 par défaut) ← NOUVEAU v3

### Infrastructure
- [ ] PostgreSQL installé + base créée
- [ ] FreeSWITCH installé + testé (ESL connection OK)
- [ ] Modèles IA téléchargés (Vosk, Ollama mistral:7b) ← AMÉLIORÉ v3
- [ ] Ollama service démarré (`ollama serve`) ← NOUVEAU v3
- [ ] Coqui TTS testé (génération audio OK)
- [ ] Objection Matcher testé (153 objections loaded) ← NOUVEAU v3

### Sécurité
- [ ] HTTPS activé (reverse proxy)
- [ ] Firewall configuré (ports 8000, 8080, 8021, 11434) ← +11434 v3
- [ ] Logs rotation configurée
- [ ] Backups base de données automatiques

### Tests
- [ ] Test FreeSWITCH ESL (connection OK)
- [ ] Test Vosk STT (transcription OK)
- [ ] Test Ollama NLP (intent detection + Freestyle generation OK) ← AMÉLIORÉ v3
- [ ] Test Objection Matcher (matching OK) ← NOUVEAU v3
- [ ] Test Coqui TTS (génération audio OK)
- [ ] Test appel complet end-to-end avec Freestyle AI ← AMÉLIORÉ v3

### Monitoring
- [ ] Prometheus configuré (scraping `/metrics`)
- [ ] Health check `/health` fonctionnel (avec Ollama check) ← AMÉLIORÉ v3
- [ ] Logs centralisés (Loki, ELK, ou fichier)
- [ ] Alertes configurées (appels échoués, erreurs IA, Ollama down) ← AMÉLIORÉ v3

### Légal
- [ ] Message enregistrement appel dans scénarios
- [ ] Horaires légaux configurés (`LEGAL_HOURS`)
- [ ] Opt-out mechanism testé
- [ ] Conservation données conforme (RGPD)

### Scénarios v3
- [ ] Au moins 1 scénario créé dans `scenarios/` ← NOUVEAU v3
- [ ] Scénarios testés avec Freestyle AI ← NOUVEAU v3
- [ ] Objections pré-enregistrées générées (TTS cache) ← NOUVEAU v3

---

## 🎯 Conclusion

MiniBotPanel v3 est une plateforme complète de robotisation d'appels téléphoniques avec IA conversationnelle **Freestyle**. Le système est **production-ready** à ~90% :

**Points forts** :
- ✅ Architecture solide (FreeSWITCH + FastAPI + PostgreSQL)
- ✅ IA conversationnelle complète (STT, NLP, TTS, AMD)
- ✅ **Freestyle AI** : Réponses dynamiques Ollama (Mistral 7B) ← NOUVEAU v3
- ✅ **Objection Matching** : 153 objections fuzzy matching ← NOUVEAU v3
- ✅ **7 Personnalités** : Agents configurables ← NOUVEAU v3
- ✅ **9 Thématiques** : Or, Vin, Crypto, Finance, etc. ← NOUVEAU v3
- ✅ Streaming ASR temps réel (WebSocket)
- ✅ API REST complète + outils CLI interactifs ← AMÉLIORÉ v3
- ✅ Conformité légale (horaires, opt-out)

**À améliorer** :
- ⚠️ Tests unitaires (couverture ~40%, besoin tests Freestyle AI)
- ⚠️ Dashboard web monitoring (Freestyle turns + objections)
- ⚠️ Scaling asyncio (100+ appels)
- ⚠️ Cache sémantique Freestyle (au lieu de MD5)
- ⚠️ Documentation utilisateur finale (guide complet Freestyle)

**Démarrage rapide v3** :
```bash
# 1. Installation (avec Ollama)
# Voir GUIDE_INSTALLATION.md section 6

# 2. Configuration
cp .env.example .env
nano .env  # Configurer OLLAMA_MODEL, API_PASSWORD, etc.

# 3. Télécharger modèle Ollama
ollama pull mistral:7b

# 4. Créer un scénario
python create_scenario.py --interactive

# 5. Démarrage
python -m uvicorn system.api.main:app --host 0.0.0.0 --port 8000

# 6. Lancer campagne
python launch_campaign.py --interactive

# 7. Test health
curl http://localhost:8000/health
```

Pour toute question, consultez `GUIDE_INSTALLATION.md`, `GUIDE_UTILISATION.md` et `FREESTYLE_MODE.md`.

---

**Version du guide** : v3.0.0
**Dernière mise à jour** : 2025-01-29
