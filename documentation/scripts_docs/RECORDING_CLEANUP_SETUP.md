# Setup Recording Cleanup Automatique
======================================

## Statistiques Actuelles

```
📁 Total Recordings: 215 files
📁 Total Size: 14.30 GB
💾 Disk Usage: 19.4% (183.70 GB / 944.78 GB)
💾 Free Space: 713.02 GB
```

**En production avec beaucoup d'appels**, les recordings peuvent rapidement saturer le disque!

Exemple: 1000 appels/jour × 5 minutes × 1.5 MB/min = **7.5 GB/jour** → **225 GB/mois**

## Configuration

Le cleanup est contrôlé via `.env`:

```bash
# Recording Cleanup (activé par défaut)
RECORDING_CLEANUP_ENABLED=true
RECORDING_RETENTION_DAYS=7              # Supprimer recordings > 7 jours
RECORDING_CLEANUP_DISK_THRESHOLD=80     # Déclencher cleanup si disque > 80%
RECORDING_CLEANUP_DISK_TARGET=70        # Objectif après cleanup: 70%
```

## Mode 1: Time-Based Cleanup (Recommandé)

Supprimer tous les recordings plus vieux que N jours.

### Test (Dry Run)
```bash
# Voir ce qui serait supprimé (sans supprimer)
./venv/bin/python scripts/cleanup_recordings.py --dry-run --days 7
```

### Exécution Manuelle
```bash
# Supprimer recordings > 7 jours
./venv/bin/python scripts/cleanup_recordings.py --days 7

# Supprimer recordings > 14 jours
./venv/bin/python scripts/cleanup_recordings.py --days 14
```

### Automation via Cron (Recommandé)

Exécuter automatiquement tous les jours à 2h du matin:

```bash
# Éditer crontab
crontab -e

# Ajouter ligne (adapter chemins):
0 2 * * * /home/jokyjokeai/Desktop/fs_minibot_streaming/venv/bin/python /home/jokyjokeai/Desktop/fs_minibot_streaming/scripts/cleanup_recordings.py --days 7 >> /home/jokyjokeai/Desktop/fs_minibot_streaming/logs/cleanup.log 2>&1
```

**IMPORTANT**: Utiliser chemins ABSOLUS dans cron!

### Automation via Systemd Timer (Alternative)

1. Créer service systemd:
```bash
sudo nano /etc/systemd/system/minibot-cleanup.service
```

Contenu:
```ini
[Unit]
Description=MiniBotPanel - Recordings Cleanup
After=network.target

[Service]
Type=oneshot
User=jokyjokeai
WorkingDirectory=/home/jokyjokeai/Desktop/fs_minibot_streaming
ExecStart=/home/jokyjokeai/Desktop/fs_minibot_streaming/venv/bin/python scripts/cleanup_recordings.py --days 7
StandardOutput=append:/home/jokyjokeai/Desktop/fs_minibot_streaming/logs/cleanup.log
StandardError=append:/home/jokyjokeai/Desktop/fs_minibot_streaming/logs/cleanup.log
```

2. Créer timer systemd:
```bash
sudo nano /etc/systemd/system/minibot-cleanup.timer
```

Contenu:
```ini
[Unit]
Description=MiniBotPanel - Daily Recordings Cleanup
Requires=minibot-cleanup.service

[Timer]
# Exécuter tous les jours à 2h du matin
OnCalendar=daily
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

3. Activer timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable minibot-cleanup.timer
sudo systemctl start minibot-cleanup.timer

# Vérifier status
sudo systemctl status minibot-cleanup.timer
sudo systemctl list-timers | grep minibot
```

## Mode 2: Disk-Based Cleanup

Supprimer vieux recordings jusqu'à atteindre target disk usage.

**Utile en production** si volume d'appels variable.

