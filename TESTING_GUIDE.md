# 🧪 MiniBotPanel v3 FINAL - Testing Guide

**Phase 9 - Validation complète des fonctionnalités Phases 1-8**

Ce guide détaille les tests pour valider toutes les nouvelles fonctionnalités de la v3 FINAL.

---

## 📋 Vue d'ensemble des tests

| # | Test | Phase | Durée | Difficulté |
|---|------|-------|-------|------------|
| 1 | Background Audio Loop | 2 | 5 min | ⭐ Facile |
| 2 | YouTube Extract Multi-locuteurs | 3 | 15 min | ⭐⭐ Moyen |
| 3 | Clone Voice + 150 TTS | 4 | 30 min | ⭐⭐⭐ Avancé |
| 4 | Agent Autonome Complet | 6-7 | 20 min | ⭐⭐⭐ Avancé |
| 5 | Create Scenario Workflow | 7 | 10 min | ⭐⭐ Moyen |

**Temps total**: ~1h30

---

## 🎵 Test 1: Background Audio Loop (Phase 2)

**Objectif**: Vérifier que l'audio de fond tourne en boucle infinie pendant tout l'appel.

### Préparation

1. **Préparer un fichier audio court** (10-15s) pour faciliter la détection du loop:

```bash
# Créer dossier si nécessaire
mkdir -p audio/background/

# Copier un audio court (ou générer)
cp audio/samples/short_ambient.wav audio/background/test_loop_10s.wav

# Vérifier format
ffprobe audio/background/test_loop_10s.wav
# Doit être: 22050Hz, mono, WAV
```

2. **Créer scénario de test**:

```json
// scenarios/test_background_loop.json
{
  "name": "Test Background Loop",
  "agent_mode": false,
  "background_audio": "test_loop_10s.wav",
  "steps": [
    {
      "name": "Hello",
      "type": "speak",
      "message": "Bonjour, ceci est un test de 60 secondes pour vérifier le loop.",
      "audio_path": "test/hello_60s.wav"
    }
  ]
}
```

3. **Générer audio principal long** (60s) pour laisser le background tourner:

```bash
# Utiliser TTS pour générer 60s de silence avec message court au début
python -c "
from system.services.tts_service import TTSService
import time

tts = TTSService()
text = 'Bonjour, test en cours. ' + (' Veuillez patienter. ' * 20)
tts.generate_audio(text, 'audio/test/hello_60s.wav')
"
```

### Exécution du test

```bash
# Lancer robot
python run_minibot.py
```

**Via API ou Panel Web**, lancer appel avec scénario `test_background_loop`.

**Ou via CLI de test**:

```python
# test_background_loop.py
from system.robot_freeswitch import RobotFreeSWITCH
import time

robot = RobotFreeSWITCH()

# Appel de test (vers numéro safe ou SIP test)
call_uuid = robot.originate_call(
    phone_number="+33123456789",  # Numéro test
    scenario_name="test_background_loop"
)

print(f"Appel lancé: {call_uuid}")
print("Laissez tourner 60s pour vérifier le loop...")
time.sleep(65)

# Vérifier logs
print(robot.get_call_logs(call_uuid))
```

### Critères de validation

✅ **PASS** si:
- Background audio démarre dès le début de l'appel
- Audio tourne en boucle continue (pas de coupure entre répétitions)
- Volume background à -8dB (audible mais pas couvrant)
- Loop continue pendant toute la durée (60s+)

❌ **FAIL** si:
- Audio s'arrête après 1ère lecture
- Coupure/silence entre loops
- Volume incorrect (trop fort/faible)

**Logs attendus**:

```
[INFO] Call 550e8400 OUTBOUND → +33123456789
[INFO] Background audio started: test_loop_10s.wav (-8dB)
[DEBUG] FreeSWITCH uuid_displace: limit=0 (infinite loop)
[INFO] Playing main audio: hello_60s.wav
[INFO] Background still active after 30s
[INFO] Background still active after 60s
[INFO] Call ended - Background audio stopped
```

---

## 🎙️ Test 2: YouTube Extract Multi-locuteurs (Phase 3)

**Objectif**: Extraire et isoler un locuteur spécifique depuis vidéo YouTube multi-locuteurs.

### Préparation

1. **Choisir vidéo YouTube de test** avec plusieurs locuteurs clairs:

