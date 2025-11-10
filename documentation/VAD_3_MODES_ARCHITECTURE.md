# Architecture VAD 3 Modes - Design Document

**Date:** 2025-11-10
**Version:** 1.0
**Auteur:** Claude Code + User

## 🎯 Objectif

Séparer la détection VAD en **3 modes distincts** avec des comportements optimisés selon le contexte :

1. **AMD Mode** : Answering Machine Detection
2. **PLAYING Mode** : Barge-in intelligent pendant que robot parle
3. **WAITING Mode** : End-of-speech detection pendant attente réponse

---

## 📊 Recherche Best Practices

### Sources
- Twilio AMD Documentation (2025)
- Retell AI VAD/Turn-Taking Best Practices
- Deepgram End-of-Speech Detection
- AWS Connect Outbound Campaigns Best Practices

### Paramètres Recommandés (Industry Standards)

| Paramètre | Valeur Standard | Notre Choix | Rationale |
|-----------|----------------|-------------|-----------|
| **AMD Timeout** | 4.0s (Twilio) | 3.0s | Optimisé pour FR, plus rapide |
| **AMD Min Speech** | N/A | 0.3s | Détection précoce |
| **Barge-in Threshold** | 2.5-3.0s | 2.5s | Filtre backchannels |
| **Backchannel Max** | N/A | 0.8s | "oui", "ok", "hum" |
| **Silence Reset** | N/A | 2.0s | Anti-accumulation |
| **End-of-Speech Silence** | 0.5-2.0s | 1.5s | Bon compromis |
| **Waiting Timeout** | 10-15s | 10.0s | Standard télémarketing |

---

## 🏗️ Architecture Détaillée

### **MODE 1: AMD (Answering Machine Detection)**

**Durée:** 3.0s
**Fonction:** `_monitor_vad_amd(call_uuid, record_file)`

**Workflow:**
```
1. Lancer uuid_record (enregistrer 3s)
2. Thread VAD surveille fichier en continu
3. Transcrire TOUT dès qu'audio détecté (pas de seuil)
4. À la fin des 3s:
   - Transcrire audio complet
   - NLP pour détecter: HUMAN ("allô"), MACHINE ("messagerie"), BEEP, SILENCE
5. Retourner résultat AMD
```

**Caractéristiques:**
- ✅ Pas de seuil minimum (même 0.3s transcrit)
- ✅ Transcrire progressivement pendant les 3s
- ✅ NLP sur transcription finale
- ❌ Pas de barge-in (on écoute juste)

**Transcriptions attendues:**
- HUMAN: "allô ?", "oui bonjour", "c'est qui ?"
- MACHINE: "vous êtes sur la messagerie de...", "laissez votre message après le bip"
- BEEP: *bip* (détecté par pattern audio ou transcription vide après beep)
- SILENCE: "" (aucune transcription)

---

### **MODE 2: PLAYING_AUDIO (Barge-in intelligent)**

**Durée:** Tant que robot parle
**Fonction:** `_monitor_vad_playing(call_uuid, record_file, audio_duration)`

**Workflow:**
```
1. uuid_record démarre EN PARALLÈLE de uuid_broadcast
2. Thread VAD surveille en continu
3. Détecter segments de parole:
   - Si < 0.8s: Backchannel → Logger + transcrire, PAS de barge-in
   - Si >= 2.5s: Vraie interruption → BARGE-IN!
4. Si barge-in:
   - Smooth delay 1.0s
   - uuid_break + uuid_record stop
   - Transcrire fichier complet
   - Retourner transcription pour NLP
5. Si pas de barge-in:
   - Audio se termine normalement
   - Supprimer recording (pas de transcription nécessaire)
```

**Caractéristiques:**
- ✅ Transcrire TOUS les segments (même <0.8s)
- ✅ Logger backchannels pour analytics
- ✅ Barge-in seulement si >= 2.5s parole continue
- ✅ Reset compteur si silence >= 2.0s
- ✅ Smooth delay avant interruption