### Test (Dry Run)
```bash
# Simuler cleanup si disque > 80%
./venv/bin/python scripts/cleanup_recordings.py --dry-run --disk-mode --threshold 80 --target 70
```

### Exécution Manuelle
```bash
# Si disque > 80%, supprimer jusqu'à 70%
./venv/bin/python scripts/cleanup_recordings.py --disk-mode --threshold 80 --target 70
```

### Automation (Même principe que time-based)

Cron:
```bash
# Vérifier disk usage toutes les heures, nettoyer si besoin
0 * * * * /home/jokyjokeai/Desktop/fs_minibot_streaming/venv/bin/python /home/jokyjokeai/Desktop/fs_minibot_streaming/scripts/cleanup_recordings.py --disk-mode --threshold 80 --target 70 >> /home/jokyjokeai/Desktop/fs_minibot_streaming/logs/cleanup.log 2>&1
```

## Monitoring (Stats Seulement)

Voir statistiques sans supprimer:

```bash
./venv/bin/python scripts/cleanup_recordings.py --no-cleanup
```

Output:
```
📊 Current Status:
----------------------------------------------------------------------
💾 Disk Usage: 183.70 GB / 944.78 GB (19.4%)
💾 Free Space: 713.02 GB
📁 Total Recordings: 215 files
📁 Total Size: 14.30 GB
📅 Oldest Recording: 2025-11-10 11:20:20
📅 Newest Recording: 2025-11-10 21:14:12
```

## Recommandations Production

1. **Time-based cleanup quotidien**:
   - Rétention: 7 jours (RECORDING_RETENTION_DAYS=7)
   - Cron: Tous les jours à 2h du matin
   - Prévient accumulation progressive

2. **Disk-based cleanup horaire** (backup):
   - Seuil: 80% (RECORDING_CLEANUP_DISK_THRESHOLD=80)
   - Target: 70% (RECORDING_CLEANUP_DISK_TARGET=70)
   - Cron: Toutes les heures
   - Protection contre saturation soudaine

3. **Monitoring**:
   - Logs: `/home/jokyjokeai/Desktop/fs_minibot_streaming/logs/cleanup.log`
   - Alertes si disque > 85% (à configurer séparément)

4. **Ajuster rétention selon volume**:
   - Faible volume: 14-30 jours
   - Volume moyen: 7 jours
   - Fort volume: 3-5 jours

## Désactiver Cleanup

Si vous voulez gérer manuellement:

```bash
# Dans .env
RECORDING_CLEANUP_ENABLED=false
```

Le script continuera de fonctionner en mode `--dry-run` même si désactivé.

## Logs

Tous les nettoyages sont loggés avec détails:

```
2025-11-10 02:00:00 | INFO     | 🧹 Starting cleanup: delete recordings older than 7 days
2025-11-10 02:00:00 | DEBUG    | Deleting: 0c2a3b4c-5d6e-7f8g.wav (23.45 MB, created 2025-11-03 15:30:45)
2025-11-10 02:00:05 | INFO     | ✅ Cleanup complete: 42 files deleted, 1.23 GB freed
```

## Troubleshooting

### Permission denied
```bash
# Vérifier permissions sur répertoire recordings
ls -la /usr/local/freeswitch/recordings/

# Si besoin, ajuster permissions (selon config FreeSWITCH)
sudo chown -R jokyjokeai:jokyjokeai /usr/local/freeswitch/recordings/
```

### Cron ne s'exécute pas
```bash
# Vérifier logs cron
sudo tail -f /var/log/syslog | grep CRON

# Vérifier chemin absolu Python
which python3
/home/jokyjokeai/Desktop/fs_minibot_streaming/venv/bin/python  # Utiliser ce chemin complet!
```

### Script ne trouve pas config
```bash
# Vérifier que script s'exécute depuis répertoire projet
cd /home/jokyjokeai/Desktop/fs_minibot_streaming
./venv/bin/python scripts/cleanup_recordings.py --dry-run
```
