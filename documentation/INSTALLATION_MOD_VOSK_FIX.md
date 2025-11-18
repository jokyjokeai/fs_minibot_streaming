# Installation mod_vosk avec libks vosk-fix

## Table des matières

1. [Problème](#problème)
2. [Solution](#solution)
3. [Prérequis](#prérequis)
4. [Installation complète](#installation-complète)
5. [Vérification](#vérification)
6. [Troubleshooting](#troubleshooting)
7. [Utilisation](#utilisation)

---

## Problème

### Erreur classique lors du chargement de mod_vosk

Quand on essaie de charger mod_vosk dans FreeSWITCH, on obtient cette erreur:

```
[CRIT] switch_loadable_module.c:1754 Error Loading module /usr/local/freeswitch/mod/mod_vosk.so
/usr/local/freeswitch/mod/mod_vosk.so: undefined symbol: ks_json_add_string_to_object
```

ou

```
undefined symbol: __ks_json_add_string_to_object
```

### Cause du problème

mod_vosk dépend de **libks** (SignalWire Kitchen Sink library), mais la version officielle de libks **ne contient pas** les fonctions JSON/WebSocket requises par mod_vosk.

Ces fonctions incluent:
- `ks_json_add_string_to_object`
- `ks_json_add_number_to_object`
- `ks_json_create_object`
- Autres fonctions spécifiques pour mod_vosk

### Pourquoi la libks officielle ne suffit pas?

mod_vosk nécessite des **patches spéciaux** qui ne sont pas encore mergés dans la branche principale de SignalWire/libks. Ces patches ajoutent des fonctionnalités JSON essentielles pour la communication avec Vosk.

---

## Solution

### La branche vosk-fix

**alphacep** (créateur de Vosk) maintient un fork de libks avec une branche spéciale `vosk-fix` qui contient tous les patches nécessaires.

**Repository**: https://github.com/alphacep/libks
**Branche**: `vosk-fix`

Cette branche contient:
- ✅ Toutes les fonctions JSON requises par mod_vosk
- ✅ Patches WebSocket pour communication Vosk
- ✅ Fixes de compatibilité FreeSWITCH

---

## Prérequis

### Système requis

- Ubuntu 20.04+ / Debian 11+
- FreeSWITCH compilé depuis les sources
- Accès sudo
- Outils de compilation (gcc, make, cmake, git)

### Vérifier FreeSWITCH

```bash
# FreeSWITCH doit être compilé depuis les sources
ls /usr/src/freeswitch/

# Vérifier que mod_vosk est présent
ls /usr/src/freeswitch/src/mod/asr_tts/mod_vosk/
```

---

## Installation complète

### Étape 1: Nettoyer les anciennes installations

Si vous avez déjà essayé d'installer libks, il faut tout nettoyer:

```bash
# Supprimer les anciennes libks
sudo rm -rf /tmp/libks
sudo rm -f /usr/lib/libks2.so*
sudo rm -f /usr/lib/pkgconfig/libks2.pc
sudo rm -rf /usr/include/libks2

# Nettoyer les symlinks
sudo rm -f /usr/include/libks

# Mettre à jour le cache des librairies
sudo ldconfig
```

### Étape 2: Cloner libks vosk-fix

```bash
cd /tmp
git clone --branch vosk-fix --single-branch https://github.com/alphacep/libks
cd libks
```

### Étape 3: Patcher pour OpenSSL 3.0 (Ubuntu 22.04+)

Si vous utilisez Ubuntu 22.04+ avec OpenSSL 3.0, appliquez ce patch:

```bash
# Éditer src/ks_ssl.c
nano src/ks_ssl.c

# Trouver la ligne (environ ligne 134):
CRYPTO_mem_ctrl(CRYPTO_MEM_CHECK_ON);

# Remplacer par:
// CRYPTO_mem_ctrl(CRYPTO_MEM_CHECK_ON); // Disabled for OpenSSL 3.0 compatibility
```

Ou via sed:

```bash
sed -i 's/CRYPTO_mem_ctrl(CRYPTO_MEM_CHECK_ON);/\/\/ CRYPTO_mem_ctrl(CRYPTO_MEM_CHECK_ON); \/\/ Disabled for OpenSSL 3.0 compatibility/' src/ks_ssl.c
```

### Étape 4: Compiler libks

```bash
cd /tmp/libks

# Configurer avec CMake
cmake .

# Compiler (utilise tous les cores CPU)
make -j$(nproc)

# Installer
sudo make install

# Mettre à jour le cache des librairies
sudo ldconfig
```

### Étape 5: Vérifier l'installation de libks

```bash
# Vérifier que la librairie est installée
ls -la /usr/lib/libks.so*

# Doit afficher:
# lrwxrwxrwx 1 root root     10 <date> /usr/lib/libks.so -> libks.so.1
# -rw-r--r-- 1 root root 733920 <date> /usr/lib/libks.so.1

# Vérifier que les headers sont installés
ls /usr/include/libks/ks_json.h

# Vérifier que la fonction existe
nm /usr/lib/libks.so.1 | grep ks_json_add_string_to_object

# Doit afficher quelque chose comme:
# 0000000000021219 T __ks_json_add_string_to_object
```

### Étape 6: Nettoyer l'ancienne compilation de mod_vosk

```bash
cd /usr/src/freeswitch

# Nettoyer mod_vosk
sudo make mod_vosk-clean

# Supprimer les anciens fichiers compilés
sudo rm -f /usr/src/freeswitch/src/mod/asr_tts/mod_vosk/.libs/mod_vosk.so
```

### Étape 7: Recompiler mod_vosk avec libks

```bash
cd /usr/src/freeswitch/src/mod/asr_tts/mod_vosk

# Méthode manuelle avec libtool (recommandée)
sudo /bin/bash /usr/src/freeswitch/libtool --tag=CC --mode=link gcc \
  -I/usr/include/uuid -I/usr/src/freeswitch/src/include \
  -fPIC -g -O2 -Wall -std=c99 \
  -shared -module -avoid-version -no-undefined \
  -rpath /usr/local/freeswitch/mod \
  -o mod_vosk.la \
  .libs/mod_vosk.o \
  /usr/src/freeswitch/libfreeswitch.la \
  -lks
```

**Note**: Si `.libs/mod_vosk.o` n'existe pas, compilez d'abord:

```bash
cd /usr/src/freeswitch
sudo make mod_vosk
```

### Étape 8: Installer mod_vosk

```bash
# Copier le module compilé vers FreeSWITCH
sudo cp /usr/src/freeswitch/src/mod/asr_tts/mod_vosk/.libs/mod_vosk.so \
     /usr/local/freeswitch/mod/
```

### Étape 9: Vérifier le linking

```bash
# Vérifier que libks est bien linkée
ldd /usr/local/freeswitch/mod/mod_vosk.so | grep libks

# Doit afficher:
# libks.so.1 => /usr/lib/libks.so.1 (0x00007xxxxx)

# Vérifier qu'il n'y a pas de librairies manquantes
ldd /usr/local/freeswitch/mod/mod_vosk.so | grep "not found"

# Ne doit rien afficher (pas de librairies manquantes)
```

### Étape 10: Charger mod_vosk dans FreeSWITCH

```bash
# Charger le module
fs_cli -x "load mod_vosk"

# Doit afficher:
# +OK Reloading XML
# +OK
```

---

## Vérification

### Vérifier que mod_vosk est chargé

```bash
# Vérifier l'existence du module
fs_cli -x "module_exists mod_vosk"
# Doit afficher: true

# Vérifier les logs FreeSWITCH
tail -50 /usr/local/freeswitch/log/freeswitch.log | grep vosk

# Doit afficher quelque chose comme:
# [CONSOLE] switch_loadable_module.c:1772 Successfully Loaded [mod_vosk]
# [NOTICE] switch_loadable_module.c:565 Adding ASR interface 'vosk'
```

### Tester avec l'intégration Python

Si vous avez le projet fs_minibot_streaming:

```bash
cd /home/jokyjokeai/Desktop/fs_minibot_streaming

# Activer l'environnement virtuel
source venv/bin/activate

# Lancer les tests d'intégration
python test_vosk_integration.py --all

# Doit afficher:
# ✅ PASS - service
# ✅ PASS - grammar
# ✅ PASS - commands
# ✅ PASS - module
# ✅ PASS - events
# 🎉 Tous les tests sont passés !
```

---

## Troubleshooting

### Erreur: "undefined symbol: ks_json_add_string_to_object"

**Cause**: libks n'est pas correctement linkée ou vous utilisez l'ancienne version.

**Solution**:
1. Vérifiez que vous avez bien cloné la branche `vosk-fix`:
   ```bash
   cd /tmp/libks
   git branch
   # Doit afficher: * vosk-fix
   ```

2. Vérifiez que la fonction existe dans libks:
   ```bash
   nm /usr/lib/libks.so.1 | grep ks_json_add_string_to_object
   ```

3. Vérifiez le linking de mod_vosk:
   ```bash
   ldd /usr/local/freeswitch/mod/mod_vosk.so | grep libks
   ```

   Si libks n'apparaît pas, recompilez mod_vosk avec l'étape 7.

### Erreur de compilation libks avec OpenSSL 3.0

**Erreur**:
```
error: 'CRYPTO_MEM_CHECK_ON' undeclared
```

**Solution**: Appliquez le patch OpenSSL 3.0 (Étape 3).

### libks.so.1 not found

**Erreur**:
```
error while loading shared libraries: libks.so.1: cannot open shared object file
```

**Solution**:
```bash
# Vérifier où est installée libks
find /usr -name "libks.so.1" 2>/dev/null

# Si elle est dans /usr/local/lib au lieu de /usr/lib:
sudo ln -s /usr/local/lib/libks.so.1 /usr/lib/libks.so.1

# Mettre à jour le cache
sudo ldconfig
```

### mod_vosk se charge mais ne fonctionne pas

**Vérifications**:

1. **Vérifier la configuration**:
   ```bash
   cat /usr/local/freeswitch/conf/autoload_configs/vosk.conf.xml
   ```

2. **Vérifier que le modèle existe**:
   ```bash
   ls -la /usr/share/vosk/model-fr/
   ```

3. **Vérifier les logs détaillés**:
   ```bash
   fs_cli
   > console loglevel DEBUG
   > reload mod_vosk
   ```

### mod_vosk.o n'existe pas lors de la compilation

**Solution**: Compilez d'abord mod_vosk normalement:

```bash
cd /usr/src/freeswitch
sudo make mod_vosk
```

Puis suivez l'étape 7 pour le relinking manuel.

---

## Utilisation

### Configuration de base

Éditez `/usr/local/freeswitch/conf/autoload_configs/vosk.conf.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration name="vosk.conf" description="Vosk ASR Configuration">
  <settings>
    <!-- Chemin vers le modèle Vosk (mode offline) -->
    <param name="model-path" value="/usr/share/vosk/model-fr"/>

    <!-- Sample rate (8kHz pour téléphonie) -->
    <param name="sample-rate" value="8000"/>

    <!-- Nombre de threads (2-4 recommandé) -->
    <param name="thread-count" value="4"/>

    <!-- Nombre max d'alternatives de transcription -->
    <param name="max-alternatives" value="3"/>
  </settings>
</configuration>
```

### Charger automatiquement au démarrage

Éditez `/usr/local/freeswitch/conf/autoload_configs/modules.conf.xml`:

```xml
<configuration name="modules.conf" description="Modules">
  <modules>
    <!-- ... autres modules ... -->

    <!-- ASR/TTS -->
    <load module="mod_vosk"/>

  </modules>
</configuration>
```

### Utiliser mod_vosk dans un dialplan

```xml
<action application="play_and_detect_speech"
        data="/path/to/audio.wav detect:vosk"/>
```

### Utiliser avec Python ESL

```python
from ESL import ESLconnection

conn = ESLconnection("127.0.0.1", "8021", "ClueCon")

# Activer la détection de parole avec Vosk
conn.api(f"uuid_play_and_detect_speech {call_uuid} /path/to/audio.wav detect:vosk")
```

---

## Résumé de l'installation (Quick Start)

```bash
# 1. Nettoyer
sudo rm -rf /tmp/libks /usr/lib/libks* /usr/include/libks*
sudo ldconfig

# 2. Cloner libks vosk-fix
cd /tmp
git clone --branch vosk-fix --single-branch https://github.com/alphacep/libks
cd libks

# 3. Patcher OpenSSL 3.0 (Ubuntu 22.04+)
sed -i 's/CRYPTO_mem_ctrl(CRYPTO_MEM_CHECK_ON);/\/\/ CRYPTO_mem_ctrl(CRYPTO_MEM_CHECK_ON);/' src/ks_ssl.c

# 4. Compiler et installer libks
cmake . && make -j$(nproc) && sudo make install && sudo ldconfig

# 5. Vérifier libks
nm /usr/lib/libks.so.1 | grep ks_json_add_string_to_object

# 6. Compiler mod_vosk
cd /usr/src/freeswitch
sudo make mod_vosk-clean
sudo make mod_vosk

# 7. Relinker avec libks
cd /usr/src/freeswitch/src/mod/asr_tts/mod_vosk
sudo /bin/bash /usr/src/freeswitch/libtool --tag=CC --mode=link gcc \
  -I/usr/include/uuid -I/usr/src/freeswitch/src/include \
  -fPIC -g -O2 -Wall -std=c99 \
  -shared -module -avoid-version -no-undefined \
  -rpath /usr/local/freeswitch/mod \
  -o mod_vosk.la .libs/mod_vosk.o \
  /usr/src/freeswitch/libfreeswitch.la -lks

# 8. Installer
sudo cp .libs/mod_vosk.so /usr/local/freeswitch/mod/

# 9. Vérifier linking
ldd /usr/local/freeswitch/mod/mod_vosk.so | grep libks

# 10. Charger dans FreeSWITCH
fs_cli -x "load mod_vosk"
fs_cli -x "module_exists mod_vosk"  # Doit afficher: true
```

---

## Références

- **libks vosk-fix**: https://github.com/alphacep/libks/tree/vosk-fix
- **mod_vosk source**: https://github.com/freeswitch/freeswitch/tree/master/src/mod/asr_tts/mod_vosk
- **Vosk documentation**: https://alphacephei.com/vosk/
- **FreeSWITCH mod_vosk docs**: https://freeswitch.org/confluence/display/FREESWITCH/mod_vosk

---

## Notes importantes

1. **Ne PAS utiliser libks2 de SignalWire** - Elle ne contient pas les fonctions requises
2. **Ne PAS utiliser la branche master de libks** - Utilisez uniquement `vosk-fix`
3. **Toujours vérifier le linking** avant de charger mod_vosk
4. **Patcher OpenSSL 3.0** sur Ubuntu 22.04+ est obligatoire
5. **Le relinking manuel** avec libtool est parfois nécessaire si `make mod_vosk-install` ne linke pas libks

---

**Document créé**: 16 novembre 2025
**Testé sur**: Ubuntu 22.04 LTS
**FreeSWITCH version**: 1.10.12-release
**libks version**: 1.5.1 (vosk-fix branch)
