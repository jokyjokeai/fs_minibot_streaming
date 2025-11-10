# Guide POC Jambonz - Test Rapide (2 semaines)

**Objectif:** Tester si Jambonz peut remplacer notre système V3 FreeSWITCH
**Durée estimée:** 2 semaines
**Décision finale:** GO/NO-GO pour migration complète

---

## Table des matières

1. [Qu'est-ce qu'on teste?](#1-quest-ce-quon-teste)
2. [Critères de succès](#2-critères-de-succès)
3. [Installation Jambonz](#3-installation-jambonz)
4. [Configuration de base](#4-configuration-de-base)
5. [Application webhook minimale](#5-application-webhook-minimale)
6. [Tests à réaliser](#6-tests-à-réaliser)
7. [Grille d'évaluation](#7-grille-dévaluation)
8. [Décision GO/NO-GO](#8-décision-gono-go)

---

## 1. Qu'est-ce qu'on teste?

### Fonctionnalités CRITIQUES à valider

| Feature | Importance | Test |
|---------|-----------|------|
| **AEC (Acoustic Echo Cancellation)** | 🔴 BLOQUANT | Appel avec haut-parleur activé |
| **AMD (Answering Machine Detection)** | 🔴 CRITIQUE | Détection humain vs machine |
| **Barge-in** | 🔴 CRITIQUE | Interrompre le robot pendant qu'il parle |
| **Qualité ASR** | 🟡 IMPORTANT | Précision transcription français |
| **Qualité TTS** | 🟡 IMPORTANT | Naturel de la voix |
| **Latence** | 🟡 IMPORTANT | Réactivité globale |
| **Streaming audio** | 🟢 BONUS | Bidirectionnel temps réel |

### Ce qu'on NE teste PAS (pour l'instant)

- Scénarios complexes (on teste juste 1 conversation simple)
- Database integration (pas nécessaire pour POC)
- Campaign management (pas nécessaire pour POC)
- Scalabilité (on teste 1 seul appel)

---

## 2. Critères de succès

### 🎯 Critères GO (Migration recommandée)

**TOUS les critères suivants doivent être OK:**

1. ✅ **AEC fonctionne:** Pas d'écho avec haut-parleur activé (0 faux barge-in)
2. ✅ **AMD >= V3:** Détecte correctement humain vs machine (85%+ précision)
3. ✅ **Barge-in réactif:** Interruption en < 500ms après début parole utilisateur
4. ✅ **ASR >= V3:** Transcription française correcte (90%+ précision)
5. ✅ **TTS naturel:** Voix compréhensible et agréable
6. ✅ **Latence acceptable:** Conversation fluide sans délais gênants
7. ✅ **Stable:** Aucun crash pendant les tests

### 🛑 Critères NO-GO (Rester sur V3)

**UN SEUL de ces critères = NO-GO:**

1. ❌ AEC ne fonctionne pas (écho avec haut-parleur)
2. ❌ AMD très inférieur à V3 (< 70% précision)
3. ❌ Barge-in non fonctionnel ou très lent (> 1s)
4. ❌ ASR beaucoup moins bon que Vosk (< 70% précision)
5. ❌ Bugs critiques fréquents (> 2 crashes pendant tests)

---

## 3. Installation Jambonz

### Option A: Docker Local (RECOMMANDÉ pour POC)

**Prérequis:**
- Ubuntu 20.04+ ou 22.04
- Docker + Docker Compose
- 4GB RAM minimum
- Ports libres: 5060, 5061, 8080, 3000

**Installation:**

```bash
# 1. Cloner le repo Jambonz
cd ~/Desktop
git clone https://github.com/jambonz/docker-compose-jambonz.git
cd docker-compose-jambonz

# 2. Configuration minimale
cp .env.sample .env

# Éditer .env pour votre configuration
nano .env
```

**Configuration .env minimale:**
```bash
# Domaine (localhost pour POC)
JAMBONZ_DOMAIN=localhost

# MySQL credentials
MYSQL_ROOT_PASSWORD=your_strong_password
MYSQL_DATABASE=jambonz
MYSQL_USER=jambonz
MYSQL_PASSWORD=jambonz_password

# Redis
REDIS_PASSWORD=redis_password

# API
JAMBONZ_API_BASE_URL=http://localhost:3000

# SIP
SIP_PORT=5060

# HTTP
HTTP_PORT=8080
```

**Lancement:**
```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier que tout tourne
docker-compose ps

# Vous devriez voir:
# - jambonz-mysql
# - jambonz-redis
# - jambonz-webapp
# - jambonz-sbc-sip
# - jambonz-sbc-rtp
# - jambonz-feature-server

# Logs
docker-compose logs -f
```

**Accès Web Portal:**
```
URL: http://localhost:8080
Username: admin
Password: admin (à changer!)
```

### Option B: Installation Serveur (Alternative)

Si Docker ne fonctionne pas, suivre: https://docs.jambonz.org/guides/get-started/installation

---

## 4. Configuration de base

### 4.1 Créer un compte Jambonz

1. Accéder au portal: http://localhost:8080
2. Login: admin / admin
3. Créer un Service Provider (si pas déjà fait)
4. Créer un Account sous ce Service Provider

### 4.2 Configurer Speech Credentials

**Option 1: Google Cloud (Meilleur qualité, payant)**

1. Dans portal Jambonz → Speech Services
2. Ajouter Google Cloud credentials:
   - Télécharger JSON key depuis Google Cloud Console
   - Coller le contenu dans Jambonz

**Option 2: Vosk (Gratuit, self-hosted)**

```bash
# Installer Vosk server
docker run -d -p 2700:2700 \
  --name vosk-server \
  alphacep/kaldi-fr:latest

# Dans Jambonz portal → Speech Services
# Ajouter "Custom STT Provider"
# URL: http://host.docker.internal:2700
```

**Option 3: Coqui TTS (Gratuit, self-hosted)**

```bash
# Dans votre venv actuel (vous avez déjà Coqui)
cd ~/Desktop/fs_minibot_streaming
source venv/bin/activate

# Lancer serveur TTS
python -m TTS.server.server --model_name tts_models/fr/mai/tacotron2-DDC

# Dans Jambonz portal → Speech Services
# Ajouter "Custom TTS Provider"
# URL: http://localhost:5002
```

### 4.3 Configurer SIP Carrier (Trunk sortant)

**Utiliser votre trunk actuel (gateway1):**

1. Dans portal Jambonz → Carriers
2. Cliquer "Add Carrier"
3. Remplir:
   ```
   Name: gateway1
   Type: SIP Gateway

   Outbound:
   - SIP Gateway: <votre_trunk_ip>
   - Port: 5060
   - Protocol: UDP
   - Username: <votre_username>
   - Password: <votre_password>

   Outbound caller ID: +33987654321 (votre numéro)
   ```

### 4.4 Créer une Application

1. Dans portal Jambonz → Applications
2. Cliquer "Add Application"
3. Remplir:
   ```
   Name: POC Test App
   Type: Webhook
   Webhook URL: http://host.docker.internal:3000/call-webhook
   Method: POST
   ```

**Note:** `host.docker.internal` permet à Docker d'accéder à votre machine locale

---

## 5. Application webhook minimale

### 5.1 Structure du projet

```bash
cd ~/Desktop
mkdir jambonz-poc-webhook
cd jambonz-poc-webhook

# Initialiser projet Node.js
npm init -y

# Installer dépendances
npm install express axios dotenv
```

### 5.2 Code webhook complet

**Créer `app.js`:**

```javascript
const express = require('express');
const app = express();

app.use(express.json());

// ============================================
// WEBHOOK PRINCIPAL - Début d'appel
// ============================================
app.post('/call-webhook', async (req, res) => {
  console.log('=== NOUVEL APPEL ===');
  console.log('Call SID:', req.body.call_sid);
  console.log('Direction:', req.body.direction);
  console.log('From:', req.body.from);
  console.log('To:', req.body.to);

  const verbs = [
    // Configuration barge-in
    {
      verb: 'config',
      bargeIn: {
        enable: true,
        input: ['speech'],
        actionHook: '/handle-bargein'
      }
    },

    // Message initial
    {
      verb: 'say',
      text: "Bonjour, je suis Julie, assistante virtuelle. Je vais vous poser quelques questions pour tester le système. Êtes-vous prêt?",
      synthesizer: {
        vendor: 'google',  // ou 'coqui' si vous utilisez Coqui
        language: 'fr-FR',
        voice: 'fr-FR-Wavenet-A'
      }
    },

    // Attendre réponse utilisateur
    {
      verb: 'gather',
      input: ['speech'],
      timeout: 5,
      actionHook: '/handle-response-1',
      recognizer: {
        vendor: 'google',  // ou 'vosk' si vous utilisez Vosk
        language: 'fr-FR'
      }
    }
  ];

  res.json(verbs);
});

// ============================================
// HANDLER - Première réponse
// ============================================
app.post('/handle-response-1', async (req, res) => {
  const { speech, call_sid } = req.body;

  console.log('\n=== RÉPONSE UTILISATEUR 1 ===');
  console.log('Transcription:', speech?.text || 'VIDE');
  console.log('Confidence:', speech?.confidence || 'N/A');

  const verbs = [
    {
      verb: 'say',
      text: "Parfait. Maintenant je vais parler pendant quelques secondes. N'hésitez pas à m'interrompre à tout moment pour tester le barge-in. Je continue de parler pour vous laisser le temps de m'interrompre. Vous pouvez dire quelque chose maintenant si vous voulez tester l'interruption.",
      synthesizer: {
        vendor: 'google',
        language: 'fr-FR',
        voice: 'fr-FR-Wavenet-A'
      }
    },
    {
      verb: 'gather',
      input: ['speech'],
      timeout: 5,
      actionHook: '/handle-response-2',
      recognizer: {
        vendor: 'google',
        language: 'fr-FR'
      }
    }
  ];

  res.json(verbs);
});

// ============================================
// HANDLER - Deuxième réponse
// ============================================
app.post('/handle-response-2', async (req, res) => {
  const { speech, call_sid } = req.body;

  console.log('\n=== RÉPONSE UTILISATEUR 2 ===');
  console.log('Transcription:', speech?.text || 'VIDE');
  console.log('Confidence:', speech?.confidence || 'N/A');

  const verbs = [
    {
      verb: 'say',
      text: "Merci pour ce test. Le système fonctionne correctement. Je vais maintenant raccrocher. Au revoir!",
      synthesizer: {
        vendor: 'google',
        language: 'fr-FR',
        voice: 'fr-FR-Wavenet-A'
      }
    },
    {
      verb: 'hangup'
    }
  ];

  res.json(verbs);
});

// ============================================
// HANDLER - Barge-in (interruption)
// ============================================
app.post('/handle-bargein', async (req, res) => {
  const { speech, call_sid } = req.body;

  console.log('\n=== BARGE-IN DÉTECTÉ ===');
  console.log('Transcription:', speech?.text || 'VIDE');
  console.log('Timestamp:', new Date().toISOString());

  const verbs = [
    {
      verb: 'say',
      text: "Très bien, je vous ai entendu m'interrompre. Le barge-in fonctionne parfaitement!",
      synthesizer: {
        vendor: 'google',
        language: 'fr-FR',
        voice: 'fr-FR-Wavenet-A'
      }
    },
    {
      verb: 'gather',
      input: ['speech'],
      timeout: 5,
      actionHook: '/handle-response-2',
      recognizer: {
        vendor: 'google',
        language: 'fr-FR'
      }
    }
  ];

  res.json(verbs);
});

// ============================================
// WEBHOOK - AMD Result
// ============================================
app.post('/amd-result', async (req, res) => {
  const { call_sid, amd } = req.body;

  console.log('\n=== AMD RÉSULTAT ===');
  console.log('Result:', amd?.result || 'N/A');
  console.log('Confidence:', amd?.confidence || 'N/A');
  console.log('Duration:', amd?.duration || 'N/A');

  if (amd?.result === 'MACHINE') {
    // Raccrocher si répondeur
    res.json([
      {
        verb: 'say',
        text: "Désolé, nous rappellerons plus tard. Au revoir."
      },
      {
        verb: 'hangup'
      }
    ]);
  } else {
    // Continuer si humain
    res.json([]);
  }
});

// ============================================
// WEBHOOK - Call Status (fin appel)
// ============================================
app.post('/call-status', async (req, res) => {
  const { call_sid, call_status, duration } = req.body;

  console.log('\n=== FIN APPEL ===');
  console.log('Call SID:', call_sid);
  console.log('Status:', call_status);
  console.log('Duration:', duration, 'secondes');

  res.sendStatus(200);
});

// ============================================
// Démarrage serveur
// ============================================
const PORT = 3000;
app.listen(PORT, () => {
  console.log(`🚀 Webhook server listening on port ${PORT}`);
  console.log(`📞 Ready to receive calls from Jambonz!`);
  console.log(`\nEndpoints disponibles:`);
  console.log(`- POST http://localhost:${PORT}/call-webhook`);
  console.log(`- POST http://localhost:${PORT}/handle-response-1`);
  console.log(`- POST http://localhost:${PORT}/handle-response-2`);
  console.log(`- POST http://localhost:${PORT}/handle-bargein`);
  console.log(`- POST http://localhost:${PORT}/amd-result`);
  console.log(`- POST http://localhost:${PORT}/call-status`);
});
```

### 5.3 Lancement webhook

```bash
cd ~/Desktop/jambonz-poc-webhook
node app.js
```

**Vous devriez voir:**
```
🚀 Webhook server listening on port 3000
📞 Ready to receive calls from Jambonz!
```

---

## 6. Tests à réaliser

### 6.1 Test 1: Appel sortant basique

**Objectif:** Vérifier que tout fonctionne end-to-end

**Procédure:**

1. Utiliser l'API REST Jambonz pour lancer un appel:

```bash
# Créer fichier test-call.sh
cat > test-call.sh << 'EOF'
#!/bin/bash

ACCOUNT_SID="<votre_account_sid>"  # Trouver dans portal Jambonz
APPLICATION_SID="<votre_app_sid>"   # ID de l'app créée
API_TOKEN="<votre_api_token>"       # Générer dans portal

curl -X POST http://localhost:3000/v1/Accounts/${ACCOUNT_SID}/Calls \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+33612345678",
    "from": "+33987654321",
    "application_sid": "'${APPLICATION_SID}'",
    "webhook": {
      "url": "http://host.docker.internal:3000/call-webhook",
      "method": "POST"
    }
  }'
EOF

chmod +x test-call.sh
./test-call.sh
```

**Alternative: Utiliser le portal web**

1. Aller dans Jambonz portal → Recent Calls
2. Cliquer "Make Test Call"
3. Entrer numéro cible
4. Sélectionner application "POC Test App"
5. Cliquer "Dial"

**Validation:**
- ✅ Appel reçu sur téléphone
- ✅ Message initial entendu
- ✅ Réponse transcrite correctement
- ✅ Conversation complète sans crash

### 6.2 Test 2: Barge-in (CRITIQUE)

**Objectif:** Vérifier que l'interruption fonctionne

**Procédure:**

1. Lancer appel (comme Test 1)
2. Quand le robot dit "Je vais parler pendant quelques secondes..."
3. **L'INTERROMPRE immédiatement** en disant "allô" ou "stop"

**Validation:**
- ✅ Robot s'arrête de parler immédiatement (< 500ms)
- ✅ Votre interruption est transcrite
- ✅ Robot répond "Très bien, je vous ai entendu m'interrompre"
- ✅ Logs webhook montrent événement barge-in

**Test console webhook:**
```
=== BARGE-IN DÉTECTÉ ===
Transcription: allô
Timestamp: 2025-11-09T...
```

### 6.3 Test 3: AEC Haut-parleur (CRITIQUE BLOQUANT)

**Objectif:** Vérifier qu'il n'y a PAS d'écho acoustique

**Procédure:**

1. **IMPORTANT:** Mettre votre téléphone en **HAUT-PARLEUR**
2. Lancer appel
3. Augmenter volume du haut-parleur
4. Laisser le robot parler SANS interrompre
5. Observer si le robot se coupe tout seul (= écho détecté)

**Validation:**
- ✅ Robot parle en continu SANS s'interrompre
- ✅ Aucun faux barge-in détecté
- ✅ Logs webhook ne montrent PAS de barge-in intempestifs

**Si échec (écho détecté):**
- ❌ Robot s'interrompt tout seul
- ❌ Logs montrent barge-in alors que vous n'avez rien dit
- ❌ **= PROBLÈME AEC = Potentiel NO-GO**

### 6.4 Test 4: AMD (Answering Machine Detection)

**Objectif:** Vérifier la détection répondeur

**Setup AMD dans Jambonz:**

Modifier `app.js` pour activer AMD:

```javascript
app.post('/call-webhook', async (req, res) => {
  const verbs = [
    {
      verb: 'dial',
      target: [{
        type: 'phone',
        number: '+33612345678'  // Votre numéro test
      }],
      answerOnBridge: true,
      amd: {
        actionHook: '/amd-result',
        recognizer: {
          vendor: 'google',
          language: 'fr-FR'
        },
        thresholds: {
          greeting_duration: 2000  // 2 secondes
        }
      }
    }
  ];

  res.json(verbs);
});
```

**Procédure:**

**Test A: Détection HUMAIN**
1. Lancer appel vers votre téléphone
2. Répondre rapidement: "Allô"
3. Vérifier logs webhook

**Validation:**
```
=== AMD RÉSULTAT ===
Result: HUMAN
Confidence: > 0.8
```

**Test B: Détection MACHINE**
1. Lancer appel vers numéro qui va sur répondeur
2. Ou simuler: répondre et dire un long message (> 5 secondes)

**Validation:**
```
=== AMD RÉSULTAT ===
Result: MACHINE
Confidence: > 0.7
```

**Taux de précision à viser:** >= 85% (sur 10 tests)

### 6.5 Test 5: Qualité ASR (Transcription)

**Objectif:** Comparer précision vs. Vosk actuel

**Procédure:**

Préparer 10 phrases test en français:
```
1. "Bonjour, je suis intéressé par votre offre"
2. "Non merci, je ne suis pas disponible"
3. "Pouvez-vous rappeler plus tard?"
4. "Je suis propriétaire depuis cinq ans"
5. "La surface est d'environ cent mètres carrés"
6. "Je ne comprends pas votre question"
7. "Oui, d'accord, c'est parfait"
8. "Non, je préfère ne pas continuer"
9. "Quelle est votre proposition exactement?"
10. "Je vais réfléchir et je vous rappelle"
```

**Pour chaque phrase:**
1. Lancer appel
2. Dire la phrase clairement
3. Noter transcription reçue
4. Calculer WER (Word Error Rate)

**Validation:**
- ✅ WER < 10% (90%+ mots corrects)
- ✅ Performance >= Vosk actuel

**Comparaison Vosk:**
Faire les mêmes tests avec votre V3 pour comparer.

### 6.6 Test 6: Qualité TTS (Voix)

**Objectif:** Évaluer naturel de la voix

**Procédure:**

Tester 3 providers différents:

**A. Google Wavenet:**
```javascript
synthesizer: {
  vendor: 'google',
  language: 'fr-FR',
  voice: 'fr-FR-Wavenet-A'  // Voix féminine
}
```

**B. ElevenLabs (si disponible):**
```javascript
synthesizer: {
  vendor: 'elevenlabs',
  voice: 'julie-voice-id',
  language: 'fr-FR'
}
```

**C. Coqui (gratuit):**
```javascript
synthesizer: {
  vendor: 'coqui',
  voice: 'jenny'
}
```

**Évaluation subjective:**
- Naturel (1-5): _____
- Compréhensibilité (1-5): _____
- Intonation (1-5): _____
- Vitesse (1-5): _____

**Validation:**
- ✅ Note moyenne >= 4/5
- ✅ Meilleur que TTS actuel (si applicable)

### 6.7 Test 7: Latence

**Objectif:** Mesurer réactivité

**Métriques à mesurer:**

1. **Call Setup Time:** Temps entre dial → première audio
2. **ASR Latency:** Fin de parole → transcription reçue
3. **TTS Latency:** Envoi texte → début audio
4. **Barge-in Latency:** Début parole → interruption effective

**Procédure:**

Instrumenter le code webhook:

```javascript
// Au début de chaque handler
const startTime = Date.now();

// À la fin
const latency = Date.now() - startTime;
console.log(`Latency: ${latency}ms`);
```

**Validation:**
- ✅ Call setup: < 3s
- ✅ ASR latency: < 1s
- ✅ TTS latency: < 500ms
- ✅ Barge-in: < 500ms

### 6.8 Test 8: Stabilité

**Objectif:** Vérifier absence de crashes

**Procédure:**

Faire 20 appels consécutifs en variant:
- Durées différentes
- Interruptions à différents moments
- Silences prolongés
- Phrases complexes

**Validation:**
- ✅ 0 crash serveur Jambonz
- ✅ 0 crash webhook app
- ✅ Tous les appels se terminent proprement

---

## 7. Grille d'évaluation

### Tableau de scoring

| Critère | Poids | Note /5 | Score pondéré | Commentaires |
|---------|-------|---------|---------------|--------------|
| **AEC (Haut-parleur)** | 25% | ___ | ___ | BLOQUANT si < 4 |
| **AMD Précision** | 20% | ___ | ___ | BLOQUANT si < 3 |
| **Barge-in Réactivité** | 15% | ___ | ___ | BLOQUANT si < 3 |
| **ASR Qualité** | 15% | ___ | ___ | Important |
| **TTS Naturel** | 10% | ___ | ___ | Important |
| **Latence globale** | 10% | ___ | ___ | Important |
| **Stabilité** | 5% | ___ | ___ | Important |
| **TOTAL** | 100% | - | **/5** | - |

**Barème de notation:**

- **5/5:** Excellent, dépasse attentes
- **4/5:** Très bon, égale ou surpasse V3
- **3/5:** Correct, acceptable
- **2/5:** Moyen, inférieur à V3
- **1/5:** Mauvais, non fonctionnel

### Exemples de notation

**AEC (25% - CRITIQUE):**
- 5/5: Aucun écho, fonctionne parfaitement avec haut-parleur fort
- 4/5: Écho très léger, ignorable
- 3/5: Écho modéré, utilisable
- 2/5: Écho fréquent, problématique
- 1/5: Écho constant, inutilisable → **NO-GO**

**AMD (20% - CRITIQUE):**
- 5/5: 95-100% précision sur tests
- 4/5: 85-94% précision
- 3/5: 75-84% précision
- 2/5: 65-74% précision → **NO-GO**
- 1/5: < 65% précision → **NO-GO**

**Barge-in (15% - CRITIQUE):**
- 5/5: < 300ms, imperceptible
- 4/5: 300-500ms, très réactif
- 3/5: 500-800ms, acceptable
- 2/5: 800-1500ms, lent → **NO-GO**
- 1/5: > 1500ms ou non fonctionnel → **NO-GO**

---

## 8. Décision GO/NO-GO

### Règles de décision

**🟢 GO pour migration complète SI:**

1. ✅ Score total >= 4.0/5
2. ✅ **ET** AEC >= 4/5 (OBLIGATOIRE)
3. ✅ **ET** AMD >= 3/5
4. ✅ **ET** Barge-in >= 3/5
5. ✅ **ET** Stabilité = 5/5 (0 crash)

**🔴 NO-GO (rester sur V3) SI:**

1. ❌ AEC < 4/5 (écho problématique)
2. ❌ **OU** AMD < 3/5 (trop d'erreurs)
3. ❌ **OU** Barge-in < 3/5 (trop lent)
4. ❌ **OU** Crashes fréquents (> 2 crashes sur 20 tests)
5. ❌ **OU** Score total < 3.5/5

**🟡 PEUT-ÊTRE (investigation supplémentaire) SI:**

- Score entre 3.5 et 4.0
- Un critère non-bloquant faible mais améliorable
- → Faire tests supplémentaires 1 semaine

### Template rapport final

```markdown
# Rapport POC Jambonz - Résultats

**Date:** 2025-11-XX
**Durée tests:** 2 semaines
**Nombre d'appels test:** 25

## Scores

| Critère | Note | Commentaire |
|---------|------|-------------|
| AEC | __/5 | ... |
| AMD | __/5 | ... |
| Barge-in | __/5 | ... |
| ASR | __/5 | ... |
| TTS | __/5 | ... |
| Latence | __/5 | ... |
| Stabilité | __/5 | ... |
| **TOTAL** | **__/5** | - |

## Incidents rencontrés

1. ...
2. ...

## Points positifs

- ...
- ...

## Points négatifs

- ...
- ...

## Décision finale

🟢 **GO** / 🔴 **NO-GO** / 🟡 **PEUT-ÊTRE**

### Justification:

...

### Prochaines étapes:

Si GO:
1. ...
2. ...

Si NO-GO:
1. Améliorer V3 (focus AEC)
2. ...
```

---

## 9. Troubleshooting

### Problème: Jambonz ne démarre pas

```bash
# Vérifier logs
docker-compose logs

# Redémarrer services
docker-compose down
docker-compose up -d

# Vérifier ports utilisés
sudo netstat -tlnp | grep -E '5060|8080|3000'
```

### Problème: Webhook non accessible depuis Jambonz

```bash
# Si Docker ne peut pas accéder à localhost
# Utiliser IP machine au lieu de localhost

# Trouver votre IP locale
ip addr show

# Dans Jambonz Application, utiliser:
# http://192.168.X.X:3000/call-webhook (au lieu de localhost)
```

### Problème: Pas d'audio bidirectionnel

Vérifier:
1. Firewall autorise RTP (ports 10000-60000)
2. NAT configuration si serveur distant
3. Logs SBC: `docker-compose logs jambonz-sbc-rtp`

### Problème: ASR ne transcrit rien

Vérifier:
1. Speech credentials configurées correctement
2. Langue définie: `language: 'fr-FR'`
3. Vendor accessible: `curl http://localhost:2700` (si Vosk)

### Problème: AMD toujours MACHINE

Ajuster seuils:
```javascript
amd: {
  thresholds: {
    greeting_duration: 3000,  // Plus souple
    speech_threshold: 128     // Plus sensible
  }
}
```

---

## 10. Ressources

### Documentation officielle

- Site officiel: https://jambonz.org
- Docs: https://docs.jambonz.org
- GitHub: https://github.com/jambonz
- Community Slack: https://joinslack.jambonz.org

### Exemples de code

- Exemples officiels: https://github.com/jambonz/jambonz-examples
- AMD example: https://github.com/jambonz/anwering-machine-detection-example
- OpenAI integration: https://github.com/jambonz/openai-s2s-example

### Support

- GitHub Issues: https://github.com/jambonz/jambonz-feature-server/issues
- Slack community (très réactif)
- Documentation FAQ

---

## Conclusion

Ce POC doit vous permettre de décider **objectivement** si Jambonz peut remplacer votre V3 FreeSWITCH.

**Focus sur les 3 critères BLOQUANTS:**
1. 🔴 **AEC (haut-parleur)** - Le plus important
2. 🟡 **AMD** - Critique pour production
3. 🟡 **Barge-in** - Core feature

Si ces 3 points passent, le reste est ajustable.

**Timing:**
- Semaine 1: Installation + premiers tests (Test 1-4)
- Semaine 2: Tests approfondis + évaluation (Test 5-8)
- Jour 14: Décision GO/NO-GO

**Bonne chance pour le POC! 🚀**

---

**Questions?** Relire ce guide ou consulter la doc Jambonz.