**Suggestions**:
- Interview 2 personnes (facile à distinguer)
- Podcast avec animateur + invité
- Débat politique (3-4 locuteurs)

**Exemple**: Interview tech (10-15 min durée)

```
URL test: https://www.youtube.com/watch?v=EXEMPLE_VIDEO_ID
```

2. **Vérifier HuggingFace token** configuré:

```bash
grep HUGGINGFACE_TOKEN .env
# Doit afficher: HUGGINGFACE_TOKEN=hf_...

# Vérifier accès pyannote
python -c "
from pyannote.audio import Pipeline
pipeline = Pipeline.from_pretrained(
    'pyannote/speaker-diarization-3.1',
    use_auth_token='VOTRE_TOKEN'
)
print('✅ Token valide')
"
```

### Exécution du test

```bash
python youtube_extract.py
```

**Étapes interactives**:

1. **URL YouTube**: Coller votre URL de test
2. **Nom du locuteur**: `invité_tech` (ou nom de votre choix)
3. **Sélection locuteur**: Le script détecte automatiquement X locuteurs

**Exemple d'output**:

```
🎬 YouTube Voice Extractor - MiniBotPanel v3

📥 Téléchargement audio...
✅ Audio téléchargé: /tmp/youtube_abc123.wav

🔍 Analyse speaker diarization...
   Modèle: pyannote/speaker-diarization-3.1

⏳ Diarization en cours (peut prendre 2-5 min pour 15 min audio)...

✅ Diarization terminée!

🔊 Locuteurs détectés: 2
   • Locuteur A: 7m 23s (52%)
   • Locuteur B: 6m 12s (48%)

Quel locuteur voulez-vous extraire? (A/B): B

📊 Découpage intelligent...
   • 47 segments du Locuteur B détectés
   • Filtrage segments 4-10s...
   • 31 segments conservés

🎵 Extraction + nettoyage audio...
   • Extraction voix (audio-separator)
   • Réduction bruit (noisereduce)
   • Normalisation -20dB
   • Conversion 22050Hz mono

✅ Voix extraite avec succès!

📂 Fichiers créés:
   voices/invité_tech/raw/chunk_001.wav (4.2s)
   voices/invité_tech/raw/chunk_002.wav (7.8s)
   ...
   voices/invité_tech/raw/chunk_031.wav (5.1s)

📊 Statistiques:
   • Total audio extrait: 3m 47s
   • Qualité moyenne: 31 chunks 4-10s
   • Prêt pour clonage: ✅

💡 Prochaine étape: Cloner cette voix
   python clone_voice.py --voice invité_tech
```

### Critères de validation

✅ **PASS** si:
- Diarization détecte tous les locuteurs (2-4 attendus)
- Segments extraits sont bien du locuteur sélectionné (vérif manuelle)
- Durée chunks entre 4-10s (95%+ des chunks)
- Audio nettoyé: pas de musique de fond, bruit réduit
- Format final: 22050Hz mono WAV

❌ **FAIL** si:
- Diarization échoue ou ne détecte qu'1 locuteur
- Mauvais locuteur extrait (confusion)
- Chunks trop courts (<3s) ou trop longs (>12s)
- Audio non nettoyé (musique/bruit présent)

**Vérification manuelle**:

```bash
# Écouter quelques chunks extraits
ffplay voices/invité_tech/raw/chunk_001.wav
ffplay voices/invité_tech/raw/chunk_015.wav
ffplay voices/invité_tech/raw/chunk_030.wav

# Vérifier format
ffprobe voices/invité_tech/raw/chunk_001.wav
# Doit afficher: 22050 Hz, 1 channels (mono), pcm_s16le
```

---

## 🗣️ Test 3: Clone Voice + 150 TTS (Phase 4)

**Objectif**: Cloner voix depuis chunks extraits + générer 150 fichiers TTS pour objections/FAQ.

### Préparation

1. **Utiliser voix extraite du Test 2** ou préparer manuellement:

```bash
# Si Test 2 effectué
ls -lh voices/invité_tech/raw/
# Doit contenir 20-50 fichiers WAV 4-10s

# OU utiliser voix existante
ls -lh voices/default/raw/
```

2. **Vérifier objections_database.py** à jour avec 80 entrées:

