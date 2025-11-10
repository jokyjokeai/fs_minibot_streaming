# Installation Systemd - Recording Cleanup Service

Ce guide explique comment installer le service de nettoyage automatique des recordings.

## Installation

### 1. Copier les fichiers systemd

```bash
sudo cp systemd/minibot-recording-cleanup.service /etc/systemd/system/
sudo cp systemd/minibot-recording-cleanup.timer /etc/systemd/system/
```

### 2. Recharger systemd

```bash
sudo systemctl daemon-reload
```

### 3. Activer et démarrer le timer

```bash
# Activer le timer (démarrage auto au boot)
sudo systemctl enable minibot-recording-cleanup.timer

# Démarrer le timer
sudo systemctl start minibot-recording-cleanup.timer
```

### 4. Vérifier le statut

```bash
# Vérifier que le timer est actif
sudo systemctl status minibot-recording-cleanup.timer

# Voir quand sera la prochaine exécution
sudo systemctl list-timers | grep minibot

# Output attendu:
# NEXT                         LEFT          LAST                         PASSED  UNIT                              ACTIVATES
# Tue 2025-11-11 03:00:00 CET  5h 45min left n/a                          n/a     minibot-recording-cleanup.timer   minibot-recording-cleanup.service
```

## Test du Service

### Test immédiat (sans attendre 3h du matin)

```bash
# Exécuter le service manuellement
sudo systemctl start minibot-recording-cleanup.service

# Voir les logs en temps réel
sudo journalctl -u minibot-recording-cleanup.service -f

# Ou voir logs dans fichier
tail -f /home/jokyjokeai/Desktop/fs_minibot_streaming/logs/recording_cleanup.log
```

### Test en dry-run (simulation)

```bash
# Exécuter manuellement en dry-run
/home/jokyjokeai/Desktop/fs_minibot_streaming/venv/bin/python \
  /home/jokyjokeai/Desktop/fs_minibot_streaming/system/services/recording_cleanup_service.py \
  --dry-run
```

## Monitoring

### Voir les logs

```bash
# Logs systemd (journal)
sudo journalctl -u minibot-recording-cleanup.service -n 50

# Logs fichier
tail -50 /home/jokyjokeai/Desktop/fs_minibot_streaming/logs/recording_cleanup.log

# Logs en temps réel
sudo journalctl -u minibot-recording-cleanup.service -f
```

### Vérifier historique exécutions

```bash
# Voir les 10 dernières exécutions
sudo systemctl status minibot-recording-cleanup.service

# Logs détaillés avec timestamps
sudo journalctl -u minibot-recording-cleanup.service --since "7 days ago"
```

## Configuration

Le service utilise la configuration dans `/home/jokyjokeai/Desktop/fs_minibot_streaming/.env`:

```bash
RECORDING_CLEANUP_ENABLED=true          # Activer/désactiver
RECORDING_RETENTION_DAYS=7              # Supprimer > 7 jours
RECORDING_CLEANUP_DISK_THRESHOLD=80     # Si disque > 80%
RECORDING_CLEANUP_DISK_TARGET=70        # Nettoyer jusqu'à 70%
```

Pour modifier la configuration:
```bash
nano /home/jokyjokeai/Desktop/fs_minibot_streaming/.env
# Pas besoin de redémarrer le timer, changements pris en compte à la prochaine exécution
```

## Changer l'Heure d'Exécution

Par défaut: **3h00 du matin**

Pour changer:
```bash
# Éditer le timer
sudo nano /etc/systemd/system/minibot-recording-cleanup.timer

# Modifier la ligne OnCalendar:
# Exemples:
# OnCalendar=*-*-* 02:00:00    # 2h du matin
# OnCalendar=*-*-* 04:30:00    # 4h30 du matin
# OnCalendar=daily             # Minuit
# OnCalendar=*-*-* 03:00:00,15:00:00   # 3h ET 15h

# Recharger
sudo systemctl daemon-reload
sudo systemctl restart minibot-recording-cleanup.timer
```

## Désactiver le Service

```bash
# Stopper le timer
sudo systemctl stop minibot-recording-cleanup.timer

# Désactiver le timer (ne démarrera plus au boot)
sudo systemctl disable minibot-recording-cleanup.timer

# Vérifier
sudo systemctl status minibot-recording-cleanup.timer
```

## Désinstaller

```bash
# Stopper et désactiver
sudo systemctl stop minibot-recording-cleanup.timer
sudo systemctl disable minibot-recording-cleanup.timer

# Supprimer fichiers
sudo rm /etc/systemd/system/minibot-recording-cleanup.service
sudo rm /etc/systemd/system/minibot-recording-cleanup.timer

# Recharger
sudo systemctl daemon-reload
```

