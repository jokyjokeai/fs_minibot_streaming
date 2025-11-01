# Configuration FreeSWITCH pour MiniBotPanel

## 📋 Installation Rapide

Ces fichiers sont des **modèles** de configuration FreeSWITCH pour faire fonctionner MiniBotPanel.

### 1. Copier les fichiers

```bash
# ESL (Event Socket) - OBLIGATOIRE
sudo cp event_socket.conf.xml /etc/freeswitch/autoload_configs/

# Modules - OBLIGATOIRE
sudo cp modules.conf.xml /etc/freeswitch/autoload_configs/

# Dialplan pour appels sortants
sudo cp dialplan_outbound.xml /etc/freeswitch/dialplan/

# Gateway SIP (remplacer avec vos infos)
sudo cp gateway_example.xml /etc/freeswitch/sip_profiles/external/
```

### 2. Éditer les fichiers

⚠️ **IMPORTANT** : Modifier ces valeurs :

#### event_socket.conf.xml
- Changer le mot de passe `ClueCon` par un mot de passe sécurisé
- Mettre à jour dans `.env` : `FREESWITCH_ESL_PASSWORD=votre_mot_de_passe`

#### gateway_example.xml
- Remplacer avec les infos de votre provider SIP :
  - `proxy` : Serveur SIP du provider
  - `username` : Votre identifiant
  - `password` : Votre mot de passe
  - `caller-id-number` : Votre numéro de téléphone

### 3. Recharger FreeSWITCH

```bash
# Recharger la config
fs_cli -x "reloadxml"

# Vérifier ESL
fs_cli -x "show api"

# Vérifier gateway
fs_cli -x "sofia status gateway gateway1"
```

## 📚 Fichiers fournis

### event_socket.conf.xml
Configuration ESL pour que Python puisse contrôler FreeSWITCH.

### modules.conf.xml
Liste des modules à charger (seulement ceux nécessaires).

### dialplan_outbound.xml
Règles pour les appels sortants avec AMD.

### gateway_example.xml
Modèle de configuration pour votre provider SIP.

## ✅ Vérification

Pour vérifier que tout fonctionne :

```bash
# Test connexion ESL depuis Python
python3 -c "
import ESL
con = ESL.ESLconnection('127.0.0.1', '8021', 'votre_mot_de_passe')
if con.connected():
    print('✅ ESL OK')
else:
    print('❌ ESL Failed')
"
```

## 🚨 Sécurité

1. **Ne jamais** laisser le mot de passe par défaut
2. **Limiter** l'accès ESL à localhost uniquement (127.0.0.1)
3. **Firewall** : Bloquer le port 8021 depuis l'extérieur

## 🆘 Debug

Si ça ne marche pas :

```bash
# Logs FreeSWITCH
tail -f /var/log/freeswitch/freeswitch.log

# Vérifier que mod_event_socket est chargé
fs_cli -x "show modules" | grep event_socket

# Tester un appel manuel
fs_cli -x "originate sofia/gateway/gateway1/+33612345678 &park()"
```

## 📝 Notes

- Ces fichiers sont des **modèles minimalistes**
- Adaptez selon vos besoins
- Pas besoin de plus pour faire fonctionner MiniBotPanel