```bash
python -c "
from system.objections_database import (
    OBJECTIONS_GENERAL, FAQ_GENERAL,
    OBJECTIONS_FINANCE, FAQ_FINANCE,
    OBJECTIONS_CRYPTO, FAQ_CRYPTO,
    OBJECTIONS_ENERGIE, FAQ_ENERGIE
)

total = (len(OBJECTIONS_GENERAL) + len(FAQ_GENERAL) +
         len(OBJECTIONS_FINANCE) + len(FAQ_FINANCE) +
         len(OBJECTIONS_CRYPTO) + len(FAQ_CRYPTO) +
         len(OBJECTIONS_ENERGIE) + len(FAQ_ENERGIE))

print(f'Total entrées: {total}')
assert total == 80, 'Devrait avoir 80 entrées'
print('✅ Objections database OK')
"
```

### Exécution du test

#### Partie 1: Clonage voix

```bash
python clone_voice.py
```

**Étapes**:

1. **Sélection voix**: Choisir `invité_tech` (ou votre voix test)
2. **Analyse audio**: Le script analyse durée totale
3. **Détection mode**: Automatique selon durée
   - `<30s`: quick (qualité moyenne)
   - `30-120s`: standard (recommandé)
   - `>120s`: fine-tuning (excellente qualité)

**Output attendu**:

```
🎤 Voice Cloning Manager - MiniBotPanel v3

📂 Voix disponibles:
   1. default (45 fichiers, 5m 32s)
   2. invité_tech (31 fichiers, 3m 47s)

Quelle voix cloner? (1-2): 2

📊 Analyse audio...
   • Total fichiers: 31
   • Durée totale: 3m 47s (227s)
   • Qualité: 31 chunks 4-10s

🔍 Détection mode clonage...
   ✅ Mode: FINE-TUNING (>120s → excellente qualité)

⚙️ Configuration Coqui XTTS v2:
   • Modèle: tts_models/multilingual/multi-dataset/xtts_v2
   • Fine-tuning: 500 epochs
   • Language: fr

🔥 Démarrage fine-tuning (peut prendre 10-20 min)...

Epoch [50/500]: loss=0.245
Epoch [100/500]: loss=0.189
Epoch [150/500]: loss=0.142
...
Epoch [500/500]: loss=0.028

✅ Fine-tuning terminé!

💾 Sauvegarde modèle: models/xtts_v2_invité_tech/

🧪 Test qualité (génération phrase test)...
   "Bonjour, ceci est un test de voix clonée."

✅ Voix clonée avec succès!
   Fichier test: voices/invité_tech/test_clone.wav

🔊 Écouter le test:
   ffplay voices/invité_tech/test_clone.wav
```

**Vérification manuelle qualité**:

```bash
# Écouter test clone
ffplay voices/invité_tech/test_clone.wav

# Comparer avec voix originale
ffplay voices/invité_tech/raw/chunk_001.wav

# Critères qualité:
# - Timbre similaire (hauteur, grain)
# - Prosodie naturelle (pas robotique)
# - Pas d'artefacts (craquements, distorsions)
```

#### Partie 2: Génération 150 TTS

```bash
# Générer TTS pour TOUTES les thématiques
python clone_voice.py --generate-tts invité_tech --all-themes

# OU pour 1 thématique spécifique
python clone_voice.py --generate-tts invité_tech --theme finance
```

**Output attendu**:

```
🎙️ Génération TTS pour objections/FAQ

📊 Configuration:
   • Voix: invité_tech
   • Thématiques: general, finance, crypto, energie (4)
   • Entrées totales: 80

🔄 Génération en cours...

[1/80] GENERAL/objection_pas_interesse.wav ✅ (2.3s)
[2/80] GENERAL/objection_rappeler.wav ✅ (1.8s)
[3/80] GENERAL/objection_pas_temps.wav ✅ (2.1s)
...
[80/80] ENERGIE/faq_panneaux.wav ✅ (4.7s)

✅ Génération terminée!

📂 Fichiers créés:
   audio/objections/general/objection_pas_interesse.wav
   audio/objections/general/faq_contact.wav
   ...
   audio/objections/energie/faq_panneaux.wav

📊 Statistiques:
   • Total généré: 80 fichiers
   • Durée moyenne: 2.8s
   • Taille totale: 47 MB
   • Échecs: 0
   • Temps total: 8m 23s

💡 Les audio_path sont automatiquement renseignés dans ObjectionEntry
```