**Exemples:**
```
Robot: "Bonjour, êtes-vous intéressé par..."
Client: "oui" (0.3s) → Logger "oui", continuer
Client: "ok" (0.2s)  → Logger "ok", continuer
Client: "ah non désolé là je suis occupé" (3.2s) → BARGE-IN + transcription complète

Avec max_autonomous_turns:
→ NLP détecte "occupé" = objection
→ Passer à objection_handler
```

---

### **MODE 3: WAITING_RESPONSE (End-of-speech detection)**

**Durée:** 10.0s timeout
**Fonction:** `_monitor_vad_waiting(call_uuid, record_file, timeout)`

**Workflow:**
```
1. uuid_record démarre (pas d'audio robot)
2. Thread VAD surveille en continu
3. Détecter DÉBUT de parole (dès 0.3s)
4. Transcrire en continu pendant que client parle
5. Détecter FIN de parole (silence >= 1.5s)
6. Stopper recording
7. Finaliser transcription (FinalResult)
8. Retourner transcription complète
9. Si timeout (10s) atteint sans parole → retry_silence
```

**Caractéristiques:**
- ✅ Détection début parole dès 0.3s
- ✅ Transcription continue (latence minimale)
- ✅ Fin de parole si silence >= 1.5s
- ✅ Timeout 10s si silence total
- ✅ Pas de seuil minimum (toute parole comptabilisée)

**Exemples:**
```
Robot: "Êtes-vous intéressé ?"
[silence 2s]
Client: "euh..." (début détecté)
Client: "...ben en fait... oui pourquoi pas"
[silence 1.5s] (fin détectée)
→ Transcription: "euh ben en fait oui pourquoi pas"
→ NLP: ACCEPT
```

---

## 🔧 Implémentation Technique

### Nouvelles Fonctions

**1. `_monitor_vad_amd(call_uuid, record_file)` → str**
- Input: call_uuid, record_file path
- Output: "HUMAN" | "MACHINE" | "BEEP" | "SILENCE" | "UNKNOWN"
- Durée: Exactement 3.0s
- Transcription: Vosk mode fichier (transcribe_file)

**2. `_monitor_vad_playing(call_uuid, record_file, audio_duration)` → Optional[str]**
- Input: call_uuid, record_file, durée audio robot
- Output: Transcription si barge-in, None sinon
- Durée: Tant que audio_duration ou barge-in
- Transcription: Segments continus + finale si barge-in

**3. `_monitor_vad_waiting(call_uuid, record_file, timeout)` → Optional[str]**
- Input: call_uuid, record_file, timeout
- Output: Transcription client ou None si timeout
- Durée: Jusqu'à end-of-speech ou timeout
- Transcription: Continue pendant parole + finale

### Fonctions Modifiées

**1. `_detect_answering_machine(call_uuid)`**
```python
# AVANT: Listening initial + transcription ad-hoc
# APRÈS: Appeler _monitor_vad_amd()
record_file = start_recording()
result = self._monitor_vad_amd(call_uuid, record_file)
return result  # "HUMAN" | "MACHINE" | etc.
```

**2. `_play_audio(call_uuid, audio_file)`**
```python
# AVANT: _monitor_barge_in_vad() (ancien mode)
# APRÈS: _monitor_vad_playing()
record_file = start_recording()
vad_thread = Thread(target=self._monitor_vad_playing, args=(call_uuid, record_file, duration))
# ...check barge-in flag...
```

**3. `_listen_for_response(call_uuid, timeout)`**
```python
# AVANT: _listen_record_fallback() (enregistrement fixe)
# APRÈS: _monitor_vad_waiting()
record_file = start_recording()
transcription = self._monitor_vad_waiting(call_uuid, record_file, timeout)
return transcription
```

---

## 📈 Bénéfices Attendus

### Performance
- ✅ **AMD plus rapide:** 3s vs. 2.5s + analyse actuelle
- ✅ **Latence réduite WAITING:** Transcription continue vs. attendre timeout
- ✅ **Pas de faux positifs barge-in:** Backchannels < 0.8s ignorés

### UX
- ✅ **Conversation plus naturelle:** Backchannels loggés mais pas interruptifs
- ✅ **Réactivité améliorée:** End-of-speech 1.5s vs. 4s timeout actuel
- ✅ **Détection AMD précise:** 3s optimal pour FR

