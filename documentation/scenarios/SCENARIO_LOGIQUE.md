# 📞 LOGIQUE DU SCÉNARIO DE BASE - MiniBotPanel

## 🎯 Vue d'ensemble

Le scénario suit un flux conversationnel structuré avec détection d'intention et qualification automatique des leads.

## 🔄 FLUX PRINCIPAL

```
HELLO (Introduction)
   ├─ OUI/Intéressé → Q1
   ├─ NON/Pas intéressé → RETRY
   ├─ Pas sûr/Callback → RETRY
   └─ Silence (15 sec) → RETRY

RETRY (Tentative de relance)
   ├─ OUI/Intéressé → Q1
   ├─ NON/Pas intéressé → BYE_FAILED (Not_interested)
   ├─ Pas sûr → BYE_FAILED (Not_interested)
   └─ Silence (15 sec) → BYE_FAILED

Q1 (Question 1 - Propriétaire?)
   ├─ Toute réponse → Q2
   └─ Silence (12 sec) → Q2

Q2 (Question 2 - Travaux prévus?)
   ├─ Toute réponse → Q3
   └─ Silence (12 sec) → Q3

Q3 (Question 3 - Budget?)
   ├─ Toute réponse → IS_LEADS
   └─ Silence (12 sec) → IS_LEADS

IS_LEADS (Question qualifiante - Intéressé par offre?)
   ├─ OUI/Intéressé → CONFIRM → BYE_SUCCESS (✅ LEAD)
   ├─ NON/Pas intéressé → BYE_FAILED (❌ NOT_INTERESTED)
   ├─ Pas sûr → BYE_FAILED (❌ NOT_INTERESTED)
   └─ Silence (15 sec) → BYE_FAILED

CONFIRM (Confirmation rendez-vous)
   ├─ Toute réponse → BYE_SUCCESS
   └─ Silence (10 sec) → BYE_SUCCESS
```

## 🎭 DÉTECTION D'INTENTION (Intent Mapping)

### Intents détectés par l'IA :

- **affirm** : Oui, d'accord, ok, bien sûr, absolument
- **interested** : Ça m'intéresse, pourquoi pas, je veux bien
- **deny** : Non, pas intéressé, non merci
- **not_interested** : Pas du tout, aucun intérêt
- **unsure** : Je ne sais pas, peut-être, il faut voir
- **callback** : Rappelez-moi, plus tard, pas maintenant
- **question** : Le client pose une question
- **silence** : Pas de réponse détectée

## 📊 QUALIFICATION DES LEADS

### Règle BINAIRE simple :

**➡️ LEAD** si :
- Le client arrive jusqu'à IS_LEADS
- ET répond OUI/Intéressé à IS_LEADS

**➡️ NOT_INTERESTED** si :
- Le client dit NON à HELLO ou RETRY
- OU dit NON/Pas sûr à IS_LEADS
- OU raccroche avant IS_LEADS

## ⚙️ PARAMÈTRES TECHNIQUES

### Timeouts silence :
- **HELLO** : 15 secondes
- **RETRY** : 15 secondes
- **Q1, Q2, Q3** : 12 secondes
- **IS_LEADS** : 15 secondes
- **CONFIRM** : 10 secondes

### Barge-in (interruption) :
- ✅ **Activé sur TOUTES les étapes**
- Le client peut interrompre à tout moment
- L'audio s'arrête dès détection de parole

### Gestion silence :
- 3 secondes de silence = fin de phrase détectée
- Après timeout → passage étape suivante automatique

## 🤖 MODE IA FREESTYLE (À implémenter)

### Déclenchement :
- Quand le client pose une **question**
- Quand l'intent n'est **pas clair**
- Quand le client **parle pendant le message**

### Fonctionnement :
1. **Pause du scénario**
2. **IA répond** à la question/objection
3. **IA ramène** vers le scénario principal
4. **Reprise** à l'étape appropriée

### Exemple :
```
BOT: "Bonjour, je suis Julie..."
CLIENT: "C'est pour quoi exactement?"
IA: "Nous proposons des panneaux solaires..."
IA: "Puis-je vous poser quelques questions?"
CLIENT: "D'accord"
→ Retour à Q1
```

## 📝 MESSAGES AUDIO

### Fichiers requis :
- `hello.wav` : Introduction (Bonjour, je suis Julie de...)
- `retry.wav` : Relance (Je comprends, c'est très rapide...)
- `q1.wav` : Question 1 (Êtes-vous propriétaire?)
- `q2.wav` : Question 2 (Avez-vous des travaux prévus?)
- `q3.wav` : Question 3 (Quel est votre budget?)
- `is_leads.wav` : Question qualifiante (Seriez-vous intéressé?)
- `confirm.wav` : Confirmation (Parfait, on vous rappelle...)
- `bye_success.wav` : Fin succès (Merci, à bientôt!)
- `bye_failed.wav` : Fin échec (Merci de votre temps)

## 🎯 DÉTECTION AMD (Answering Machine Detection)

### Dual-layer :
1. **FreeSWITCH** : Détection rapide (< 3 sec)
2. **Python/IA** : Détection précise si doute

### Actions :
- **HUMAN** → Continue scénario
- **MACHINE** → Raccroche ou laisse message
- **UNSURE** → Continue comme HUMAN

## 📊 MÉTRIQUES COLLECTÉES

Pour chaque appel :
- **Durée totale**
- **Durée par étape**
- **Transcriptions complètes**
- **Intents détectés**
- **Confiance IA** (0-100%)
- **Sentiment global** (Positif/Neutre/Négatif)
- **Résultat final** (Lead/Not_interested)
- **Raison abandon** (si échec)

## 🔄 SYSTÈME DE RETRY

### NO_ANSWER :
- Max 2 tentatives
- Délai 30 minutes entre tentatives
- Priorité haute dans la queue

### BUSY :
- Max 1 tentative
- Délai 5 minutes
- Priorité normale

## 💡 RÈGLES IMPORTANTES

1. **Toujours commencer par HELLO**
2. **Une seule relance (RETRY) maximum**
3. **Questions Q1-Q3 sont informatives**
4. **IS_LEADS est LA question qualifiante**
5. **Barge-in toujours actif**
6. **Silence prolongé = passage suivant**
7. **IA Freestyle en backup si confusion**

## 🚀 UTILISATION

### Pour créer un nouveau scénario :
1. Garder cette structure de base
2. Remplacer les fichiers audio
3. Adapter les textes des questions
4. Conserver la logique d'enchaînement

### Pour personnaliser :
- Changer les timeouts dans config
- Ajouter/retirer des questions (Q4, Q5...)
- Modifier les règles de qualification
- Activer/désactiver barge-in par étape

## ⚠️ POINTS D'ATTENTION

- **IS_LEADS** est CRITIQUE - c'est LA question qui qualifie
- Le **RETRY** ne se fait qu'UNE fois
- Le **silence** est interprété comme désintérêt
- L'**IA Freestyle** doit toujours ramener au scénario
- Les **transcriptions** sont sauvées pour analyse

---

*Ce document définit la logique métier du scénario. L'implémentation technique se trouve dans les fichiers Python correspondants.*