### Critères de validation

✅ **PASS** si:
- Clonage réussit avec mode détecté correctement
- Test clone ressemble à voix originale (vérif manuelle)
- 80 fichiers TTS générés (100% succès)
- Durée fichiers cohérente avec texte (2-5s pour objections courtes)
- Format: 22050Hz mono WAV
- Qualité audio: naturelle, pas d'artefacts

❌ **FAIL** si:
- Fine-tuning échoue ou crash
- Test clone ne ressemble pas (timbre différent)
- Génération TTS <80 fichiers (échecs)
- Qualité médiocre (voix robotique, artefacts)

**Vérification finale**:

```bash
# Compter fichiers générés
find audio/objections -name "*.wav" | wc -l
# Doit afficher: 80

# Écouter échantillon thématiques
ffplay audio/objections/general/objection_pas_interesse.wav
ffplay audio/objections/finance/faq_credit.wav
ffplay audio/objections/crypto/objection_arnaque.wav
ffplay audio/objections/energie/faq_installation.wav

# Vérifier audio_path dans database
python -c "
from system.objections_database import OBJECTIONS_FINANCE

obj = OBJECTIONS_FINANCE[0]
print(f'Keywords: {obj.keywords}')
print(f'Audio path: {obj.audio_path}')
assert obj.audio_path is not None, 'audio_path devrait être renseigné'
print('✅ Audio paths OK')
"
```

---

## 🤖 Test 4: Agent Autonome Complet (Phase 6-7)

**Objectif**: Valider workflow complet agent autonome avec matcher→freestyle→rail→silences.

### Préparation

1. **Créer scénario de test agent** via `create_scenario.py`:

```bash
python create_scenario.py
```

**Configuration recommandée**:

```
Nom: test_agent_autonome
Agent autonome: Oui
Voix: invité_tech (ou default)
Thématique: finance
Téléprospecteur: Sophie Martin
Société: FinanceConseil
Background: corporate_ambient.wav

Questions (3 questions simples):
Q1: "Avez-vous déjà un crédit immobilier ?" (poids: 30%)
Q2: "Êtes-vous propriétaire ?" (poids: 40%)
Q3: "Souhaitez-vous réduire vos mensualités ?" (poids: 30%)

Qualification:
- Seuil LEAD: 70%
- Confirm_Time si LEAD

Rail généré:
["Hello", "Q1", "Q2", "Q3", "Is_Leads", "Confirm_Time", "Bye"]
```

2. **Vérifier cache + Ollama prewarm**:

```python
# Précharger cache
python -c "
from system.cache_manager import get_cache

cache = get_cache()

# Précharger scénario
import json
with open('scenarios/test_agent_autonome.json') as f:
    scenario = json.load(f)
    cache.set_scenario('test_agent_autonome', scenario)

# Précharger objections
from system.objections_database import get_objections_by_theme
objections = get_objections_by_theme('finance')
cache.set_objections('finance', objections)

cache.print_stats()
"

# Prewarm Ollama
python -c "
from system.services.ollama_nlp import OllamaNLP

nlp = OllamaNLP()
nlp.prewarm()
print('✅ Ollama prewarmed')
"
```

### Exécution du test

```bash
# Lancer robot
python run_minibot.py
```

**Créer campagne de test** avec **4 numéros** pour tester différents cas:

```csv
phone,first_name,last_name,scenario
+33601010101,Test,Affirm,test_agent_autonome
+33602020202,Test,Objection,test_agent_autonome
+33603030303,Test,Silence,test_agent_autonome
+33604040404,Test,Question,test_agent_autonome
```

**Via Panel Web**:
1. Campagnes → Nouvelle
2. Importer CSV ci-dessus
3. Lancer campagne

### Cas de test détaillés

#### Cas 1: Prospect affirmatif (lead attendu)

**Scénario**:
- Robot: "Bonjour, Sophie Martin de FinanceConseil..."
- Prospect: "Oui bonjour" → Intent: affirm
- Robot: "Avez-vous déjà un crédit immobilier?"
- Prospect: "Oui j'ai un crédit" → Intent: affirm (+30%)
- Robot: "Êtes-vous propriétaire ?"
- Prospect: "Oui" → Intent: affirm (+40% = 70% total)
- Robot: "Souhaitez-vous réduire vos mensualités ?"
- Prospect: "Oui tout à fait" → Intent: affirm (+30% = 100%)
- Is_Leads: Score 100% ≥ 70% → **LEAD**
- Confirm_Time: Proposition RDV
- Prospect: "Oui d'accord"
- Bye: Remerciements

