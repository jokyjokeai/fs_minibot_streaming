# 📡 API Reference - MiniBotPanel v3

Documentation complète de l'API REST FastAPI pour MiniBotPanel v3.

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Authentification](#authentification)
3. [Endpoints racine](#endpoints-racine)
4. [Campaigns - Gestion des campagnes](#campaigns---gestion-des-campagnes)
5. [Statistics - Statistiques](#statistics---statistiques)
6. [Exports - Exports et téléchargements](#exports---exports-et-téléchargements)
7. [Codes d'erreur](#codes-derreur)
8. [Exemples cURL](#exemples-curl)
9. [Exemples Python](#exemples-python)
10. [Rate Limiting & Performance](#rate-limiting--performance)

---

## Vue d'ensemble

### Informations générales

| Paramètre | Valeur |
|-----------|--------|
| **URL de base** | `http://localhost:8000` (développement) |
| **Version API** | `3.0.0` |
| **Framework** | FastAPI |
| **Format réponse** | JSON |
| **Encodage** | UTF-8 |
| **Authentification** | Mot de passe simple (X-API-Key) |

### URLs de documentation auto-générée

- **Swagger UI** : `http://localhost:8000/docs`
- **ReDoc** : `http://localhost:8000/redoc`
- **OpenAPI JSON** : `http://localhost:8000/openapi.json`

---

## Authentification

L'API utilise une authentification simple par mot de passe unique.

### Méthode 1 : Header HTTP (recommandé)

```http
X-API-Key: votre_mot_de_passe
```

### Méthode 2 : Query parameter

```http
GET /api/campaigns?password=votre_mot_de_passe
```

### Endpoints publics (pas d'authentification requise)

- `GET /`
- `GET /health`
- `GET /metrics`
- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`

### Configuration du mot de passe

Dans `system/config.py` ou via variable d'environnement :

```bash
export API_PASSWORD="your_secure_password_here"
```

### Exemple d'authentification

```bash
# Avec header (recommandé)
curl -H "X-API-Key: mypassword123" http://localhost:8000/api/campaigns

# Avec query param
curl "http://localhost:8000/api/campaigns?password=mypassword123"
```

### Erreur d'authentification

**Code HTTP** : `401 Unauthorized`

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or missing API password. Provide it via X-API-Key header or ?password= query param."
  }
}
```

---

## Endpoints racine

### `GET /` - Informations système

Retourne les informations de base de l'API.

**Authentification** : Non requise

**Réponse** :

```json
{
  "name": "MiniBotPanel v3 API",
  "version": "3.0.0",
  "status": "running",
  "uptime": "5h 32m",
  "documentation": {
    "swagger": "/docs",
    "redoc": "/redoc",
    "openapi": "/openapi.json"
  },
  "endpoints": {
    "campaigns": "/api/campaigns",
    "statistics": "/api/stats",
    "exports": "/api/exports"
  }
}
```

**Exemple cURL** :

```bash
curl http://localhost:8000/
```

---

### `GET /health` - Health check

Vérifie l'état de tous les composants du système.

**Authentification** : Non requise

**Réponse** :

```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T14:32:10.123456",
  "components": {
    "database": {
      "status": "healthy"
    },
    "freeswitch": {
      "status": "healthy",
      "esl_port": 8021
    },
    "vosk": {
      "status": "healthy"
    },
    "ollama": {
      "status": "healthy"
    }
  }
}
```

**Codes HTTP** :
- `200 OK` : Système sain
- `503 Service Unavailable` : Un ou plusieurs composants défaillants

**Exemple cURL** :

```bash
curl http://localhost:8000/health
```

---

### `GET /metrics` - Métriques Prometheus

Retourne les métriques au format Prometheus.

**Authentification** : Non requise

**Format** : `text/plain` (compatible Prometheus)

**Réponse** :

```
# HELP minibot_campaigns_active Number of active campaigns
# TYPE minibot_campaigns_active gauge
minibot_campaigns_active 3

# HELP minibot_calls_active Number of active calls
# TYPE minibot_calls_active gauge
minibot_calls_active 12

# HELP minibot_calls_completed_total Total completed calls
# TYPE minibot_calls_completed_total counter
minibot_calls_completed_total 1247

# HELP minibot_uptime_seconds Uptime in seconds
# TYPE minibot_uptime_seconds gauge
minibot_uptime_seconds 19920
```

**Exemple cURL** :

```bash
curl http://localhost:8000/metrics
```

---

## Campaigns - Gestion des campagnes

### `POST /api/campaigns/` - Créer une campagne

Crée une nouvelle campagne d'appels.

**Authentification** : Requise

**Body** :

```json
{
  "name": "Prospection Q1 2025",
  "description": "Campagne de prospection commerciale Q1",
  "contact_ids": [1, 2, 3, 4, 5],
  "scenario": "scenario_finance_crypto",
  "max_concurrent_calls": 5,
  "batch_size": 10,
  "retry_enabled": true,
  "max_retries": 2
}
```

**Paramètres** :

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `name` | string | ✅ | Nom de la campagne (1-200 caractères) |
| `description` | string | ❌ | Description (max 500 caractères) |
| `contact_ids` | array[int] | ✅ | Liste des IDs contacts (1-10000) |
| `scenario` | string | ✅ | Nom du scénario JSON (sans .json) |
| `max_concurrent_calls` | int | ❌ | Appels simultanés (1-50, défaut: 5) |
| `batch_size` | int | ❌ | Taille des batchs (1-20, défaut: 10) |
| `retry_enabled` | bool | ❌ | Activer retry (défaut: true) |
| `max_retries` | int | ❌ | Nombre de retry (0-5, défaut: 2) |

**Réponse** : `201 Created`

```json
{
  "id": 42,
  "name": "Prospection Q1 2025",
  "description": "Campagne de prospection commerciale Q1",
  "scenario": "scenario_finance_crypto",
  "status": "pending",
  "max_concurrent_calls": 5,
  "batch_size": 10,
  "retry_enabled": true,
  "max_retries": 2,
  "stats": {
    "total": 5,
    "completed": 0,
    "pending": 5
  },
  "created_at": "2025-01-15T14:00:00.000000",
  "started_at": null,
  "completed_at": null
}
```

**Erreurs** :
- `400 Bad Request` : Contact IDs invalides ou plus de 10000 contacts
- `422 Unprocessable Entity` : Données de validation invalides

**Exemple cURL** :

```bash
curl -X POST http://localhost:8000/api/campaigns/ \
  -H "X-API-Key: mypassword" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Campaign",
    "contact_ids": [1, 2, 3],
    "scenario": "scenario_test_demo"
  }'
```

---

### `GET /api/campaigns/` - Lister les campagnes

Liste toutes les campagnes avec pagination et filtres.

**Authentification** : Requise

**Query Parameters** :

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `status` | string | null | Filtrer par statut (pending, running, paused, completed, cancelled) |
| `limit` | int | 50 | Nombre max de résultats (1-500) |
| `offset` | int | 0 | Offset pour pagination |

**Réponse** : `200 OK`

```json
{
  "total": 127,
  "limit": 50,
  "offset": 0,
  "campaigns": [
    {
      "id": 42,
      "name": "Prospection Q1 2025",
      "scenario": "scenario_finance_crypto",
      "status": "running",
      "stats": {
        "total": 150,
        "completed": 87,
        "in_progress": 3,
        "pending": 60
      },
      "created_at": "2025-01-15T14:00:00.000000"
    },
    {
      "id": 41,
      "name": "Lead Generation Wine",
      "scenario": "scenario_vin",
      "status": "completed",
      "stats": {
        "total": 200,
        "completed": 200,
        "in_progress": 0,
        "pending": 0
      },
      "created_at": "2025-01-14T10:00:00.000000"
    }
  ]
}
```

**Exemple cURL** :

```bash
# Toutes les campagnes
curl -H "X-API-Key: mypassword" http://localhost:8000/api/campaigns/

# Campagnes actives uniquement
curl -H "X-API-Key: mypassword" "http://localhost:8000/api/campaigns/?status=running"

# Pagination
curl -H "X-API-Key: mypassword" "http://localhost:8000/api/campaigns/?limit=20&offset=40"
```

---

### `GET /api/campaigns/{campaign_id}` - Détails d'une campagne

Récupère les détails complets d'une campagne.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `200 OK`

```json
{
  "id": 42,
  "name": "Prospection Q1 2025",
  "description": "Campagne de prospection commerciale Q1",
  "scenario": "scenario_finance_crypto",
  "status": "running",
  "max_concurrent_calls": 5,
  "batch_size": 10,
  "retry_enabled": true,
  "max_retries": 2,
  "stats": {
    "total": 150,
    "completed": 87,
    "in_progress": 3,
    "pending": 60,
    "leads": 23,
    "not_interested": 45,
    "callbacks": 12
  },
  "created_at": "2025-01-15T14:00:00.000000",
  "started_at": "2025-01-15T14:05:00.000000",
  "completed_at": null
}
```

**Erreurs** :
- `404 Not Found` : Campagne introuvable

**Exemple cURL** :

```bash
curl -H "X-API-Key: mypassword" http://localhost:8000/api/campaigns/42
```

---

### `PATCH /api/campaigns/{campaign_id}` - Modifier une campagne

Met à jour les paramètres d'une campagne.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Body** (tous les champs sont optionnels) :

```json
{
  "name": "Nouveau nom",
  "description": "Nouvelle description",
  "max_concurrent_calls": 10
}
```

**Limitations** :
- Les campagnes en cours (`running`) : seul `max_concurrent_calls` peut être modifié
- Les campagnes `pending` ou `paused` : tous les champs peuvent être modifiés

**Réponse** : `200 OK`

```json
{
  "id": 42,
  "name": "Nouveau nom",
  "description": "Nouvelle description",
  "scenario": "scenario_finance_crypto",
  "status": "running",
  "max_concurrent_calls": 10,
  "stats": {...},
  "created_at": "2025-01-15T14:00:00.000000",
  "started_at": "2025-01-15T14:05:00.000000",
  "completed_at": null
}
```

**Erreurs** :
- `400 Bad Request` : Modification non autorisée pour une campagne en cours
- `404 Not Found` : Campagne introuvable

**Exemple cURL** :

```bash
curl -X PATCH http://localhost:8000/api/campaigns/42 \
  -H "X-API-Key: mypassword" \
  -H "Content-Type: application/json" \
  -d '{"max_concurrent_calls": 10}'
```

---

### `POST /api/campaigns/{campaign_id}/start` - Démarrer une campagne

Démarre une campagne en attente.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `200 OK`

```json
{
  "status": "success",
  "message": "Campaign 42 started",
  "campaign_id": 42
}
```

**Erreurs** :
- `400 Bad Request` : Campagne déjà en cours ou terminée
- `404 Not Found` : Campagne introuvable

**Exemple cURL** :

```bash
curl -X POST http://localhost:8000/api/campaigns/42/start \
  -H "X-API-Key: mypassword"
```

---

### `POST /api/campaigns/{campaign_id}/pause` - Mettre en pause

Met en pause une campagne en cours.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `200 OK`

```json
{
  "status": "success",
  "message": "Campaign 42 paused",
  "campaign_id": 42
}
```

**Erreurs** :
- `400 Bad Request` : Seule une campagne `running` peut être mise en pause
- `404 Not Found` : Campagne introuvable

**Exemple cURL** :

```bash
curl -X POST http://localhost:8000/api/campaigns/42/pause \
  -H "X-API-Key: mypassword"
```

---

### `POST /api/campaigns/{campaign_id}/resume` - Reprendre

Reprend une campagne en pause.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `200 OK`

```json
{
  "status": "success",
  "message": "Campaign 42 resumed",
  "campaign_id": 42
}
```

**Erreurs** :
- `400 Bad Request` : Seule une campagne `paused` peut être reprise
- `404 Not Found` : Campagne introuvable

**Exemple cURL** :

```bash
curl -X POST http://localhost:8000/api/campaigns/42/resume \
  -H "X-API-Key: mypassword"
```

---

### `POST /api/campaigns/{campaign_id}/stop` - Arrêter définitivement

Arrête définitivement une campagne (status → `cancelled`).

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `200 OK`

```json
{
  "status": "success",
  "message": "Campaign 42 stopped",
  "campaign_id": 42,
  "final_stats": {
    "total": 150,
    "completed": 87,
    "pending": 63,
    "leads": 23,
    "not_interested": 45
  }
}
```

**Notes** :
- Tous les appels `pending` sont marqués comme `cancelled`
- L'opération est irréversible

**Erreurs** :
- `400 Bad Request` : Campagne déjà terminée
- `404 Not Found` : Campagne introuvable

**Exemple cURL** :

```bash
curl -X POST http://localhost:8000/api/campaigns/42/stop \
  -H "X-API-Key: mypassword"
```

---

### `DELETE /api/campaigns/{campaign_id}` - Supprimer

Supprime une campagne non démarrée.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `204 No Content`

**Erreurs** :
- `400 Bad Request` : Seules les campagnes `pending` peuvent être supprimées
- `404 Not Found` : Campagne introuvable

**Exemple cURL** :

```bash
curl -X DELETE http://localhost:8000/api/campaigns/42 \
  -H "X-API-Key: mypassword"
```

---

### `GET /api/campaigns/{campaign_id}/calls` - Lister les appels

Liste tous les appels d'une campagne avec filtres.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Query Parameters** :

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `status` | string | null | Filtrer par statut (pending, calling, ringing, in_progress, completed, failed, cancelled, no_answer) |
| `result` | string | null | Filtrer par résultat (lead, not_interested, callback, no_answer, failed, wrong_number, answering_machine) |
| `limit` | int | 50 | Limite (1-500) |
| `offset` | int | 0 | Offset pagination |

**Réponse** : `200 OK`

```json
{
  "total": 150,
  "limit": 50,
  "offset": 0,
  "calls": [
    {
      "id": 1234,
      "uuid": "abc-def-123-456",
      "contact": {
        "phone": "+33612345678",
        "first_name": "Jean",
        "last_name": "Dupont",
        "company": "TechCorp"
      },
      "status": "completed",
      "result": "lead",
      "duration": 127,
      "sentiment": "positive",
      "created_at": "2025-01-15T14:10:00.000000"
    }
  ]
}
```

**Exemple cURL** :

```bash
# Tous les appels
curl -H "X-API-Key: mypassword" http://localhost:8000/api/campaigns/42/calls

# Appels avec résultat "lead"
curl -H "X-API-Key: mypassword" "http://localhost:8000/api/campaigns/42/calls?result=lead"

# Appels complétés uniquement
curl -H "X-API-Key: mypassword" "http://localhost:8000/api/campaigns/42/calls?status=completed"
```

---

## Statistics - Statistiques

### `GET /api/stats/campaign/{campaign_id}` - Stats complètes

Récupère toutes les statistiques d'une campagne.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `200 OK`

```json
{
  "campaign_id": 42,
  "campaign_name": "Prospection Q1 2025",
  "campaign_status": "running",
  "total": 150,
  "status": {
    "pending": 60,
    "calling": 2,
    "ringing": 1,
    "in_progress": 3,
    "completed": 87,
    "failed": 2,
    "cancelled": 0,
    "no_answer": 0
  },
  "results": {
    "lead": 23,
    "not_interested": 45,
    "callback": 12,
    "no_answer": 5,
    "failed": 2,
    "wrong_number": 0,
    "answering_machine": 0
  },
  "sentiment": {
    "positive": 35,
    "neutral": 30,
    "negative": 22
  },
  "amd": {
    "human": 82,
    "machine": 5,
    "detection_rate": "94.3%"
  },
  "averages": {
    "duration": "124.5s",
    "calls_per_hour": "52.3"
  },
  "conversion": {
    "leads": 23,
    "rate": "26.4%"
  },
  "timestamps": {
    "created": "2025-01-15T14:00:00.000000",
    "started": "2025-01-15T14:05:00.000000",
    "completed": null,
    "elapsed_seconds": 3600
  }
}
```

**Exemple cURL** :

```bash
curl -H "X-API-Key: mypassword" http://localhost:8000/api/stats/campaign/42
```

---

### `GET /api/stats/campaign/{campaign_id}/live` - Stats temps réel

Stats optimisées pour monitoring live (avec cache).

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `200 OK`

```json
{
  "campaign_id": 42,
  "campaign_name": "Prospection Q1 2025",
  "status": "running",
  "total": 150,
  "completed": 87,
  "in_progress": 3,
  "pending": 60,
  "results": {
    "leads": 23,
    "not_interested": 45,
    "callbacks": 12,
    "answering_machines": 5,
    "no_answer": 2
  },
  "percentages": {
    "completion": "58.0%",
    "leads": "26.4%",
    "not_interested": "51.7%"
  },
  "duration": {
    "average": "124.5s",
    "total": "180.5min"
  },
  "sentiment": {
    "positive": 35,
    "neutral": 30,
    "negative": 22,
    "positive_rate": "40.2%"
  },
  "eta": "2025-01-15T15:30:00.000000",
  "last_update": "2025-01-15T14:55:00.000000"
}
```

**Notes** :
- Données mises en cache pour performance
- Rafraîchissement automatique toutes les 5 secondes
- ETA calculé en fonction du rythme actuel

**Exemple cURL** :

```bash
curl -H "X-API-Key: mypassword" http://localhost:8000/api/stats/campaign/42/live

# Polling toutes les 5 secondes
watch -n 5 'curl -s -H "X-API-Key: mypassword" http://localhost:8000/api/stats/campaign/42/live | jq'
```

---

### `GET /api/stats/campaign/{campaign_id}/timeline` - Timeline activité

Timeline d'activité par intervalles.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Query Parameters** :

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `interval` | int | 60 | Intervalle en minutes (1-1440) |

**Réponse** : `200 OK`

```json
{
  "campaign_id": 42,
  "interval_minutes": 60,
  "timeline": [
    {
      "timestamp": "2025-01-15T14:00:00.000000",
      "calls": 25,
      "leads": 6
    },
    {
      "timestamp": "2025-01-15T15:00:00.000000",
      "calls": 32,
      "leads": 8
    },
    {
      "timestamp": "2025-01-15T16:00:00.000000",
      "calls": 30,
      "leads": 9
    }
  ]
}
```

**Exemple cURL** :

```bash
# Timeline par heure (défaut)
curl -H "X-API-Key: mypassword" http://localhost:8000/api/stats/campaign/42/timeline

# Timeline par 15 minutes
curl -H "X-API-Key: mypassword" "http://localhost:8000/api/stats/campaign/42/timeline?interval=15"

# Timeline journalière
curl -H "X-API-Key: mypassword" "http://localhost:8000/api/stats/campaign/42/timeline?interval=1440"
```

---

### `GET /api/stats/system` - Stats système globales

Statistiques globales de l'ensemble du système.

**Authentification** : Requise

**Réponse** : `200 OK`

```json
{
  "system": {
    "version": "3.0.0",
    "status": "operational",
    "uptime": "5h 32m"
  },
  "campaigns": {
    "total": 127,
    "active": 3,
    "completed": 124
  },
  "calls": {
    "total": 15847,
    "today": 387,
    "active_now": 12,
    "average_duration": "118.3s"
  },
  "contacts": {
    "total": 8523
  },
  "performance": {
    "conversion_rate": "24.7%",
    "total_leads": 3912
  },
  "limits": {
    "max_concurrent_calls": 50,
    "current_usage": "24.0%"
  }
}
```

**Exemple cURL** :

```bash
curl -H "X-API-Key: mypassword" http://localhost:8000/api/stats/system
```

---

## Exports - Exports et téléchargements

### `GET /api/exports/campaign/{campaign_id}/csv` - Export CSV

Exporte les résultats d'une campagne en CSV.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Query Parameters** :

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `include_links` | bool | true | Inclure liens audio/transcriptions |

**Réponse** : `200 OK` (fichier CSV)

**Format CSV** :

```csv
phone,first_name,last_name,email,company,status,result,duration,sentiment,confidence,amd_result,created_at,ended_at,audio_link,transcript_link
+33612345678,Jean,Dupont,jean@example.com,TechCorp,completed,lead,127,positive,0.92,human,2025-01-15T14:10:00,2025-01-15T14:12:07,http://localhost:8000/api/exports/audio/abc-123,http://localhost:8000/api/exports/transcript/abc-123
```

**Headers réponse** :
- `Content-Type: text/csv`
- `Content-Disposition: attachment; filename=campaign_42_20250115_141000.csv`

**Exemple cURL** :

```bash
# Télécharger CSV avec liens
curl -H "X-API-Key: mypassword" \
  http://localhost:8000/api/exports/campaign/42/csv \
  -o campaign_42.csv

# Sans liens audio/transcriptions
curl -H "X-API-Key: mypassword" \
  "http://localhost:8000/api/exports/campaign/42/csv?include_links=false" \
  -o campaign_42.csv
```

---

### `GET /api/exports/campaign/{campaign_id}/json` - Export JSON

Exporte les résultats complets en JSON.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `200 OK`

```json
{
  "campaign": {
    "id": 42,
    "name": "Prospection Q1 2025",
    "description": "Campagne de prospection commerciale Q1",
    "scenario": "scenario_finance_crypto",
    "status": "completed",
    "stats": {...},
    "created_at": "2025-01-15T14:00:00.000000",
    "started_at": "2025-01-15T14:05:00.000000",
    "completed_at": "2025-01-15T16:30:00.000000"
  },
  "calls": [
    {
      "uuid": "abc-def-123-456",
      "contact": {
        "phone": "+33612345678",
        "first_name": "Jean",
        "last_name": "Dupont",
        "email": "jean@example.com",
        "company": "TechCorp"
      },
      "status": "completed",
      "result": "lead",
      "duration": 127,
      "sentiment": "positive",
      "confidence": 0.92,
      "amd_result": "human",
      "metadata": {
        "objection_matched": "J'ai déjà une banque",
        "freestyle_turns": 2
      },
      "created_at": "2025-01-15T14:10:00.000000",
      "answered_at": "2025-01-15T14:10:03.000000",
      "ended_at": "2025-01-15T14:12:07.000000"
    }
  ]
}
```

**Exemple cURL** :

```bash
curl -H "X-API-Key: mypassword" \
  http://localhost:8000/api/exports/campaign/42/json \
  -o campaign_42.json

# Avec jq pour formater
curl -H "X-API-Key: mypassword" \
  http://localhost:8000/api/exports/campaign/42/json | jq '.'
```

---

### `GET /api/exports/audio/{call_uuid}` - Télécharger audio

Télécharge l'enregistrement audio d'un appel.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `call_uuid` | string | UUID de l'appel |

**Réponse** : `200 OK` (fichier WAV)

**Headers réponse** :
- `Content-Type: audio/wav`
- `Content-Disposition: attachment; filename=call_abc-123.wav`

**Erreurs** :
- `404 Not Found` : Appel introuvable ou pas d'enregistrement disponible

**Exemple cURL** :

```bash
# Télécharger audio
curl -H "X-API-Key: mypassword" \
  http://localhost:8000/api/exports/audio/abc-123-456 \
  -o call_recording.wav

# Lire directement avec ffplay
curl -H "X-API-Key: mypassword" \
  http://localhost:8000/api/exports/audio/abc-123-456 | ffplay -
```

---

### `GET /api/exports/transcript/{call_uuid}` - Télécharger transcription

Télécharge la transcription d'un appel.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `call_uuid` | string | UUID de l'appel |

**Query Parameters** :

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `format` | string | txt | Format (txt ou json) |

**Réponse format `txt`** : `200 OK` (text/plain)

```
[2025-01-15 14:10:05] Agent: Allô, bonjour Monsieur Dupont. Je suis Julie de TechCorp.
[2025-01-15 14:10:12] Contact: Oui bonjour.
[2025-01-15 14:10:15] Agent: Seriez-vous disponible pour une démo gratuite de 15 minutes ?
[2025-01-15 14:10:23] Contact: Pourquoi pas, de quoi s'agit-il exactement ?
...
```

**Réponse format `json`** : `200 OK` (application/json)

```json
{
  "call_uuid": "abc-123-456",
  "transcription": "[2025-01-15 14:10:05] Agent: Allô, bonjour...",
  "duration": 127,
  "sentiment": "positive"
}
```

**Headers réponse (format txt)** :
- `Content-Type: text/plain`
- `Content-Disposition: attachment; filename=transcript_abc-123.txt`

**Erreurs** :
- `404 Not Found` : Appel introuvable ou pas de transcription disponible

**Exemple cURL** :

```bash
# Format texte (défaut)
curl -H "X-API-Key: mypassword" \
  http://localhost:8000/api/exports/transcript/abc-123-456 \
  -o transcript.txt

# Format JSON
curl -H "X-API-Key: mypassword" \
  "http://localhost:8000/api/exports/transcript/abc-123-456?format=json" | jq '.'
```

---

### `GET /api/exports/summary/{campaign_id}` - Résumé campagne

Génère un résumé détaillé pour rapport.

**Authentification** : Requise

**Path Parameters** :

| Paramètre | Type | Description |
|-----------|------|-------------|
| `campaign_id` | int | ID de la campagne |

**Réponse** : `200 OK`

```json
{
  "campaign": {
    "id": 42,
    "name": "Prospection Q1 2025",
    "scenario": "scenario_finance_crypto",
    "status": "completed"
  },
  "summary": {
    "total_calls": 150,
    "completed_calls": 148,
    "completion_rate": "98.7%",
    "results": {
      "lead": 37,
      "not_interested": 68,
      "callback": 15,
      "no_answer": 2,
      "failed": 2,
      "wrong_number": 0,
      "answering_machine": 26
    },
    "conversion_rate": "25.0%",
    "average_duration": "114.2s",
    "date_range": {
      "started": "2025-01-15T14:00:00.000000",
      "completed": "2025-01-15T18:45:00.000000"
    }
  }
}
```

**Exemple cURL** :

```bash
curl -H "X-API-Key: mypassword" \
  http://localhost:8000/api/exports/summary/42 | jq '.'
```

---

## Codes d'erreur

### Format des erreurs

Toutes les erreurs sont retournées au format JSON standardisé :

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Description de l'erreur",
    "details": {}  // Optionnel
  }
}
```

### Codes HTTP et signification

| Code | Signification | Description |
|------|---------------|-------------|
| `200 OK` | Succès | Requête réussie |
| `201 Created` | Créé | Ressource créée avec succès |
| `204 No Content` | Aucun contenu | Suppression réussie |
| `400 Bad Request` | Requête invalide | Paramètres invalides ou action impossible |
| `401 Unauthorized` | Non autorisé | Authentification manquante ou invalide |
| `404 Not Found` | Non trouvé | Ressource introuvable |
| `422 Unprocessable Entity` | Entité non traitable | Erreur de validation Pydantic |
| `500 Internal Server Error` | Erreur serveur | Erreur interne non gérée |
| `503 Service Unavailable` | Service indisponible | Composant système défaillant |

### Exemples d'erreurs courantes

**401 - Authentification invalide** :

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or missing API password. Provide it via X-API-Key header or ?password= query param."
  }
}
```

**404 - Campagne non trouvée** :

```json
{
  "error": {
    "code": "HTTP_404",
    "message": "Campaign 999 not found"
  }
}
```

**400 - Action impossible** :

```json
{
  "error": {
    "code": "HTTP_400",
    "message": "Cannot start a completed campaign"
  }
}
```

**422 - Validation échouée** :

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "details": [
      {
        "loc": ["body", "contact_ids"],
        "msg": "field required",
        "type": "value_error.missing"
      }
    ]
  }
}
```

---

## Exemples cURL

### Créer et lancer une campagne complète

```bash
#!/bin/bash
API_KEY="mypassword"
BASE_URL="http://localhost:8000"

# 1. Créer la campagne
echo "Creating campaign..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/campaigns/" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Campaign",
    "contact_ids": [1, 2, 3, 4, 5],
    "scenario": "scenario_test_demo",
    "max_concurrent_calls": 3
  }')

CAMPAIGN_ID=$(echo $RESPONSE | jq -r '.id')
echo "Campaign created: $CAMPAIGN_ID"

# 2. Démarrer la campagne
echo "Starting campaign..."
curl -s -X POST "$BASE_URL/api/campaigns/$CAMPAIGN_ID/start" \
  -H "X-API-Key: $API_KEY" | jq '.'

# 3. Monitorer en temps réel (boucle 30 secondes)
echo "Monitoring live stats for 30 seconds..."
for i in {1..6}; do
  echo "--- Update $i/6 ---"
  curl -s -H "X-API-Key: $API_KEY" \
    "$BASE_URL/api/stats/campaign/$CAMPAIGN_ID/live" | jq '.percentages'
  sleep 5
done

# 4. Récupérer stats finales
echo "Final stats:"
curl -s -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/stats/campaign/$CAMPAIGN_ID" | jq '.conversion'

# 5. Export CSV
echo "Exporting CSV..."
curl -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/exports/campaign/$CAMPAIGN_ID/csv" \
  -o "campaign_${CAMPAIGN_ID}.csv"

echo "Done!"
```

### Monitorer toutes les campagnes actives

```bash
#!/bin/bash
API_KEY="mypassword"
BASE_URL="http://localhost:8000"

# Récupérer toutes les campagnes actives
CAMPAIGNS=$(curl -s -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/campaigns/?status=running" | jq -r '.campaigns[].id')

# Afficher stats pour chaque campagne
for CAMPAIGN_ID in $CAMPAIGNS; do
  echo "=== Campaign $CAMPAIGN_ID ==="
  curl -s -H "X-API-Key: $API_KEY" \
    "$BASE_URL/api/stats/campaign/$CAMPAIGN_ID/live" | \
    jq '{name, completed, leads: .results.leads, rate: .percentages.leads}'
  echo ""
done
```

### Health check + métriques système

```bash
#!/bin/bash
BASE_URL="http://localhost:8000"

# Health check
echo "=== Health Status ==="
curl -s "$BASE_URL/health" | jq '.components | to_entries[] | {component: .key, status: .value.status}'

echo ""
echo "=== System Stats ==="
curl -s -H "X-API-Key: mypassword" "$BASE_URL/api/stats/system" | \
  jq '{version: .system.version, uptime: .system.uptime, active_campaigns: .campaigns.active, active_calls: .calls.active_now}'
```

---

## Exemples Python

### Client Python simple

```python
import requests
import json
from typing import Dict, List, Optional

class MiniBotClient:
    """Client Python pour API MiniBotPanel v3"""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    def create_campaign(
        self,
        name: str,
        contact_ids: List[int],
        scenario: str,
        description: str = None,
        max_concurrent_calls: int = 5
    ) -> Dict:
        """Crée une nouvelle campagne"""
        payload = {
            "name": name,
            "contact_ids": contact_ids,
            "scenario": scenario,
            "max_concurrent_calls": max_concurrent_calls
        }
        if description:
            payload["description"] = description

        response = requests.post(
            f"{self.base_url}/api/campaigns/",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def start_campaign(self, campaign_id: int) -> Dict:
        """Démarre une campagne"""
        response = requests.post(
            f"{self.base_url}/api/campaigns/{campaign_id}/start",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def get_live_stats(self, campaign_id: int) -> Dict:
        """Récupère les stats live"""
        response = requests.get(
            f"{self.base_url}/api/stats/campaign/{campaign_id}/live",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def export_csv(self, campaign_id: int, output_file: str):
        """Exporte les résultats en CSV"""
        response = requests.get(
            f"{self.base_url}/api/exports/campaign/{campaign_id}/csv",
            headers=self.headers,
            stream=True
        )
        response.raise_for_status()

        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def list_campaigns(self, status: str = None) -> Dict:
        """Liste les campagnes"""
        params = {}
        if status:
            params["status"] = status

        response = requests.get(
            f"{self.base_url}/api/campaigns/",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()


# Exemple d'utilisation
if __name__ == "__main__":
    # Initialiser client
    client = MiniBotClient(
        base_url="http://localhost:8000",
        api_key="mypassword"
    )

    # Créer campagne
    campaign = client.create_campaign(
        name="Test Python API",
        contact_ids=[1, 2, 3, 4, 5],
        scenario="scenario_test_demo",
        max_concurrent_calls=3
    )

    campaign_id = campaign["id"]
    print(f"Campaign created: {campaign_id}")

    # Démarrer
    client.start_campaign(campaign_id)
    print(f"Campaign {campaign_id} started")

    # Monitorer
    import time
    for i in range(5):
        stats = client.get_live_stats(campaign_id)
        print(f"[{i+1}/5] Completed: {stats['completed']}/{stats['total']} - Leads: {stats['results']['leads']}")
        time.sleep(5)

    # Export CSV
    client.export_csv(campaign_id, f"campaign_{campaign_id}.csv")
    print(f"Results exported to campaign_{campaign_id}.csv")
```

### Monitoring async avec asyncio

```python
import asyncio
import aiohttp
import json
from datetime import datetime

class AsyncMiniBotClient:
    """Client asynchrone pour monitoring en temps réel"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def get_live_stats(self, session: aiohttp.ClientSession, campaign_id: int):
        """Récupère stats live"""
        headers = {"X-API-Key": self.api_key}
        async with session.get(
            f"{self.base_url}/api/stats/campaign/{campaign_id}/live",
            headers=headers
        ) as response:
            return await response.json()

    async def monitor_campaign(self, campaign_id: int, interval: int = 5):
        """Monitore une campagne en continu"""
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    stats = await self.get_live_stats(session, campaign_id)

                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] Campaign {campaign_id}:")
                    print(f"  Completed: {stats['completed']}/{stats['total']} ({stats['percentages']['completion']})")
                    print(f"  Leads: {stats['results']['leads']} ({stats['percentages']['leads']})")
                    print(f"  In progress: {stats['in_progress']}")
                    print()

                    # Arrêter si campagne terminée
                    if stats['status'] in ['completed', 'cancelled']:
                        print(f"Campaign {campaign_id} finished with status: {stats['status']}")
                        break

                    await asyncio.sleep(interval)

                except Exception as e:
                    print(f"Error: {e}")
                    await asyncio.sleep(interval)


# Utilisation
async def main():
    client = AsyncMiniBotClient(
        base_url="http://localhost:8000",
        api_key="mypassword"
    )

    # Monitorer campagne ID 42
    await client.monitor_campaign(campaign_id=42, interval=5)

if __name__ == "__main__":
    asyncio.run(main())
```

### Analyse batch de campagnes

```python
import requests
import pandas as pd
from typing import List, Dict

class CampaignAnalyzer:
    """Analyseur de performances campagnes"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key}

    def get_all_campaigns(self, status: str = "completed") -> List[Dict]:
        """Récupère toutes les campagnes complétées"""
        response = requests.get(
            f"{self.base_url}/api/campaigns/",
            headers=self.headers,
            params={"status": status, "limit": 500}
        )
        response.raise_for_status()
        return response.json()["campaigns"]

    def get_campaign_stats(self, campaign_id: int) -> Dict:
        """Récupère stats complètes d'une campagne"""
        response = requests.get(
            f"{self.base_url}/api/stats/campaign/{campaign_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def analyze_performance(self) -> pd.DataFrame:
        """Analyse les performances globales"""
        campaigns = self.get_all_campaigns()

        data = []
        for campaign in campaigns:
            stats = self.get_campaign_stats(campaign["id"])

            # Extraire métriques clés
            conversion_rate = float(stats["conversion"]["rate"].rstrip("%"))
            avg_duration = float(stats["averages"]["duration"].rstrip("s"))

            data.append({
                "campaign_id": campaign["id"],
                "name": campaign["name"],
                "scenario": campaign["scenario"],
                "total_calls": stats["total"],
                "completed": stats["status"]["completed"],
                "leads": stats["results"]["lead"],
                "conversion_rate": conversion_rate,
                "avg_duration": avg_duration,
                "humans_detected": stats["amd"]["human"],
                "machines_detected": stats["amd"]["machine"]
            })

        return pd.DataFrame(data)

    def top_performing_scenarios(self, n: int = 5) -> pd.DataFrame:
        """Identifie les meilleurs scénarios"""
        df = self.analyze_performance()

        # Grouper par scénario
        scenario_perf = df.groupby("scenario").agg({
            "conversion_rate": "mean",
            "total_calls": "sum",
            "leads": "sum"
        }).sort_values("conversion_rate", ascending=False)

        return scenario_perf.head(n)


# Utilisation
if __name__ == "__main__":
    analyzer = CampaignAnalyzer(
        base_url="http://localhost:8000",
        api_key="mypassword"
    )

    # Analyser toutes les campagnes
    df = analyzer.analyze_performance()
    print("Campaign Performance Overview:")
    print(df[["name", "total_calls", "leads", "conversion_rate"]].to_string())

    print("\nTop 5 Scenarios by Conversion Rate:")
    top_scenarios = analyzer.top_performing_scenarios(n=5)
    print(top_scenarios.to_string())
```

---

## Rate Limiting & Performance

### Limites de l'API

| Limite | Valeur | Notes |
|--------|--------|-------|
| **Requêtes/seconde** | Illimité | Pas de rate limiting implémenté actuellement |
| **Timeout requête** | 30s | Timeout par défaut FastAPI |
| **Taille payload** | 10 MB | Limite FastAPI par défaut |
| **Contacts par campagne** | 10 000 | Limite validation Pydantic |
| **Appels simultanés** | 50 max | Configurable via `MAX_CONCURRENT_CALLS` |
| **Résultats pagination** | 500 max | Limite `limit` parameter |

### Cache et optimisations

**Endpoints avec cache** :
- `GET /api/stats/campaign/{id}/live` : Cache 5 secondes

**Optimisations recommandées** :
- Utiliser `/live` au lieu de `/stats/campaign/{id}` pour monitoring fréquent
- Paginer les résultats avec `limit` et `offset`
- Utiliser `status` filters pour réduire les résultats

### Middleware et logging

**Tous les endpoints sont loggés** :
```
2025-01-15 14:32:10 | INFO | 📥 GET /api/campaigns/
2025-01-15 14:32:10 | INFO | 📤 GET /api/campaigns/ - 200 - 0.045s
```

**CORS activé** :
- Origins : configurables via `API_CORS_ORIGINS`
- Methods : `GET, POST, PUT, PATCH, DELETE, OPTIONS`
- Headers : tous autorisés

---

## Webhooks (à venir)

**Note** : Le système de webhooks n'est pas encore implémenté dans v3.0.0, mais sera ajouté dans une version future.

### Webhooks planifiés

| Événement | URL | Description |
|-----------|-----|-------------|
| `campaign.started` | POST /webhooks/campaign/started | Campagne démarrée |
| `campaign.completed` | POST /webhooks/campaign/completed | Campagne terminée |
| `call.lead` | POST /webhooks/call/lead | Lead généré |
| `call.completed` | POST /webhooks/call/completed | Appel terminé |

---

## Support et contributions

### Ressources

- **Documentation** : `/documentation/GUIDE_UTILISATION.md`
- **Issues** : GitHub Issues
- **Swagger UI** : `http://localhost:8000/docs`

### Contact

Pour toute question ou bug, créer une issue GitHub avec :
- Version API (`GET /`)
- Endpoint concerné
- Body de la requête
- Réponse reçue
- Logs pertinents

---

**Version** : 3.0.0
**Dernière mise à jour** : 2025-01-15
**Licence** : Propriétaire