## Troubleshooting

### Le service ne démarre pas

```bash
# Vérifier erreurs
sudo systemctl status minibot-recording-cleanup.service
sudo journalctl -u minibot-recording-cleanup.service -n 50

# Vérifier permissions
ls -la /home/jokyjokeai/Desktop/fs_minibot_streaming/system/services/recording_cleanup_service.py

# Vérifier que l'utilisateur existe
id jokyjokeai
```

### Permissions denied sur /usr/local/freeswitch/recordings/

```bash
# Vérifier permissions
ls -la /usr/local/freeswitch/recordings/

# Option 1: Ajouter utilisateur au groupe freeswitch
sudo usermod -aG freeswitch jokyjokeai

# Option 2: Changer ownership (si FreeSWITCH tourne en tant que jokyjokeai)
sudo chown -R jokyjokeai:jokyjokeai /usr/local/freeswitch/recordings/

# Relancer service
sudo systemctl restart minibot-recording-cleanup.service
```

### Le timer ne se déclenche jamais

```bash
# Vérifier que le timer est bien actif
sudo systemctl is-active minibot-recording-cleanup.timer

# Vérifier la prochaine exécution
sudo systemctl list-timers --all | grep minibot

# Si "n/a", le timer n'est pas actif
sudo systemctl start minibot-recording-cleanup.timer
sudo systemctl enable minibot-recording-cleanup.timer
```

## Logs Format

Le service produit des logs détaillés:

```
2025-11-11 03:00:01 | INFO     | ======================================================================
2025-11-11 03:00:01 | INFO     | 🧹 MiniBotPanel - Recording Cleanup Service
2025-11-11 03:00:01 | INFO     | 📅 Started at: 2025-11-11 03:00:01
2025-11-11 03:00:01 | INFO     | ======================================================================
2025-11-11 03:00:01 | INFO     |
📊 Status Before Cleanup:
2025-11-11 03:00:01 | INFO     | ----------------------------------------------------------------------
2025-11-11 03:00:01 | INFO     | 💾 Disk: 183.70 GB / 944.78 GB (19.4%)
2025-11-11 03:00:01 | INFO     | 📁 Recordings: 215 files (14.30 GB)
2025-11-11 03:00:01 | INFO     | 📅 Oldest: 2025-11-04 11:20:20
2025-11-11 03:00:01 | INFO     |
🧹 Running Time-Based Cleanup:
2025-11-11 03:00:01 | INFO     | ----------------------------------------------------------------------
2025-11-11 03:00:01 | INFO     | Retention policy: Delete recordings older than 7 days
2025-11-11 03:00:02 | INFO     |
📊 Time-Based Cleanup Results:
2025-11-11 03:00:02 | INFO     | ----------------------------------------------------------------------
2025-11-11 03:00:02 | INFO     | Deleted: 42 files
2025-11-11 03:00:02 | INFO     | Freed: 3.21 GB
2025-11-11 03:00:02 | INFO     |
✅ Cleanup completed successfully
2025-11-11 03:00:02 | INFO     | 📅 Finished at: 2025-11-11 03:00:02
2025-11-11 03:00:02 | INFO     | ======================================================================
```

## Monitoring Production

Pour production, recommandé d'ajouter monitoring:

```bash
# Créer script de monitoring
cat > /home/jokyjokeai/Desktop/fs_minibot_streaming/scripts/check_cleanup_health.sh <<'EOF'
#!/bin/bash
LOG_FILE="/home/jokyjokeai/Desktop/fs_minibot_streaming/logs/recording_cleanup.log"
ALERT_EMAIL="admin@example.com"

# Vérifier dernière exécution < 25h (quotidien)
LAST_RUN=$(grep "Started at:" "$LOG_FILE" | tail -1 | cut -d'|' -f1)
if [ -z "$LAST_RUN" ]; then
    echo "WARNING: No cleanup logs found!" | mail -s "MiniBotPanel Cleanup Alert" "$ALERT_EMAIL"
fi

# Vérifier erreurs récentes
ERRORS=$(grep -c "ERROR" "$LOG_FILE" | tail -50)
if [ "$ERRORS" -gt 0 ]; then
    echo "WARNING: $ERRORS errors in last 50 lines!" | mail -s "MiniBotPanel Cleanup Alert" "$ALERT_EMAIL"
fi
EOF

chmod +x /home/jokyjokeai/Desktop/fs_minibot_streaming/scripts/check_cleanup_health.sh

# Cron pour vérifier santé (1x/jour)
# crontab -e
# 0 4 * * * /home/jokyjokeai/Desktop/fs_minibot_streaming/scripts/check_cleanup_health.sh
```