**Résultat attendu**: `call_status=LEAD`, `lead_score=100.0`

#### Cas 2: Prospect avec objection (matcher rapide <50ms)

**Scénario**:
- Robot: "Avez-vous déjà un crédit immobilier?"
- Prospect: "Non, pas intéressé" → Détection objection
- Matcher: Cherche keywords ["pas intéressé"]
- Match trouvé (42ms): `objection_pas_interesse`
- Robot: Joue audio `objections/general/objection_pas_interesse.wav`
- Robot: Question rail retour "Ça vous parle ?"
- Prospect: "Oui pourquoi pas" → Intent: affirm
- Robot: Continue rail → Q2

**Logs attendus**:

```
[INFO] Step: Q1 → Playing audio
[INFO] ASR detected: "non, pas intéressé"
[INFO] Objection detection triggered
[DEBUG] Objection matcher: searching keywords...
[INFO] Match found: objection_pas_interesse (score: 0.85, 42ms)
[INFO] Playing objection audio: objections/general/objection_pas_interesse.wav
[DEBUG] Rail return question: "Ça vous parle ?"
[INFO] ASR detected: "oui pourquoi pas"
[INFO] Intent: affirm → Returning to rail
[INFO] Next step: Q2
```

**Résultat attendu**: Objection traitée, retour au rail, autonomous_turns=1

#### Cas 3: Prospect avec question (freestyle fallback 2-3s)

**Scénario**:
- Robot: "Avez-vous déjà un crédit immobilier?"
- Prospect: "C'est quoi exactement votre offre ?" → Question non pré-enregistrée
- Matcher: Aucun match (pas dans keywords)
- Fallback: Freestyle AI (2-3s)
- Robot: Génère réponse IA + question retour rail
- Prospect: "Ok compris" → Intent: affirm
- Robot: Continue rail

**Logs attendus**:

```
[INFO] ASR detected: "c'est quoi exactement votre offre"
[INFO] Objection detection triggered
[DEBUG] Objection matcher: no match found
[INFO] Fallback: Freestyle AI (context: finance)
[DEBUG] Ollama generating response... (2.3s)
[INFO] Freestyle response generated
[DEBUG] Rail return question: "Vous me suivez ?"
[INFO] TTS generating combined response... (800ms)
[INFO] Playing freestyle + rail return audio
[INFO] ASR detected: "ok compris"
[INFO] Intent: affirm → Returning to rail
[INFO] Next step: Q2
```

**Résultat attendu**: Freestyle utilisé, latence 2-3s acceptable, retour au rail

#### Cas 4: Prospect silencieux (2 silences → hangup)

**Scénario**:
- Robot: "Avez-vous déjà un crédit immobilier?"
- Prospect: *silence* (timeout 8s)
- Robot: "Vous êtes toujours là ?" (relance automatique)
- Prospect: *silence* (timeout 8s)
- Robot: Détecte 2 silences consécutifs
- Robot: "Je vous laisse, bonne journée" + hangup

**Logs attendus**:

```
[INFO] Step: Q1 → Playing audio
[WARN] ASR timeout: no speech detected (8s)
[INFO] Silence detected (1/2)
[INFO] Playing silence prompt: "Vous êtes toujours là ?"
[WARN] ASR timeout: no speech detected (8s)
[INFO] Silence detected (2/2)
[WARN] 2 consecutive silences → Ending call
[INFO] Playing goodbye: "Je vous laisse, bonne journée"
[INFO] Call status: NO_ANSWER
[INFO] Call ended
```

**Résultat attendu**: `call_status=NO_ANSWER`, `end_reason=consecutive_silences`

### Critères de validation globale

✅ **PASS** si:
- **Cas 1**: LEAD avec score correct (70-100%)
- **Cas 2**: Objection matchée <50ms + retour rail
- **Cas 3**: Freestyle fonctionne (2-3s) + retour rail
- **Cas 4**: 2 silences → hangup NO_ANSWER
- Rail navigation correcte (Hello→Q1→Q2→Q3→Is_Leads→Confirm→Bye)
- Max autonomous_turns=2 respecté (pas de boucle infinie)
- Cache hit rate >80% (scenarios + objections)
- Ollama latency <100ms après prewarm