### Analytics
- ✅ **Backchannels trackés:** "oui", "ok", "hum" loggés
- ✅ **Meilleure visibilité:** 3 modes distincts = logs plus clairs

---

## 🧪 Plan de Test

### Test 1: AMD Mode
```
Scénario 1: HUMAN
→ Client dit "allô ?" à T+0.5s
→ Attendu: "HUMAN" détecté

Scénario 2: MACHINE
→ Messagerie: "vous êtes sur la messagerie de..."
→ Attendu: "MACHINE" détecté

Scénario 3: SILENCE
→ Aucun son pendant 3s
→ Attendu: "SILENCE" ou "UNKNOWN"
```

### Test 2: PLAYING Mode
```
Scénario 1: Backchannels
→ Client dit "oui" (0.3s) puis "ok" (0.2s)
→ Attendu: Loggé, PAS de barge-in

Scénario 2: Vraie interruption
→ Client dit "ah non mais là je suis occupé" (3s)
→ Attendu: BARGE-IN après 2.5s

Scénario 3: Silence entre "oui"
→ Client: "oui" + pause 2.5s + "ok"
→ Attendu: Compteur reset, pas de barge-in
```

### Test 3: WAITING Mode
```
Scénario 1: Réponse immédiate
→ Client répond immédiatement "oui je suis intéressé"
→ Attendu: Transcription complète

Scénario 2: Hésitation
→ Client: silence 2s, puis "euh...oui"
→ Attendu: Transcription "euh oui"

Scénario 3: Timeout
→ Client ne répond pas pendant 10s
→ Attendu: None → retry_silence
```

---

## 🚀 Déploiement

### Phase 1: Configuration (✅ FAIT)
- [x] Ajouter configs 3 modes dans config.py
- [x] Ajouter à classe Config

### Phase 2: Implémentation Core
- [ ] Créer `_monitor_vad_amd()`
- [ ] Créer `_monitor_vad_playing()`
- [ ] Créer `_monitor_vad_waiting()`

### Phase 3: Adaptation Fonctions Existantes
- [ ] Modifier `_detect_answering_machine()`
- [ ] Modifier `_play_audio()`
- [ ] Modifier `_listen_for_response()`

### Phase 4: Tests
- [ ] Test AMD mode
- [ ] Test PLAYING mode
- [ ] Test WAITING mode
- [ ] Test end-to-end call flow

### Phase 5: Rollout
- [ ] Commit avec documentation
- [ ] Test en production
- [ ] Monitoring metrics

---

## 📝 Notes Techniques

### Gestion Fichiers WAV Streaming

**Problème:** uuid_record écrit header WAV incomplet pendant streaming

**Solution actuelle (à conserver):**
- Lecture RAW binaire
- Skip jusqu'au marker "data"
- Traiter frames incrémentales

**Amélioration MODE 3 (WAITING):**
- Utiliser Vosk streaming (AcceptWaveform) pendant enregistrement
- Pas besoin d'attendre fin fichier
- Réduire latence transcription

### Thread Safety

Tous les modes VAD fonctionnent en threads séparés :
- Accès `call_sessions[uuid]` protégé par dict Python (thread-safe)
- Flag `barge_in_detected_time` utilisé pour synchronisation
- Cleanup dans `_handle_channel_hangup` attend 0.2s pour threads

### Compatibilité

Anciennes configs `BARGE_IN_*` maintenues pour compatibilité :
```python
BARGE_IN_DURATION_THRESHOLD = PLAYING_BARGE_IN_THRESHOLD  # Alias
```

---

## 🔗 Références

- [Twilio AMD Best Practices](https://www.twilio.com/docs/voice/answering-machine-detection-faq-best-practices)
- [Retell AI VAD vs Turn-Taking](https://www.retellai.com/blog/vad-vs-turn-taking-end-point-in-conversational-ai)
- [Deepgram End-of-Speech Detection](https://developers.deepgram.com/docs/understanding-end-of-speech-detection)
- [AWS Connect Campaign Best Practices](https://docs.aws.amazon.com/connect/latest/adminguide/campaign-best-practices.html)

---

**Status:** Architecture validée, implémentation en cours
