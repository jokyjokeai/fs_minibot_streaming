# Guide de Migration MiniBotPanel V3 vers Jambonz

**Date:** 2025-11-09
**Version actuelle:** MiniBotPanel V3 (FreeSWITCH)
**Plateforme cible:** Jambonz (Open Source CPaaS)
**Auteur:** Analyse automatisée complète du projet

---

## Table des matières

1. [Résumé exécutif](#1-résumé-exécutif)
2. [Architecture actuelle V3](#2-architecture-actuelle-v3)
3. [Architecture Jambonz](#3-architecture-jambonz)
4. [Mapping des fonctionnalités](#4-mapping-des-fonctionnalités)
5. [Comparaison technique détaillée](#5-comparaison-technique-détaillée)
6. [Plan de migration](#6-plan-de-migration)
7. [Avantages et inconvénients](#7-avantages-et-inconvénients)
8. [Exemples de code](#8-exemples-de-code)
9. [Risques et limitations](#9-risques-et-limitations)
10. [Recommandations](#10-recommandations)

---

## 1. Résumé exécutif

### Contexte
MiniBotPanel V3 est un système de robot vocal conversationnel actuellement basé sur FreeSWITCH avec streaming audio WebSocket. Le système intègre:
- **8,000+ lignes de code Python**
- ASR temps réel (Vosk)
- NLP (Ollama/Mistral)
- Détection de barge-in
- Gestion de scénarios JSON
- Détection AMD (Answering Machine Detection)
- Base de données PostgreSQL

### Pourquoi Jambonz?
Jambonz est une plateforme CPaaS (Communication Platform as a Service) open-source spécialement conçue pour les applications d'IA conversationnelle. Elle offre:
- Architecture moderne WebRTC native
- API simplifiée avec verbs JSON
- Streaming ASR/TTS intégré
- Barge-in natif avec gestion d'interruption
- AMD intégré
- Meilleure gestion de l'écho acoustique (AEC)

### Conclusion rapide
**Migration recommandée** - Jambonz simplifiera considérablement l'architecture (réduction estimée de 60% du code) tout en améliorant la qualité audio et la gestion des problèmes d'écho acoustique.

---

## 2. Architecture actuelle V3

### 2.1 Stack technologique

```
┌─────────────────────────────────────────────────────────┐
│                    MiniBotPanel V3                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────────────────┐   │
│  │ FreeSWITCH   │◄────►│ robot_freeswitch_v3.py   │   │
│  │   + ESL      │      │   (1805 lignes)          │   │
│  │   + mod_     │      │   - Orchestrateur        │   │
│  │   audio_     │      │   - Call control         │   │
│  │   stream     │      │   - Barge-in detector    │   │
│  └──────┬───────┘      └──────────┬───────────────┘   │
│         │                          │                    │
│         │ WebSocket               │                    │
│         │ (audio PCM)             │                    │
│         ▼                          ▼                    │
│  ┌──────────────────────┐  ┌────────────────────┐     │
│  │ streaming_asr_v3.py  │  │  scenarios.py      │     │
│  │   (521 lignes)       │  │   (575 lignes)     │     │
│  │   - Vosk ASR         │  │   - JSON loader    │     │
│  │   - WebRTC VAD       │  │   - Step executor  │     │
│  │   - Speech detection │  │   - Score calc     │     │
│  └──────────┬───────────┘  └────────┬───────────┘     │
│             │                        │                  │
│             ▼                        ▼                  │
│  ┌──────────────────────┐  ┌────────────────────┐     │
│  │   ollama_nlp.py      │  │ objection_matcher  │     │
│  │   (346 lignes)       │  │    (478 lignes)    │     │
│  │   - Intent classify  │  │   - Fuzzy match    │     │
│  │   - LLM calls        │  │   - Audio finder   │     │
│  └──────────────────────┘  └────────────────────┘     │
│                                                         │
│  ┌──────────────────────┐  ┌────────────────────┐     │
│  │   amd_service.py     │  │  database.py       │     │
│  │   (252 lignes)       │  │  models.py         │     │
│  │   - Dual AMD         │  │   - PostgreSQL     │     │
│  │   - Keyword+Duration │  │   - SQLAlchemy     │     │
│  └──────────────────────┘  └────────────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Composants principaux

#### robot_freeswitch_v3.py (1805 lignes)
**Rôle:** Orchestrateur principal du système
- Gestion de deux connexions ESL (inbound + outbound)
- Thread par appel
- State machine immutable (CallState dataclass)
- BargeInDetector simplifié (durée >= 2.0s)
- Coordination streaming audio ↔ ASR ↔ NLP ↔ Scénarios

**Fonctions clés:**
- `originate_call()`: Création d'appels sortants
- `_handle_call()`: Gestion cycle de vie appel
- `_enable_audio_streaming()`: Activation mod_audio_stream
- `_play_audio()`: Lecture fichiers audio avec UUID tracking
- `_listen_for_response()`: Écoute utilisateur avec grace period
- `_execute_scenario()`: Exécution pas-à-pas du scénario
- `_handle_streaming_event()`: Traitement événements ASR

**Configuration clé:**
```python
BARGE_IN_DURATION_THRESHOLD = 2.0  # secondes
GRACE_PERIOD_SECONDS = 2.0         # secondes
SMOOTH_DELAY_SECONDS = 1.0         # secondes
```

#### streaming_asr_v3.py (521 lignes)
**Rôle:** Serveur WebSocket ASR + VAD
- Réception audio 16kHz mono de FreeSWITCH
- Détection de parole (WebRTC VAD)
- Transcription Vosk temps réel
- Envoi événements: `speech_start`, `speech_end`, `transcription`

**Architecture:**
```python
class StreamingASRService:
    - WebSocket server (asyncio)
    - Audio buffer management (30ms frames)
    - VAD state machine
    - Vosk recognizer pool
    - Event emission avec duration
```

**Événements émis:**
```json
{
  "event": "speech_start",
  "timestamp": 1234567890.123
}

{
  "event": "speech_end",
  "duration": 2.3,
  "timestamp": 1234567892.423
}

{
  "event": "transcription",
  "text": "bonjour",
  "timestamp": 1234567892.500
}
```

#### scenarios.py (575 lignes)
**Rôle:** Gestionnaire de scénarios conversationnels JSON

**Format de scénario:**
```json
{
  "metadata": {
    "name": "Production V1",
    "voice": "julie",
    "start_step": "hello"
  },
  "agent_mode": true,
  "theme_file": "objections_finance",
  "rail": ["Hello", "Q1_Proprietaire", "Q2_Surface", "Bye_Success"],
  "steps": {
    "Hello": {
      "message_text": "Bonjour {{first_name}}, je suis Julie...",
      "audio_type": "audio",
      "audio_file": "hello.wav",
      "max_autonomous_turns": 2,
      "intent_mapping": {
        "affirm": "Q1_Proprietaire",
        "deny": "Bye_Failed",
        "objection": "autonomous_agent"
      }
    }
  }
}
```

**Fonctionnalités:**
- Chargement/validation scénarios JSON
- Navigation entre étapes
- Remplacement variables (`{{first_name}}`)
- Calcul de score lead
- Support audio prédéfini + TTS
- Mode agent autonome pour objections

#### objection_matcher.py (478 lignes)
**Rôle:** Matching d'objections avec réponses audio préenregistrées

**Algorithme de scoring:**
```python
hybrid_score = 0.7 × text_similarity + 0.3 × keyword_overlap
```

**Base de données d'objections modulaire:**
- `objections_general.py`: 30 objections générales
- `objections_finance.py`: 20 objections spécifiques finance
- Auto-conversion chemins audio FreeSWITCH

#### amd_service.py (252 lignes)
**Rôle:** Détection de répondeur automatique

**Double détection:**
1. **Keyword-based (70%)**: Recherche phrases typiques ("laissez un message")
2. **Duration-based (30%)**: Durée de salutation > seuil

**Scoring:**
```python
if final_score >= 0.5:
    result = "MACHINE"
else:
    result = "HUMAN"
```

#### Base de données (database.py + models.py)
**Modèles SQLAlchemy:**
- `Contact`: Leads avec informations
- `Campaign`: Campagnes d'appels
- `Call`: Historique d'appels
- `CallEvent`: Événements détaillés par appel

### 2.3 Flux de données typique

```
1. Origination appel
   robot_freeswitch_v3.originate_call()
   ↓
2. AMD Detection
   amd_service.detect_answering_machine()
   ↓
3. Si HUMAN détecté
   ↓
4. Chargement scénario
   scenarios.load_scenario()
   ↓
5. Lecture audio + Enable streaming
   _play_audio() + _enable_audio_streaming()
   ↓
6. Streaming audio → ASR WebSocket
   FreeSWITCH mod_audio_stream → streaming_asr_v3
   ↓
7. VAD détecte parole
   speech_start event
   ↓
8. Barge-in detector check
   Si duration >= 2.0s → interruption
   ↓
9. Transcription complète
   Vosk → transcription event
   ↓
10. Classification NLP
    ollama_nlp.classify_intent()
    ↓
11. Si objection → Matching
    objection_matcher.find_best_match()
    ↓
12. Prochaine étape scénario
    scenarios.get_next_step()
    ↓
13. Répéter 5-12 jusqu'à fin
```

### 2.4 Problèmes actuels identifiés

#### 🔴 CRITIQUE: Écho acoustique
**Problème:**
- Quand client est en haut-parleur (ou test sur ordinateur)
- Le robot parle → sortie haut-parleur
- Microphone capte l'audio du robot
- Détecté comme barge-in → interruption continue

**Impact:**
- Système inutilisable pour clients en haut-parleur
- Pas d'AEC (Acoustic Echo Cancellation) dans la config actuelle

**Solution potentielle Jambonz:**
- WebRTC natif avec AEC intégré
- Meilleure gestion de l'écho acoustique

#### 🟡 Complexité architecture
- 8,000+ lignes de code
- Multiple composants à synchroniser
- WebSocket séparé pour ASR
- Gestion manuelle des états
- Thread management complexe

#### 🟡 Dépendance FreeSWITCH
- Configuration complexe (mod_audio_stream)
- ESL peu documenté
- Debugging difficile
- Installation/maintenance lourde

---

## 3. Architecture Jambonz

### 3.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────┐
│                      Jambonz Platform                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────────────────┐   │
│  │   SBC        │      │   Feature Server         │   │
│  │  (Session    │◄────►│   (Application Logic)    │   │
│  │   Border     │      │                          │   │
│  │   Controller)│      │   - Verb execution       │   │
│  │              │      │   - Webhook calls        │   │
│  │  - SIP/RTP   │      │   - WebSocket support    │   │
│  │  - WebRTC    │      └──────────┬───────────────┘   │
│  │  - AEC       │                  │                    │
│  └──────┬───────┘                  │                    │
│         │                          │                    │
│         │                          │ HTTP/WebSocket     │
│         │                          │                    │
│         │                          ▼                    │
│         │                  ┌───────────────────────┐   │
│         │                  │  Application Webhook  │   │
│         │                  │  (Your Node.js/Python)│   │
│         │                  │                       │   │
│         │                  │  - Verb generation    │   │
│         │                  │  - Business logic     │   │
│         │                  │  - Database access    │   │
│         │                  └───────────────────────┘   │
│         │                                               │
│         ▼                                               │
│  ┌──────────────────────────────────────────────┐     │
│  │          Speech Services                     │     │
│  │  - ASR: Google, AWS, Deepgram, Whisper...   │     │
│  │  - TTS: Google, AWS, ElevenLabs, Azure...   │     │
│  │  - VAD: Integrated with ASR providers       │     │
│  └──────────────────────────────────────────────┘     │
│                                                         │
│  ┌──────────────┐      ┌──────────────────────────┐   │
│  │   MySQL      │      │   Redis                  │   │
│  │  (Multi-     │      │  (Transient data)        │   │
│  │   tenant DB) │      │                          │   │
│  └──────────────┘      └──────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Composants Jambonz

#### Session Border Controller (SBC)
- Gestion de la signalisation SIP
- Traitement média RTP/WebRTC
- **AEC (Acoustic Echo Cancellation) intégré**
- Support multi-protocoles

#### Feature Server
- Exécution des verbs Jambonz
- Appels webhooks vers application
- Gestion du streaming ASR/TTS
- Barge-in natif

#### Application Webhook
- Votre code métier (Node.js, Python, etc.)
- Génération de verbs JSON
- Logique conversationnelle
- Intégration base de données

#### Speech Services
- Intégration 18+ fournisseurs ASR/TTS
- Configuration flexible
- Streaming audio temps réel

### 3.3 Verbs Jambonz disponibles

Jambonz utilise des "verbs" JSON pour contrôler les appels:

#### `dial` - Appeler un numéro
```json
{
  "verb": "dial",
  "target": [{"type": "phone", "number": "+33612345678"}],
  "actionHook": "/dial-status",
  "answerOnBridge": true,
  "amd": {
    "actionHook": "/amd-result",
    "recognizer": {
      "vendor": "google",
      "language": "fr-FR"
    }
  }
}
```

#### `listen` - Streaming ASR bidirectionnel
```json
{
  "verb": "listen",
  "url": "wss://your-app.com/audio-stream",
  "mixType": "stereo",
  "playback": {
    "url": "wss://your-app.com/audio-stream"
  },
  "transcribe": {
    "vendor": "google",
    "language": "fr-FR",
    "interim": true,
    "separateRecognitionPerChannel": true
  }
}
```

#### `say` - TTS avec streaming
```json
{
  "verb": "say",
  "text": "Bonjour, je suis Julie",
  "synthesizer": {
    "vendor": "elevenlabs",
    "voice": "julie-voice-id",
    "language": "fr-FR"
  },
  "earlyMedia": true
}
```

#### `gather` - Collecte input avec barge-in
```json
{
  "verb": "gather",
  "actionHook": "/handle-speech",
  "input": ["speech"],
  "timeout": 5,
  "recognizer": {
    "vendor": "google",
    "language": "fr-FR",
    "hints": ["oui", "non", "peut-être"]
  },
  "say": {
    "text": "Êtes-vous propriétaire?",
    "synthesizer": {"vendor": "elevenlabs"}
  }
}
```

#### `config` - Configuration dynamique
```json
{
  "verb": "config",
  "bargeIn": {
    "enable": true,
    "input": ["speech"],
    "actionHook": "/handle-bargein"
  },
  "amd": {
    "actionHook": "/amd-result",
    "thresholds": {
      "greeting_duration": 2000
    }
  }
}
```

### 3.4 Webhooks Jambonz

Jambonz communique avec votre application via webhooks HTTP:

#### Webhook d'application
**Request de Jambonz:**
```json
{
  "call_sid": "abc123",
  "direction": "outbound",
  "from": "+33612345678",
  "to": "+33687654321",
  "call_status": "in-progress"
}
```

**Response de votre app (verbs):**
```json
[
  {
    "verb": "say",
    "text": "Bonjour {{name}}"
  },
  {
    "verb": "gather",
    "input": ["speech"],
    "actionHook": "/handle-response"
  }
]
```

#### ActionHook (événements)
**Barge-in event:**
```json
{
  "event": "user_interruption",
  "call_sid": "abc123",
  "speech": {
    "text": "allô",
    "confidence": 0.95
  }
}
```

**AMD result:**
```json
{
  "event": "amd_result",
  "call_sid": "abc123",
  "amd": {
    "result": "HUMAN",
    "confidence": 0.87,
    "duration": 1200
  }
}
```

### 3.5 API REST Jambonz

Pour créer des campagnes d'appels:

```bash
POST https://api.jambonz.org/v1/Accounts/{AccountSid}/Calls
Authorization: Bearer YOUR_API_TOKEN

{
  "to": "+33612345678",
  "from": "+33987654321",
  "application_sid": "app_abc123",
  "webhook": {
    "url": "https://your-app.com/call-webhook",
    "method": "POST"
  }
}
```

---

## 4. Mapping des fonctionnalités

### 4.1 Table de correspondance

| Fonctionnalité V3 | Composant V3 | Équivalent Jambonz | Complexité |
|------------------|--------------|-------------------|-----------|
| **Origination appel** | `robot_freeswitch_v3.originate_call()` | REST API `/Calls` + verb `dial` | ✅ Simple |
| **Streaming ASR** | `streaming_asr_v3.py` (521 lignes) | Verb `listen` avec `transcribe` | ✅ Simple |
| **VAD** | WebRTC VAD dans `streaming_asr_v3.py` | Intégré dans speech providers | ✅ Simple |
| **Barge-in detection** | `BargeInDetector` class | Config `bargeIn` natif | ✅ Simple |
| **AMD** | `amd_service.py` (252 lignes) | Verb `dial` avec option `amd` | ✅ Simple |
| **TTS audio** | `_play_audio()` fichiers WAV | Verb `say` avec streaming TTS | ✅ Simple |
| **Audio préenregistré** | Fichiers WAV + `_play_audio()` | Verb `say` avec `audio_file` URL | ✅ Simple |
| **Scénarios JSON** | `scenarios.py` (575 lignes) | Logique webhook + state DB | 🟡 Moyen |
| **NLP intent** | `ollama_nlp.py` (346 lignes) | Même code dans webhook app | ✅ Simple |
| **Objection matching** | `objection_matcher.py` (478 lignes) | Même code dans webhook app | ✅ Simple |
| **Grace period** | `GRACE_PERIOD_SECONDS` config | `gather` verb `timeout` | ✅ Simple |
| **Call state tracking** | `CallState` dataclass + threads | Session state dans DB/Redis | 🟡 Moyen |
| **Database tracking** | PostgreSQL + SQLAlchemy | Même stack possible | ✅ Simple |
| **Campaign management** | Table `Campaign` + loop | REST API + scheduler externe | 🟡 Moyen |
| **Multi-threading** | `threading.Thread` par appel | Géré par Jambonz | ✅ Simple |
| **WebSocket audio** | FreeSWITCH mod_audio_stream | Jambonz `listen` verb WebSocket | ✅ Simple |
| **AEC (Echo Cancel)** | ❌ Non implémenté | ✅ Intégré dans SBC | ✅ Simple |

### 4.2 Analyse détaillée

#### ✅ Fonctionnalités simplifiées avec Jambonz

1. **Streaming ASR + VAD**
   - **V3**: 521 lignes de code (WebSocket server + VAD + Vosk)
   - **Jambonz**: Verb `listen` avec configuration JSON
   - **Gain**: ~95% réduction code

2. **Barge-in**
   - **V3**: `BargeInDetector` class + logique manuelle
   - **Jambonz**: Config `bargeIn.enable: true`
   - **Gain**: Natif + événements automatiques

3. **AMD**
   - **V3**: 252 lignes (dual detection keyword+duration)
   - **Jambonz**: Option `amd` dans verb `dial`
   - **Gain**: ~98% réduction code

4. **AEC (Acoustic Echo Cancellation)**
   - **V3**: ❌ Problème critique non résolu
   - **Jambonz**: ✅ Intégré dans SBC WebRTC
   - **Gain**: Résolution du problème haut-parleur

#### 🟡 Fonctionnalités nécessitant refactoring

1. **Gestion de scénarios**
   - Logique métier à maintenir dans webhook app
   - État de conversation à stocker (DB ou Redis)
   - Navigation entre steps via actionHooks

2. **Campaign management**
   - Pas de système intégré dans Jambonz
   - Utiliser REST API + scheduler externe (Celery, Airflow)
   - Possibilité d'utiliser la même table PostgreSQL

3. **Call state management**
   - V3 utilise threads + CallState dataclass
   - Jambonz: webhooks stateless
   - Solution: Redis ou PostgreSQL pour état de session

---

## 5. Comparaison technique détaillée

### 5.1 Streaming ASR

#### Architecture V3 (FreeSWITCH)
```python
# streaming_asr_v3.py - 521 lignes
class StreamingASRService:
    async def handle_client(self, websocket, path):
        # Réception audio frames
        audio_data = await websocket.recv()

        # VAD processing
        is_speech = self.vad.is_speech(audio_frame, 16000)

        # Vosk transcription
        if self.recognizer.AcceptWaveform(audio_data):
            result = json.loads(self.recognizer.Result())
            text = result.get('text', '')

        # Event emission
        await self.send_event({
            "event": "transcription",
            "text": text,
            "timestamp": time.time()
        })
```

**Complexité:**
- Serveur WebSocket asyncio complet
- Gestion buffers audio
- State machine VAD manuelle
- Pool de recognizers Vosk
- Gestion erreurs/reconnexions

**Total: 521 lignes**

#### Architecture Jambonz

```json
{
  "verb": "listen",
  "url": "wss://your-app.com/audio-stream",
  "transcribe": {
    "vendor": "google",
    "language": "fr-FR",
    "interim": true
  }
}
```

**Webhook reçoit:**
```json
{
  "event": "transcription",
  "call_sid": "abc123",
  "speech": {
    "text": "bonjour",
    "confidence": 0.95,
    "is_final": true
  }
}
```

**Complexité:**
- Configuration JSON uniquement
- Pas de code serveur WebSocket
- VAD intégré dans provider
- Gestion automatique par Jambonz

**Total: ~20 lignes de configuration**

**Gain: 96% réduction de code**

### 5.2 Barge-in Detection

#### V3 Implementation
```python
# robot_freeswitch_v3.py
class BargeInDetector:
    def __init__(self):
        self.speech_duration = 0.0
        self.THRESHOLD = 2.0

    def handle_speech_start(self, timestamp):
        self.speech_start_time = timestamp

    def handle_speech_end(self, timestamp):
        duration = timestamp - self.speech_start_time
        self.speech_duration = duration

    def should_interrupt(self) -> bool:
        return self.speech_duration >= self.THRESHOLD

# Dans _play_audio()
if barge_in_detector.should_interrupt():
    self._stop_playback(call_state)
```

**Complexité:**
- Classe dédiée
- Tracking manuel des timestamps
- Logique de décision custom
- Intégration avec playback stop

#### Jambonz Implementation

```json
{
  "verb": "config",
  "bargeIn": {
    "enable": true,
    "input": ["speech"],
    "actionHook": "/handle-bargein"
  }
}
```

**Webhook reçoit automatiquement:**
```json
{
  "event": "user_interruption",
  "call_sid": "abc123",
  "speech": {
    "text": "allô",
    "duration": 2100
  }
}
```

**Complexité:**
- Configuration JSON uniquement
- Détection automatique
- Événement envoyé automatiquement
- Playback stop automatique

**Gain: Logique native, pas de code nécessaire**

### 5.3 AMD (Answering Machine Detection)

#### V3 Implementation
```python
# amd_service.py - 252 lignes
class AMDService:
    def __init__(self):
        self.machine_keywords = [
            "laissez un message", "boîte vocale",
            "veuillez laisser", "messagerie"
        ]

    def detect_answering_machine(self, transcription, duration):
        # Keyword detection (70% weight)
        keyword_score = self._check_keywords(transcription)

        # Duration detection (30% weight)
        duration_score = self._check_duration(duration)

        # Hybrid scoring
        final_score = 0.7 * keyword_score + 0.3 * duration_score

        return "MACHINE" if final_score >= 0.5 else "HUMAN"
```

**Complexité:**
- 252 lignes de code
- Dual algorithm custom
- Maintenance liste keywords
- Tuning des poids

#### Jambonz Implementation

```json
{
  "verb": "dial",
  "target": [{"type": "phone", "number": "+33612345678"}],
  "amd": {
    "actionHook": "/amd-result",
    "recognizer": {
      "vendor": "google",
      "language": "fr-FR"
    },
    "thresholds": {
      "greeting_duration": 2000,
      "speech_threshold": 256
    }
  }
}
```

**Webhook reçoit:**
```json
{
  "event": "amd_result",
  "amd": {
    "result": "HUMAN",
    "reason": "short_greeting",
    "confidence": 0.87,
    "duration": 1200
  }
}
```

**Complexité:**
- Configuration JSON uniquement
- Algorithme éprouvé intégré
- Détection automatique
- Résultat + confidence + reason

**Gain: 99% réduction de code**

### 5.4 Écho acoustique (AEC)

#### V3 Status
**Problème actuel:**
```
Client en haut-parleur:
  Robot parle → Haut-parleur → Microphone capte
  → Détecté comme speech → Barge-in déclenché
  → Interruption continue → Système bloqué
```

**Solution V3:**
- ❌ Pas d'AEC implémenté
- ❌ Nécessite configuration FreeSWITCH complexe
- ❌ Performance variable selon matériel
- 🔴 **BLOQUANT pour déploiement production**

#### Jambonz Status
**Solution intégrée:**
- ✅ AEC natif dans SBC WebRTC
- ✅ Echo cancellation automatique
- ✅ Testé et optimisé
- ✅ Pas de configuration nécessaire

**Impact:**
- Clients peuvent utiliser haut-parleur
- Tests sur ordinateur possibles
- Qualité audio améliorée
- Pas de faux barge-in

**Gain: Résolution problème critique**

---

## 6. Plan de migration

### 6.1 Phase 1: Preuve de concept (1-2 semaines)

#### Objectifs
- Valider faisabilité technique
- Tester streaming ASR + barge-in
- Vérifier AMD
- Mesurer qualité audio + AEC

#### Tâches
1. **Setup Jambonz**
   - Installation Docker local
   - Configuration compte/application
   - Setup webhooks ngrok pour dev

2. **Application webhook simple**
   ```javascript
   // app.js - Webhook Jambonz minimal
   app.post('/call-webhook', async (req, res) => {
     const { call_sid, from, to } = req.body;

     res.json([
       {
         verb: 'say',
         text: 'Bonjour, je suis Julie',
         synthesizer: {
           vendor: 'elevenlabs',
           voice: 'julie-voice-id'
         }
       },
       {
         verb: 'gather',
         input: ['speech'],
         actionHook: '/handle-response',
         recognizer: {
           vendor: 'google',
           language: 'fr-FR'
         }
       }
     ]);
   });

   app.post('/handle-response', async (req, res) => {
     const { speech } = req.body;
     console.log('User said:', speech.text);

     // Classification intent avec Ollama
     const intent = await classifyIntent(speech.text);

     // Prochaine étape
     res.json([/* next verbs */]);
   });
   ```

3. **Tests**
   - Appel sortant simple
   - Test AMD
   - Test barge-in
   - Test haut-parleur (vérif AEC)

#### Critères de succès
- ✅ Appel réussi avec audio
- ✅ AMD détecte HUMAN vs MACHINE
- ✅ Barge-in fonctionne correctement
- ✅ Pas d'écho avec haut-parleur

### 6.2 Phase 2: Migration composants core (2-3 semaines)

#### 2.1 Migration NLP + Objection Matcher

**Réutilisation code V3:**
- `ollama_nlp.py` → Intégration dans webhook app
- `objection_matcher.py` → Intégration dans webhook app
- `objections_db/` → Même structure, adaptation chemins audio

**Adaptation:**
```python
# webhook_app/nlp_service.py
from system.ollama_nlp import OllamaNLP
from system.objection_matcher import ObjectionMatcher

nlp = OllamaNLP()
objection_matcher = ObjectionMatcher()

async def handle_user_speech(speech_text, context):
    # Classification intent
    intent = await nlp.classify_intent(speech_text, context)

    # Si objection
    if intent == 'objection':
        match = objection_matcher.find_best_match(
            speech_text,
            theme='finance'
        )
        return {
            'intent': 'objection',
            'response_audio': match['audio_url'],
            'response_text': match['text']
        }

    return {'intent': intent}
```

#### 2.2 Migration gestion de scénarios

**Adaptation scenarios.py:**
```python
# webhook_app/scenario_manager.py
class JambonzScenarioManager:
    def __init__(self):
        self.scenarios = {}  # Même format JSON V3

    def get_verbs_for_step(self, scenario, step_id, context):
        """Convertit une step V3 en verbs Jambonz"""
        step = scenario['steps'][step_id]

        verbs = []

        # Audio/TTS
        if step['audio_type'] == 'audio':
            verbs.append({
                'verb': 'say',
                'audio_file': self._get_audio_url(step['audio_file'])
            })
        else:
            text = self._replace_variables(step['message_text'], context)
            verbs.append({
                'verb': 'say',
                'text': text,
                'synthesizer': {
                    'vendor': 'elevenlabs',
                    'voice': scenario['metadata']['voice']
                }
            })

        # Gather user input
        verbs.append({
            'verb': 'gather',
            'input': ['speech'],
            'timeout': 5,
            'actionHook': f'/handle-step/{step_id}',
            'recognizer': {
                'vendor': 'google',
                'language': 'fr-FR'
            }
        })

        return verbs
```

#### 2.3 Migration state management

**V3: CallState en mémoire (threads)**
```python
@dataclass
class CallState:
    call_uuid: str
    campaign_id: int
    contact_id: int
    current_step: str
    conversation_history: List[str]
```

**Jambonz: State externe (Redis ou PostgreSQL)**
```python
# webhook_app/state_manager.py
import redis

class CallStateManager:
    def __init__(self):
        self.redis = redis.Redis(host='localhost', port=6379)

    def get_state(self, call_sid):
        data = self.redis.get(f'call:{call_sid}')
        return json.loads(data) if data else None

    def update_state(self, call_sid, state):
        self.redis.setex(
            f'call:{call_sid}',
            3600,  # TTL 1h
            json.dumps(state)
        )

    def delete_state(self, call_sid):
        self.redis.delete(f'call:{call_sid}')
```

### 6.3 Phase 3: Migration database & campaigns (1-2 semaines)

#### 3.1 Réutilisation models.py

**Aucune modification nécessaire:**
- `Contact`, `Campaign`, `Call`, `CallEvent` → Identiques
- SQLAlchemy fonctionne pareil
- Ajout champ `call_sid` (ID Jambonz) dans `Call`

```python
# Ajout dans models.py
class Call(Base):
    # ... champs existants ...
    call_sid = Column(String(100), nullable=True)  # Jambonz call ID
```

#### 3.2 Campaign manager Jambonz

**V3: Loop dans robot_freeswitch_v3.py**
```python
def start_campaign(self, campaign_id):
    contacts = self.get_campaign_contacts(campaign_id)
    for contact in contacts:
        self.originate_call(contact)
        time.sleep(5)  # Rate limiting
```

**Jambonz: Celery task + REST API**
```python
# webhook_app/campaign_tasks.py
from celery import Celery
import requests

celery = Celery('campaigns')

@celery.task
def launch_campaign(campaign_id):
    campaign = Campaign.query.get(campaign_id)
    contacts = campaign.contacts

    for contact in contacts:
        # Appel REST API Jambonz
        response = requests.post(
            f'https://api.jambonz.org/v1/Accounts/{ACCOUNT_SID}/Calls',
            headers={'Authorization': f'Bearer {API_TOKEN}'},
            json={
                'to': contact.phone_number,
                'from': campaign.caller_id,
                'application_sid': APPLICATION_SID,
                'webhook': {
                    'url': f'{WEBHOOK_BASE_URL}/call-webhook',
                    'method': 'POST'
                },
                'tag': {
                    'campaign_id': campaign_id,
                    'contact_id': contact.id
                }
            }
        )

        # Enregistrement Call
        call = Call(
            campaign_id=campaign_id,
            contact_id=contact.id,
            call_sid=response.json()['sid'],
            status='initiated'
        )
        db.session.add(call)
        db.session.commit()

        time.sleep(5)  # Rate limiting
```

### 6.4 Phase 4: Tests & optimisation (2 semaines)

#### Tests fonctionnels
- Scénario complet end-to-end
- Toutes les branches de scénario
- Mode agent autonome (objections)
- Calcul de score lead
- Enregistrement database complet

#### Tests qualité audio
- Haut-parleur client (AEC)
- Barge-in précision
- Latence ASR/TTS
- Qualité voix TTS

#### Tests performance
- Charge 10/50/100 appels simultanés
- Latence webhooks
- Redis performance
- Database queries

#### Tests edge cases
- Déconnexions réseau
- Timeouts
- Répondeur AMD
- Silence prolongé
- Barge-in rapide

### 6.5 Phase 5: Déploiement production (1 semaine)

#### Infrastructure
- Jambonz production setup (pas Docker)
- Webhook app déployée (Heroku/AWS/GCP)
- Redis production
- PostgreSQL production (même DB possible)
- Monitoring (Grafana inclus dans Jambonz)

#### Migration données
- Export campagnes actives
- Export contacts
- Pas de migration d'historique d'appels (nouveau départ)

#### Cutover
- Tests finaux
- Activation nouveau système
- Désactivation ancien système (keep as backup)

---

## 7. Avantages et inconvénients

### 7.1 Avantages Jambonz

#### ✅ Simplicité architecture
**Réduction de code estimée: 60-70%**
- 521 lignes ASR → ~20 lignes config
- 252 lignes AMD → ~10 lignes config
- Threading/ESL → Géré par Jambonz
- Pas de serveur WebSocket à maintenir

#### ✅ AEC intégré (CRITIQUE)
- Résout le problème d'écho acoustique
- Clients peuvent utiliser haut-parleur
- Tests plus faciles
- Qualité audio améliorée

#### ✅ Multi-provider ASR/TTS
- 18+ fournisseurs supportés
- Switch facile (config uniquement)
- Possibilité de tester différents providers
- Pas de lock-in Vosk

#### ✅ Barge-in natif
- Détection automatique
- Événements standardisés
- Pas de logique custom à maintenir

#### ✅ Webhooks standardisés
- API claire et documentée
- Patterns éprouvés
- Communauté active
- Exemples disponibles

#### ✅ Monitoring intégré
- Grafana dashboards
- Métriques automatiques
- Logs centralisés

#### ✅ Scalabilité
- Architecture distribuée native
- Load balancing automatique
- Pas de gestion threads manuelle

### 7.2 Inconvénients Jambonz

#### ❌ Nouvelle dépendance
- Infrastructure Jambonz à maintenir
- Pas de contrôle total comme FreeSWITCH
- Risque de bugs platform

#### ❌ Coûts potentiels
- ASR/TTS providers cloud peuvent être coûteux
- Alternative: Self-hosted Vosk + Coqui TTS possibles
- Mais perd simplicité

#### ❌ Refactoring nécessaire
- State management à repenser
- Campaign manager à refaire
- Tests complets nécessaires

#### ❌ Courbe d'apprentissage
- Nouveau paradigme (verbs vs ESL)
- Documentation à apprendre
- Debugging différent

#### ❌ Moins de contrôle bas-niveau
- Moins de flexibilité que FreeSWITCH custom
- Dépend des capabilities Jambonz
- Si feature manquante, dépend de roadmap Jambonz

### 7.3 Analyse coûts

#### V3 (FreeSWITCH) - Coûts actuels
```
Infrastructure:
- Serveur FreeSWITCH: $50-100/mois
- Serveur App Python: $20-50/mois
- PostgreSQL: $20/mois
Total infra: ~$100/mois

ASR/TTS:
- Vosk: Gratuit (self-hosted)
- Coqui TTS: Gratuit (self-hosted)
- Compute GPU optionnel: $50-200/mois
Total ASR/TTS: $0-200/mois

Téléphonie:
- Trunk SIP: Variable (€0.01-0.05/min)

TOTAL: $100-300/mois + téléphonie
```

#### Jambonz - Coûts estimés

**Option 1: Self-hosted complet**
```
Infrastructure:
- Jambonz SBC/Feature: $100-150/mois (plus gros serveur)
- App webhook: $20-50/mois
- Redis: $15/mois
- PostgreSQL: $20/mois
Total infra: ~$155-235/mois

ASR/TTS:
- Vosk (self-hosted): Gratuit
- Coqui TTS (self-hosted): Gratuit
- Compute GPU: $50-200/mois
Total ASR/TTS: $50-200/mois

Téléphonie:
- Trunk SIP: Variable (€0.01-0.05/min)

TOTAL: $205-435/mois + téléphonie
```

**Option 2: Cloud ASR/TTS**
```
Infrastructure:
- Jambonz SBC/Feature: $100-150/mois
- App webhook: $20-50/mois
- Redis: $15/mois
- PostgreSQL: $20/mois
Total infra: ~$155-235/mois

ASR/TTS:
- Google Cloud Speech-to-Text: $0.006/15s = $0.024/min
- ElevenLabs TTS: $0.18/1000 chars ≈ $0.05-0.10/min
- Pour 10,000 min/mois: $740/mois
Total ASR/TTS: $740/mois @ 10k min

Téléphonie:
- Trunk SIP: Variable (€0.01-0.05/min)

TOTAL: $895-975/mois + téléphonie (10k min)
```

**Recommandation coûts:**
- Démarrage: Option 1 (self-hosted Vosk/Coqui)
- Si qualité insuffisante: Tester providers cloud
- Possibilité hybrid: ASR cloud (quality) + TTS self-hosted (volume)

---

## 8. Exemples de code

### 8.1 Application webhook complète

```javascript
// app.js - Webhook Jambonz complet
const express = require('express');
const axios = require('axios');
const Redis = require('redis');
const { Pool } = require('pg');

const app = express();
app.use(express.json());

// Redis pour state management
const redis = Redis.createClient({ url: 'redis://localhost:6379' });
await redis.connect();

// PostgreSQL (mêmes models que V3)
const db = new Pool({ connectionString: process.env.DATABASE_URL });

// Import NLP & Objection Matcher (code Python V3 porté ou API)
const nlpService = new NLPService();
const objectionMatcher = new ObjectionMatcher();
const scenarioManager = new ScenarioManager();

// ============================================
// WEBHOOK PRINCIPAL - Début d'appel
// ============================================
app.post('/call-webhook', async (req, res) => {
  const { call_sid, from, to, direction, tag } = req.body;

  // Récupération contexte campagne
  const { campaign_id, contact_id } = tag;
  const contact = await db.query(
    'SELECT * FROM contacts WHERE id = $1',
    [contact_id]
  );

  // Initialisation state
  const callState = {
    call_sid,
    campaign_id,
    contact_id,
    scenario: 'production_v1',
    current_step: 'hello',
    conversation_history: [],
    score: 0,
    autonomous_turns: 0
  };

  // Save state to Redis
  await redis.setEx(
    `call:${call_sid}`,
    3600,  // 1h TTL
    JSON.stringify(callState)
  );

  // Enregistrement Call en DB
  await db.query(
    'INSERT INTO calls (call_sid, campaign_id, contact_id, status) VALUES ($1, $2, $3, $4)',
    [call_sid, campaign_id, contact_id, 'ringing']
  );

  // Configuration barge-in global
  const verbs = [
    {
      verb: 'config',
      bargeIn: {
        enable: true,
        input: ['speech'],
        actionHook: '/handle-bargein'
      }
    }
  ];

  // Chargement scénario et première step
  const scenario = await scenarioManager.loadScenario('production_v1');
  const stepVerbs = await scenarioManager.getVerbsForStep(
    scenario,
    'hello',
    contact
  );

  verbs.push(...stepVerbs);

  res.json(verbs);
});

// ============================================
// HANDLER - Réponse utilisateur (gather)
// ============================================
app.post('/handle-step/:step_id', async (req, res) => {
  const { call_sid, speech } = req.body;
  const { step_id } = req.params;

  // Récupération state
  const stateStr = await redis.get(`call:${call_sid}`);
  const state = JSON.parse(stateStr);

  // Enregistrement transcription
  state.conversation_history.push({
    role: 'user',
    text: speech.text,
    timestamp: Date.now()
  });

  // Classification intent
  const intent = await nlpService.classifyIntent(
    speech.text,
    state.conversation_history
  );

  console.log(`[${call_sid}] User: "${speech.text}" -> Intent: ${intent}`);

  // Gestion intent
  let nextStep = null;
  let verbs = [];

  const scenario = await scenarioManager.loadScenario(state.scenario);
  const currentStep = scenario.steps[step_id];

  if (intent === 'objection') {
    // Mode agent autonome
    if (state.autonomous_turns < currentStep.max_autonomous_turns) {
      const match = await objectionMatcher.findBestMatch(
        speech.text,
        scenario.theme_file
      );

      verbs.push({
        verb: 'say',
        audio_file: match.audio_url
      });

      verbs.push({
        verb: 'gather',
        input: ['speech'],
        timeout: 5,
        actionHook: `/handle-step/${step_id}`,  // Même step
        recognizer: {
          vendor: 'google',
          language: 'fr-FR'
        }
      });

      state.autonomous_turns += 1;
      state.conversation_history.push({
        role: 'assistant',
        text: match.text,
        audio: match.audio_url
      });
    } else {
      // Max objections atteints -> bye
      nextStep = 'Bye_Failed';
    }
  } else {
    // Navigation normale via intent_mapping
    nextStep = currentStep.intent_mapping[intent] || 'Bye_Failed';
  }

  // Si changement de step
  if (nextStep) {
    state.current_step = nextStep;
    state.autonomous_turns = 0;  // Reset counter

    const nextStepVerbs = await scenarioManager.getVerbsForStep(
      scenario,
      nextStep,
      state
    );
    verbs.push(...nextStepVerbs);

    // Si step finale, hangup
    if (nextStep.startsWith('Bye_')) {
      verbs.push({ verb: 'hangup' });
    }
  }

  // Update state
  await redis.setEx(
    `call:${call_sid}`,
    3600,
    JSON.stringify(state)
  );

  res.json(verbs);
});

// ============================================
// HANDLER - Barge-in
// ============================================
app.post('/handle-bargein', async (req, res) => {
  const { call_sid, speech } = req.body;

  console.log(`[${call_sid}] BARGE-IN: "${speech.text}"`);

  // Récupération state
  const stateStr = await redis.get(`call:${call_sid}`);
  const state = JSON.parse(stateStr);

  // Enregistrement barge-in
  state.conversation_history.push({
    role: 'user',
    text: speech.text,
    timestamp: Date.now(),
    barge_in: true
  });

  // Classification intent
  const intent = await nlpService.classifyIntent(
    speech.text,
    state.conversation_history
  );

  // Même logique que handle-step
  // ... (code similaire) ...

  res.json(verbs);
});

// ============================================
// WEBHOOK - AMD Result
// ============================================
app.post('/amd-result', async (req, res) => {
  const { call_sid, amd } = req.body;

  console.log(`[${call_sid}] AMD: ${amd.result} (confidence: ${amd.confidence})`);

  // Update DB
  await db.query(
    'UPDATE calls SET amd_result = $1 WHERE call_sid = $2',
    [amd.result, call_sid]
  );

  if (amd.result === 'MACHINE') {
    // Raccrocher immédiatement
    res.json([
      {
        verb: 'say',
        text: 'Au revoir'
      },
      {
        verb: 'hangup'
      }
    ]);
  } else {
    // Continuer avec scénario
    res.json([]);  // Continue normal flow
  }
});

// ============================================
// WEBHOOK - Call Status (fin d'appel)
// ============================================
app.post('/call-status', async (req, res) => {
  const { call_sid, call_status, duration } = req.body;

  console.log(`[${call_sid}] Status: ${call_status}, Duration: ${duration}s`);

  // Récupération state finale
  const stateStr = await redis.get(`call:${call_sid}`);
  const state = stateStr ? JSON.parse(stateStr) : null;

  // Update DB
  await db.query(
    'UPDATE calls SET status = $1, duration = $2, final_step = $3, score = $4 WHERE call_sid = $5',
    [call_status, duration, state?.current_step, state?.score, call_sid]
  );

  // Enregistrement conversation history
  if (state) {
    for (const msg of state.conversation_history) {
      await db.query(
        'INSERT INTO call_events (call_sid, event_type, text, timestamp) VALUES ($1, $2, $3, $4)',
        [call_sid, msg.role, msg.text, new Date(msg.timestamp)]
      );
    }
  }

  // Cleanup Redis
  await redis.del(`call:${call_sid}`);

  res.sendStatus(200);
});

// ============================================
// API - Lancement de campagne
// ============================================
app.post('/api/campaigns/:id/launch', async (req, res) => {
  const { id } = req.params;

  // Récupération campagne + contacts
  const campaign = await db.query('SELECT * FROM campaigns WHERE id = $1', [id]);
  const contacts = await db.query(
    'SELECT * FROM contacts WHERE campaign_id = $1 AND status = $2',
    [id, 'pending']
  );

  // Lancement asynchrone (Celery ou simple Promise.all)
  const launchPromises = contacts.rows.map(async (contact) => {
    // Call Jambonz REST API
    const response = await axios.post(
      `https://api.jambonz.org/v1/Accounts/${process.env.JAMBONZ_ACCOUNT_SID}/Calls`,
      {
        to: contact.phone_number,
        from: campaign.rows[0].caller_id,
        application_sid: process.env.JAMBONZ_APP_SID,
        webhook: {
          url: `${process.env.WEBHOOK_BASE_URL}/call-webhook`,
          method: 'POST'
        },
        tag: {
          campaign_id: id,
          contact_id: contact.id
        }
      },
      {
        headers: {
          'Authorization': `Bearer ${process.env.JAMBONZ_API_TOKEN}`
        }
      }
    );

    // Enregistrement Call
    await db.query(
      'INSERT INTO calls (call_sid, campaign_id, contact_id, status) VALUES ($1, $2, $3, $4)',
      [response.data.sid, id, contact.id, 'initiated']
    );

    // Rate limiting
    await new Promise(resolve => setTimeout(resolve, 5000));
  });

  await Promise.all(launchPromises);

  res.json({ status: 'launched', count: contacts.rows.length });
});

app.listen(3000, () => {
  console.log('Jambonz webhook app listening on port 3000');
});
```

### 8.2 Scenario Manager (adaptation V3)

```javascript
// scenario_manager.js
class ScenarioManager {
  constructor() {
    this.scenarios = new Map();
  }

  async loadScenario(scenarioName) {
    // Cache
    if (this.scenarios.has(scenarioName)) {
      return this.scenarios.get(scenarioName);
    }

    // Chargement fichier JSON (même format que V3)
    const fs = require('fs').promises;
    const data = await fs.readFile(`./scenarios/${scenarioName}.json`, 'utf8');
    const scenario = JSON.parse(data);

    this.scenarios.set(scenarioName, scenario);
    return scenario;
  }

  async getVerbsForStep(scenario, stepId, context) {
    const step = scenario.steps[stepId];

    if (!step) {
      throw new Error(`Step ${stepId} not found in scenario`);
    }

    const verbs = [];

    // Audio playback
    if (step.audio_type === 'audio') {
      // Fichier audio préenregistré
      verbs.push({
        verb: 'say',
        audio_file: this._getAudioUrl(step.audio_file, scenario.metadata.voice)
      });
    } else if (step.audio_type === 'tts') {
      // TTS dynamique
      const text = this._replaceVariables(step.message_text, context);
      verbs.push({
        verb: 'say',
        text: text,
        synthesizer: {
          vendor: 'elevenlabs',
          voice: this._getVoiceId(scenario.metadata.voice),
          language: 'fr-FR'
        }
      });
    }

    // Gather user input (sauf si step finale)
    if (!stepId.startsWith('Bye_')) {
      verbs.push({
        verb: 'gather',
        input: ['speech'],
        timeout: 5,
        actionHook: `/handle-step/${stepId}`,
        recognizer: {
          vendor: 'google',
          language: 'fr-FR',
          hints: this._getHintsForStep(step)
        }
      });
    }

    return verbs;
  }

  _replaceVariables(text, context) {
    return text.replace(/\{\{(\w+)\}\}/g, (match, key) => {
      return context[key] || match;
    });
  }

  _getAudioUrl(filename, voice) {
    // Conversion chemin FreeSWITCH → URL HTTP
    return `https://your-cdn.com/sounds/${voice}/${filename}`;
  }

  _getVoiceId(voiceName) {
    const voiceMap = {
      'julie': 'elevenlabs-julie-id',
      'thomas': 'elevenlabs-thomas-id'
    };
    return voiceMap[voiceName] || voiceMap['julie'];
  }

  _getHintsForStep(step) {
    // Suggestions pour améliorer reconnaissance
    const hints = ['oui', 'non', 'peut-être'];

    if (step.intent_mapping) {
      // Ajouter keywords liés aux intents
      Object.keys(step.intent_mapping).forEach(intent => {
        if (intent === 'affirm') hints.push('oui', 'd\'accord', 'ok');
        if (intent === 'deny') hints.push('non', 'jamais', 'pas intéressé');
      });
    }

    return hints;
  }
}

module.exports = ScenarioManager;
```

### 8.3 Campaign Launcher (Celery alternative Node.js)

```javascript
// campaign_launcher.js
const axios = require('axios');
const { Pool } = require('pg');

class CampaignLauncher {
  constructor(dbConfig, jambonzConfig) {
    this.db = new Pool(dbConfig);
    this.jambonz = jambonzConfig;
  }

  async launchCampaign(campaignId, options = {}) {
    const {
      maxConcurrent = 10,
      callsPerSecond = 2,
      retryFailed = false
    } = options;

    // Récupération campagne
    const campaign = await this.db.query(
      'SELECT * FROM campaigns WHERE id = $1',
      [campaignId]
    );

    if (campaign.rows.length === 0) {
      throw new Error(`Campaign ${campaignId} not found`);
    }

    // Récupération contacts
    const statusFilter = retryFailed
      ? ['pending', 'failed']
      : ['pending'];

    const contacts = await this.db.query(
      'SELECT * FROM contacts WHERE campaign_id = $1 AND status = ANY($2) ORDER BY priority DESC',
      [campaignId, statusFilter]
    );

    console.log(`Launching campaign ${campaignId}: ${contacts.rows.length} contacts`);

    // Update campaign status
    await this.db.query(
      'UPDATE campaigns SET status = $1, started_at = NOW() WHERE id = $2',
      ['running', campaignId]
    );

    // Lancement par batches avec rate limiting
    const batchSize = maxConcurrent;
    const delayMs = 1000 / callsPerSecond;

    for (let i = 0; i < contacts.rows.length; i += batchSize) {
      const batch = contacts.rows.slice(i, i + batchSize);

      await Promise.all(
        batch.map((contact, idx) =>
          this._launchCall(campaign.rows[0], contact, idx * delayMs)
        )
      );
    }

    // Update campaign status
    await this.db.query(
      'UPDATE campaigns SET status = $1, completed_at = NOW() WHERE id = $2',
      ['completed', campaignId]
    );

    console.log(`Campaign ${campaignId} completed`);
  }

  async _launchCall(campaign, contact, delayMs) {
    // Rate limiting delay
    if (delayMs > 0) {
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }

    try {
      // Call Jambonz REST API
      const response = await axios.post(
        `${this.jambonz.apiUrl}/v1/Accounts/${this.jambonz.accountSid}/Calls`,
        {
          to: contact.phone_number,
          from: campaign.caller_id,
          application_sid: this.jambonz.applicationSid,
          webhook: {
            url: `${this.jambonz.webhookBaseUrl}/call-webhook`,
            method: 'POST'
          },
          tag: {
            campaign_id: campaign.id,
            contact_id: contact.id
          }
        },
        {
          headers: {
            'Authorization': `Bearer ${this.jambonz.apiToken}`
          }
        }
      );

      const callSid = response.data.sid;

      // Enregistrement Call
      await this.db.query(
        'INSERT INTO calls (call_sid, campaign_id, contact_id, status, created_at) VALUES ($1, $2, $3, $4, NOW())',
        [callSid, campaign.id, contact.id, 'initiated']
      );

      // Update contact status
      await this.db.query(
        'UPDATE contacts SET status = $1, last_call_at = NOW() WHERE id = $2',
        ['called', contact.id]
      );

      console.log(`✓ Call initiated: ${contact.phone_number} (${callSid})`);

    } catch (error) {
      console.error(`✗ Failed to launch call for ${contact.phone_number}:`, error.message);

      // Enregistrement erreur
      await this.db.query(
        'INSERT INTO calls (campaign_id, contact_id, status, error, created_at) VALUES ($1, $2, $3, $4, NOW())',
        [campaign.id, contact.id, 'failed', error.message]
      );
    }
  }
}

// Usage
const launcher = new CampaignLauncher(
  {
    host: 'localhost',
    database: 'minibot',
    user: 'postgres',
    password: 'password'
  },
  {
    apiUrl: 'https://api.jambonz.org',
    accountSid: process.env.JAMBONZ_ACCOUNT_SID,
    applicationSid: process.env.JAMBONZ_APP_SID,
    apiToken: process.env.JAMBONZ_API_TOKEN,
    webhookBaseUrl: process.env.WEBHOOK_BASE_URL
  }
);

// Lancement
launcher.launchCampaign(1, {
  maxConcurrent: 10,
  callsPerSecond: 2
});
```

---

## 9. Risques et limitations

### 9.1 Risques techniques

#### 🔴 RISQUE CRITIQUE: Dépendance plateforme
**Description:** Le système devient dépendant de Jambonz
**Impact:**
- Si Jambonz a un bug bloquant → système down
- Si Jambonz n'évolue pas → features bloquées
- Si projet Jambonz abandonné → migration forcée

**Mitigation:**
- Jambonz est open-source → possibilité de fork
- Architecture webhook = découplage possible
- Garder FreeSWITCH V3 comme backup 6 mois

#### 🟡 RISQUE: Latence webhooks
**Description:** Chaque interaction = HTTP request
**Impact:**
- Latence added vs. système in-process
- Possibles timeouts si serveur webhook lent

**Mitigation:**
- Déployer webhook app proche de Jambonz (même région)
- Utiliser WebSocket API au lieu de webhooks HTTP
- Optimiser DB queries (indexing, caching Redis)

#### 🟡 RISQUE: Courbe d'apprentissage
**Description:** Équipe doit apprendre nouveau paradigme
**Impact:**
- Développement initial plus lent
- Possibles erreurs de conception

**Mitigation:**
- POC approfondi (phase 1)
- Formation équipe sur Jambonz
- Documentation interne complète

#### 🟡 RISQUE: Qualité ASR/TTS self-hosted
**Description:** Si utilisation Vosk/Coqui (économie), qualité peut être inférieure à Google/AWS
**Impact:**
- Transcriptions moins précises
- Voix TTS moins naturelles
- Barge-in moins réactif

**Mitigation:**
- Tests comparatifs POC
- Budget pour providers cloud si nécessaire
- Hybrid approach possible (ASR cloud + TTS local)

### 9.2 Limitations identifiées

#### ❌ Pas de système de campagne intégré
Jambonz n'a pas de campaign manager natif comme les solutions contact center.

**Workaround:**
- Développer notre propre système (Celery/Node.js)
- Alternative: Intégrer avec Vicidial ou autre dialer

#### ❌ State management externe requis
Les webhooks Jambonz sont stateless.

**Workaround:**
- Redis pour state de session
- PostgreSQL pour persistance longue

#### ❌ Moins de contrôle bas-niveau
Impossible de modifier le comportement core de Jambonz sans fork.

**Impact:**
- Si feature spécifique nécessaire non disponible
- Dépend de roadmap Jambonz

#### ❌ Documentation parfois incomplète
Jambonz est jeune (2020), documentation en évolution.

**Mitigation:**
- Communauté active (Slack, GitHub)
- Code source disponible
- Exemples dans GitHub

---

## 10. Recommandations

### 10.1 Recommandation finale

**✅ RECOMMANDÉ: Migrer vers Jambonz**

**Justifications:**

1. **Résout le problème CRITIQUE d'écho acoustique**
   - AEC intégré = clients peuvent utiliser haut-parleur
   - Bloquant production actuellement

2. **Simplification massive architecture**
   - 60-70% réduction de code
   - Maintenance facilitée
   - Moins de bugs potentiels

3. **Meilleure scalabilité**
   - Architecture distribuée native
   - Load balancing automatique

4. **Qualité audio améliorée**
   - Possibilité d'utiliser meilleurs providers ASR/TTS
   - WebRTC natif

5. **ROI positif**
   - Temps dev économisé > coût migration
   - Moins de maintenance = plus de features

### 10.2 Approche recommandée

#### Phase 1: POC (2 semaines)
- Setup Jambonz local Docker
- Test appel sortant simple
- Validation AMD, barge-in, AEC
- **GO/NO-GO décision**

#### Phase 2: Migration progressive (4 semaines)
- Développement webhook app
- Migration NLP/Objection matcher
- Migration scénarios
- Tests complets

#### Phase 3: Production parallèle (2 semaines)
- Déploiement Jambonz production
- Tests avec vraies campagnes (petit volume)
- Comparaison qualité V3 vs Jambonz

#### Phase 4: Cutover (1 semaine)
- Migration complète
- Désactivation V3 (keep backup)

**Total: 9 semaines (2 mois)**

### 10.3 Checklist décision

Avant de commencer migration, valider:

- [ ] POC Jambonz réussi (appel + AMD + barge-in + AEC)
- [ ] Budget infrastructure validé
- [ ] Équipe formée sur Jambonz basics
- [ ] Plan de rollback défini (keep V3 6 mois)
- [ ] Stratégie ASR/TTS choisie (self-hosted vs cloud)
- [ ] Architecture webhook app validée
- [ ] State management strategy définie (Redis)
- [ ] Campaign launcher design validé

### 10.4 Alternatives considérées

#### Alternative 1: Rester sur FreeSWITCH V3
**Avantages:**
- Pas de migration
- Contrôle total
- Stack connue

**Inconvénients:**
- ❌ Problème AEC non résolu (BLOQUANT)
- ❌ Complexité maintenance
- ❌ Pas de simplification

**Verdict: NON RECOMMANDÉ** (problème AEC bloquant)

#### Alternative 2: FreeSWITCH + Jambonz features custom
**Approche:**
- Garder FreeSWITCH
- Ajouter AEC module
- Refactorer architecture

**Inconvénients:**
- Même complexité
- Temps dev > migration Jambonz
- Pas de bénéfice simplification

**Verdict: NON RECOMMANDÉ** (plus de travail, moins de gains)

#### Alternative 3: Twilio/Vonage
**Avantages:**
- Solutions enterprise éprouvées
- Support commercial
- Documentation complète

**Inconvénients:**
- ❌ Coûts très élevés ($1-2/min ASR+TTS)
- ❌ Vendor lock-in
- ❌ Moins de flexibilité

**Verdict: NON RECOMMANDÉ** (coûts prohibitifs)

### 10.5 Métriques de succès post-migration

Définir KPIs pour évaluer succès migration:

#### Qualité technique
- ✅ **AEC effectiveness**: 0% faux barge-in avec haut-parleur
- ✅ **Transcription accuracy**: >= V3 (WER < 10%)
- ✅ **Barge-in latency**: < 500ms
- ✅ **System uptime**: >= 99.5%

#### Performance
- ✅ **Concurrent calls capacity**: >= 100 simultaneous
- ✅ **Webhook latency p95**: < 200ms
- ✅ **Call setup time**: < 3s

#### Business
- ✅ **Contact rate**: >= V3 (% humans reached)
- ✅ **Qualification rate**: >= V3 (% qualified leads)
- ✅ **Cost per call**: <= V3 + 20%

#### Maintenance
- ✅ **Bug frequency**: < V3
- ✅ **Time to fix bugs**: < V3
- ✅ **Deployment frequency**: >= 1/week

---

## Conclusion

La migration de MiniBotPanel V3 vers Jambonz est **fortement recommandée**.

**Bénéfices principaux:**
1. ✅ Résolution du problème critique d'écho acoustique (AEC)
2. ✅ Simplification massive de l'architecture (60-70% moins de code)
3. ✅ Meilleure scalabilité et maintenance
4. ✅ Qualité audio améliorée
5. ✅ Barge-in et AMD natifs

**Investissement:**
- 9 semaines de développement
- POC préalable pour validation
- ROI positif grâce à réduction maintenance

**Prochaine étape:** Lancer POC Jambonz (2 semaines) pour validation technique définitive.

---

**Document créé le:** 2025-11-09
**Basé sur:** Analyse complète MiniBotPanel V3 (8,000+ lignes) + Recherche Jambonz approfondie
**Contact:** [Votre équipe développement]