❌ **FAIL** si:
- Qualification incorrecte (score faux)
- Objection matcher >100ms ou ne trouve pas
- Freestyle échoue ou timeout >5s
- 2 silences ne déclenchent pas hangup
- Rail cassé (étapes sautées/désordre)
- Boucle infinie objections (>2 autonomous_turns)

### Vérification post-test

```bash
# Statistiques base de données
psql -d minibot_db -c "
SELECT
    phone_number,
    call_status,
    lead_score,
    end_reason,
    duration_seconds
FROM calls
WHERE scenario_name = 'test_agent_autonome'
ORDER BY created_at DESC;
"

# Résultat attendu:
#  phone_number  | call_status | lead_score |     end_reason      | duration_seconds
# ---------------+-------------+------------+---------------------+------------------
#  +33601010101  | LEAD        | 100.0      | completed_confirmed | 180
#  +33602020202  | COMPLETED   | 40.0       | completed_no_lead   | 95
#  +33603030303  | NO_ANSWER   | 0.0        | consecutive_silences| 25
#  +33604040404  | COMPLETED   | 70.0       | completed_qualified | 120

# Statistiques cache
python -c "
from system.cache_manager import get_cache
cache = get_cache()
cache.print_stats()
"

# Résultat attendu:
# 🎬 SCENARIOS CACHE:
#   • Hit rate: 87.5%  (3 misses initiaux, puis hits)
#   • Cache size: 1/50
#
# 🛡️ OBJECTIONS CACHE:
#   • Hit rate: 91.2%
#   • Cache size: 1/20
#   • Themes: finance

# Statistiques Ollama
python -c "
from system.services.ollama_nlp import OllamaNLP
nlp = OllamaNLP()
stats = nlp.get_stats()
print(f'Ollama success rate: {stats[\"success_rate_pct\"]}%')
print(f'Avg latency: {stats[\"avg_latency_ms\"]:.0f}ms')
"

# Résultat attendu:
# Ollama success rate: 98.5%
# Avg latency: 87ms  (après prewarm)
```

---

## 🎬 Test 5: Create Scenario Workflow (Phase 7)

**Objectif**: Valider le nouveau workflow create_scenario.py pour agent autonome.

### Exécution du test

```bash
python create_scenario.py
```

### Étapes de validation

#### 1. Détection voix automatique

**Attendu**:

```
🎙️ Voix disponibles:
   1. default (45 fichiers)
   2. invité_tech (31 fichiers)
   3. sophie_clone (18 fichiers)

Quelle voix utiliser? (1-3):
```

✅ **PASS** si: Toutes les voix dans `voices/` détectées

#### 2. Sélection thématique

**Attendu**:

```
🛡️ Thématiques objections disponibles:
   1. general (20 entrées)
   2. finance (20 entrées)
   3. crypto (20 entrées)
   4. energie (20 entrées)

Quelle thématique? (1-4):
```

✅ **PASS** si: 4 thématiques avec 20 entrées chacune

#### 3. Configuration agent autonome

**Input test**: Créer scénario complet agent

```
Nom: test_workflow
Agent autonome: Oui
Voix: 2 (invité_tech)
Thématique: 2 (finance)
Téléprospecteur: Jean Dupont
Société: CreditPro
Background: corporate_modern.wav

Questions:
Q1: "Êtes-vous propriétaire de votre résidence principale ?"
    Type: affirm/deny
    Poids: 35%

Q2: "Avez-vous un crédit en cours ?"
    Type: affirm/deny
    Poids: 35%

Q3: "Votre crédit a-t-il plus de 2 ans ?"
    Type: affirm/deny
    Poids: 30%

(Total: 100%)

Qualification:
Seuil LEAD: 70%
```

**Output attendu**:

```
✅ Scénario créé: test_workflow

📊 Configuration:
   • Agent mode: ✅ Activé
   • Voix: invité_tech
   • Thématique: finance
   • Téléprospecteur: Jean Dupont
   • Société: CreditPro
   • Background: corporate_modern.wav

🚉 Rail de navigation:
   Hello → Q1 → Q2 → Q3 → Is_Leads → Confirm_Time → Bye

🎯 Qualification:
   • Seuil LEAD: 70%
   • Poids total: 100%
   • Steps déterminants: Q1 (35%), Q2 (35%), Q3 (30%)

📂 Fichier sauvegardé:
   scenarios/test_workflow.json

💡 Prochaines étapes:
   1. python generate_audio.py test_workflow
   2. Créer campagne avec ce scénario
```

#### 4. Validation JSON généré

```bash
# Lire scénario généré
cat scenarios/test_workflow.json | python -m json.tool
```

**Structure attendue**:

```json
{
  "name": "test_workflow",
  "agent_mode": true,
  "theme": "finance",
  "voice": "invité_tech",
  "background_audio": "corporate_modern.wav",
  "telemarketer_name": "Jean Dupont",
  "company_name": "CreditPro",
  "rail": [
    "Hello",
    "Q1",
    "Q2",
    "Q3",
    "Is_Leads",
    "Confirm_Time",
    "Bye"
  ],
  "qualification": {
    "threshold": 70,
    "weights": {
      "Q1": 35,
      "Q2": 35,
      "Q3": 30
    }
  },
  "steps": [
    {
      "name": "Hello",
      "type": "speak",
      "message": "Bonjour {{first_name}}, Jean Dupont de CreditPro...",
      "next_steps": {
        "affirm": "Q1",
        "deny": "Bye"
      },
      "max_autonomous_turns": 2
    },
    {
      "name": "Q1",
      "type": "ask",
      "question": "Êtes-vous propriétaire de votre résidence principale ?",
      "is_determinant": true,
      "qualification_weight": 35,
      "max_autonomous_turns": 2,
      "next_steps": {
        "affirm": "Q2",
        "deny": "Q2"
      }
    },
    ...
  ]
}
```

✅ **PASS** si:
- `agent_mode: true`
- `theme` correspond à sélection
- `voice` correspond à sélection
- `rail` complet avec 7 étapes (Hello→Q1-Q3→Is_Leads→Confirm→Bye)
- `qualification.threshold` = 70
- Somme `qualification.weights` = 100
- Chaque step a `max_autonomous_turns: 2`
- Steps déterminants ont `is_determinant: true` + `qualification_weight`

### Critères de validation globale

✅ **PASS** si:
- Détection automatique voix fonctionne
- 4 thématiques disponibles
- Scénario JSON généré valide
- Rail complet avec agent_mode=true
- Qualification cumulative configurée (poids = 100%)
- Variables {{first_name}}, {{company_name}} injectées
- Fichier sauvegardé dans `scenarios/`

❌ **FAIL** si:
- Voix non détectées ou erreur
- Thématiques manquantes (<4)
- JSON invalide ou champs manquants
- Rail incomplet ou ordre incorrect
- Poids qualification ≠ 100%

### Test intégration complète

**Lancer appel avec scénario généré**:

```bash
# Générer audio TTS pour toutes les étapes
python generate_audio.py test_workflow

# Créer campagne test
curl -X POST http://localhost:5000/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Workflow",
    "scenario_name": "test_workflow",
    "phone_list": [
      {"phone": "+33601010101", "first_name": "Test"}
    ]
  }'

# Vérifier appel fonctionne
tail -f logs/minibot.log
```

✅ **PASS** si: Appel se déroule normalement avec agent autonome activé

---

## 📊 Récapitulatif Final

### Checklist complète

- [ ] **Test 1**: Background audio loop infini confirmé
- [ ] **Test 2**: YouTube extract multi-locuteurs avec diarization
- [ ] **Test 3**: Clone voice + 80 TTS générés
- [ ] **Test 4**: Agent autonome complet (4 cas validés)
- [ ] **Test 5**: Create scenario workflow agent autonome

### Métriques de succès

| Métrique | Cible | Tolérance |
|----------|-------|-----------|
| Background audio loop | Infini | 0 coupure |
| Diarization précision | >90% | Locuteur correct |
| TTS générés | 80/80 | 100% succès |
| Objection matcher latency | <50ms | <100ms acceptable |
| Freestyle AI latency | 2-3s | <5s acceptable |
| Cache hit rate | >80% | >70% acceptable |
| Ollama latency (post-prewarm) | <100ms | <200ms acceptable |
| 2 silences → hangup | 100% | 0 faux positifs |
| Qualification score | Correct | ±5% tolérance |

### Rapport de test (template)

```markdown
# MiniBotPanel v3 FINAL - Test Report

**Date**: 2025-01-XX
**Testeur**: [Nom]
**Version**: v3 FINAL (Phases 1-8)

## Résultats

### Test 1: Background Audio Loop
- ✅ PASS / ❌ FAIL
- Notes: ...

### Test 2: YouTube Extract
- ✅ PASS / ❌ FAIL
- Vidéo test: [URL]
- Locuteurs détectés: X
- Notes: ...

### Test 3: Clone Voice + TTS
- ✅ PASS / ❌ FAIL
- Voix clonée: [nom]
- TTS générés: X/80
- Notes: ...

### Test 4: Agent Autonome
- Cas 1 (affirm): ✅ PASS / ❌ FAIL
- Cas 2 (objection): ✅ PASS / ❌ FAIL
- Cas 3 (freestyle): ✅ PASS / ❌ FAIL
- Cas 4 (silences): ✅ PASS / ❌ FAIL
- Notes: ...

### Test 5: Create Scenario
- ✅ PASS / ❌ FAIL
- Scénario généré: [nom]
- Notes: ...

## Métriques

- Objection matcher avg latency: XX ms
- Freestyle AI avg latency: X.Xs
- Cache hit rate scenarios: XX%
- Cache hit rate objections: XX%
- Ollama avg latency: XX ms

## Bugs identifiés

1. [Description bug si trouvé]
2. ...

## Recommandations

1. [Améliorations suggérées]
2. ...

## Conclusion

✅ Tous les tests PASS - Production ready
❌ Tests échoués - Corrections nécessaires
```

---

## 🆘 Dépannage Tests

### Test 1: Background ne loop pas

**Causes possibles**:
- `limit` != 0 dans uuid_displace
- Audio mal formaté

**Solution**:
```bash
# Vérifier code
grep "uuid_displace" system/robot_freeswitch.py
# Doit avoir: limit=0

# Vérifier format audio
ffprobe audio/background/test_loop_10s.wav
# Convertir si nécessaire
python setup_audio.py --convert audio/background/test_loop_10s.wav
```

### Test 2: Diarization échoue

**Causes possibles**:
- HuggingFace token invalide
- Vidéo 1 seul locuteur

**Solution**:
```bash
# Vérifier token
python -c "
from pyannote.audio import Pipeline
pipeline = Pipeline.from_pretrained(
    'pyannote/speaker-diarization-3.1',
    use_auth_token='VOTRE_TOKEN'
)
"

# Tester vidéo différente avec 2+ locuteurs clairs
```

### Test 3: Fine-tuning échoue

**Causes possibles**:
- Pas assez d'audio (<30s)
- GPU non disponible (normal, utilise CPU)

**Solution**:
```bash
# Vérifier durée totale
ls -lh voices/nom_voix/raw/ | wc -l
# Doit avoir 20+ fichiers pour >120s

# Si <30s, ajouter plus d'audio ou utiliser mode quick
```

### Test 4: Objection matcher ne trouve rien

**Causes possibles**:
- Thématique incorrecte
- Keywords trop spécifiques

**Solution**:
```python
# Vérifier thématique scenario
import json
with open("scenarios/test_agent_autonome.json") as f:
    scenario = json.load(f)
    print(f"Theme: {scenario.get('theme')}")

# Vérifier objections chargées
from system.objection_matcher import ObjectionMatcher
matcher = ObjectionMatcher.load_objections_for_theme("finance")
print(f"Objections: {len(matcher.objections)}")
```

### Test 5: Create scenario crash

**Causes possibles**:
- Poids total ≠ 100%
- Voix inexistante

**Solution**:
```bash
# Vérifier voix disponibles
ls -d voices/*/
# Doit lister toutes les voix

# Vérifier thématiques
python -c "
from system.objections_database import *
print('GENERAL:', len(OBJECTIONS_GENERAL) + len(FAQ_GENERAL))
print('FINANCE:', len(OBJECTIONS_FINANCE) + len(FAQ_FINANCE))
"
```

---

*Testing Guide créé pour MiniBotPanel v3 FINAL - Phase 9*
