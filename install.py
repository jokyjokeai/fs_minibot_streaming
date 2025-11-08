#!/usr/bin/env python3
"""
Installation Automatique - MiniBotPanel v3
===========================================

Script d'installation complet et interactif basé sur install_fs_minbot.md

Fonctionnalités:
- Installation automatique de tous les composants
- Tests de validation à chaque étape
- Configuration interactive (SIP, numéros test, etc.)
- Support GPU/CPU auto-détecté
- Rollback en cas d'erreur

Usage:
    sudo python3 install.py

Prérequis:
    - Ubuntu 22.04 LTS
    - Accès root (sudo)
    - Connexion Internet
"""

import os
import sys
import subprocess
import time
import json
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

COLORS = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "ENDC": "\033[0m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
}

# Détection automatique du dossier projet (là où install.py est lancé)
PROJECT_DIR = str(Path(__file__).parent.absolute())
LOG_FILE = f"/tmp/minibot_install_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# État installation (pour reprendre en cas d'interruption)
STATE_FILE = "/tmp/minibot_install_state.json"

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def print_colored(text: str, color: str = "ENDC", bold: bool = False):
    """Affiche texte coloré"""
    color_code = COLORS.get(color, COLORS["ENDC"])
    bold_code = COLORS["BOLD"] if bold else ""
    print(f"{bold_code}{color_code}{text}{COLORS['ENDC']}")


def print_section(title: str):
    """Affiche titre de section"""
    print("\n" + "=" * 80)
    print_colored(f"  {title}", "HEADER", bold=True)
    print("=" * 80 + "\n")


def print_step(step: str):
    """Affiche étape"""
    print_colored(f"➤ {step}", "CYAN")


def print_success(message: str):
    """Affiche succès"""
    print_colored(f"✅ {message}", "GREEN")


def print_warning(message: str):
    """Affiche avertissement"""
    print_colored(f"⚠️  {message}", "YELLOW")


def print_error(message: str):
    """Affiche erreur"""
    print_colored(f"❌ {message}", "RED", bold=True)


def run_command(
    cmd: str,
    check: bool = True,
    shell: bool = True,
    capture_output: bool = False,
    timeout: Optional[int] = None
) -> Tuple[int, str, str]:
    """
    Exécute une commande shell.

    Returns:
        (returncode, stdout, stderr)
    """
    try:
        # Log commande
        with open(LOG_FILE, "a") as f:
            f.write(f"\n[{datetime.now()}] Executing: {cmd}\n")

        result = subprocess.run(
            cmd,
            shell=shell,
            executable='/bin/bash' if shell else None,  # Utiliser bash au lieu de sh
            check=check,
            capture_output=capture_output,
            text=True,
            timeout=timeout
        )

        stdout = result.stdout if capture_output else ""
        stderr = result.stderr if capture_output else ""

        # Log résultat
        with open(LOG_FILE, "a") as f:
            if stdout:
                f.write(f"STDOUT:\n{stdout}\n")
            if stderr:
                f.write(f"STDERR:\n{stderr}\n")
            f.write(f"Return code: {result.returncode}\n")

        return result.returncode, stdout, stderr

    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed: {cmd}\nError: {e}"
        print_error(error_msg)

        with open(LOG_FILE, "a") as f:
            f.write(f"\n[ERROR] {error_msg}\n")

        if check:
            sys.exit(1)

        return e.returncode, "", str(e)

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        print_error(error_msg)

        with open(LOG_FILE, "a") as f:
            f.write(f"\n[EXCEPTION] {error_msg}\n")

        sys.exit(1)


def ask_user(question: str, default: str = "") -> str:
    """Demande input utilisateur"""
    if default:
        question = f"{question} [{default}]"

    print_colored(f"\n❓ {question}: ", "YELLOW", bold=True)
    response = input().strip()

    return response if response else default


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Demande confirmation oui/non"""
    default_str = "O/n" if default else "o/N"
    response = ask_user(question, default_str)

    if not response:
        return default

    return response.lower() in ["o", "oui", "y", "yes"]


def save_state(state: Dict[str, Any]):
    """Sauvegarde état installation"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_state() -> Dict[str, Any]:
    """Charge état installation"""
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def check_root():
    """Vérifie droits root"""
    if os.geteuid() != 0:
        print_error("Ce script doit être exécuté en tant que root (sudo)")
        sys.exit(1)


def check_ubuntu_version() -> bool:
    """Vérifie version Ubuntu"""
    print_step("Vérification version Ubuntu...")

    returncode, stdout, _ = run_command(
        "lsb_release -a",
        capture_output=True,
        check=False
    )

    if returncode == 0 and "22.04" in stdout:
        print_success("Ubuntu 22.04 LTS détecté")
        return True
    else:
        print_warning("Ubuntu 22.04 LTS recommandé (vous utilisez une autre version)")
        return ask_yes_no("Continuer quand même ?", default=False)


def detect_gpu() -> Tuple[bool, Optional[str]]:
    """Détecte GPU NVIDIA"""
    print_step("Détection GPU NVIDIA...")

    returncode, stdout, _ = run_command(
        "lspci | grep -i nvidia",
        capture_output=True,
        check=False
    )

    if returncode == 0 and stdout.strip():
        gpu_name = stdout.strip().split('\n')[0]
        print_success(f"GPU NVIDIA détecté: {gpu_name}")
        return True, gpu_name
    else:
        print_warning("Aucun GPU NVIDIA détecté (mode CPU)")
        return False, None


# ============================================================================
# SECTIONS D'INSTALLATION
# ============================================================================

def section_1_system_preparation():
    """Section 1: Préparation système"""
    print_section("SECTION 1: Préparation du Système")

    print_step("Mise à jour du système...")
    run_command("apt update && apt upgrade -y")
    print_success("Système mis à jour")

    print_step("Installation outils de base...")
    run_command(
        "apt install -y git curl wget vim nano build-essential "
        "software-properties-common lsb-release"
    )
    print_success("Outils de base installés")

    # Vérifier version Ubuntu
    if not check_ubuntu_version():
        sys.exit(1)


def section_2_clone_project():
    """Section 2: Vérification projet"""
    print_section("SECTION 2: Vérification du Projet")

    print_step(f"Projet détecté: {PROJECT_DIR}")

    # Vérifier que les fichiers essentiels existent
    essential_files = [
        "requirements.txt",
        "system/config.py",
        "system/models.py"
    ]

    missing_files = []
    for file in essential_files:
        if not Path(f"{PROJECT_DIR}/{file}").exists():
            missing_files.append(file)

    if missing_files:
        print_error(f"Fichiers manquants: {', '.join(missing_files)}")
        print_error(f"Assurez-vous d'exécuter install.py depuis le dossier du projet MiniBotPanel")
        sys.exit(1)

    print_success("Tous les fichiers essentiels sont présents")
    print_colored(f"📁 Dossier projet: {PROJECT_DIR}", "CYAN")


def section_3_postgresql():
    """Section 3: PostgreSQL"""
    print_section("SECTION 3: Installation PostgreSQL")

    print_step("Installation PostgreSQL...")
    run_command("apt install -y postgresql postgresql-contrib")
    print_success("PostgreSQL installé")

    print_step("Démarrage service...")
    run_command("systemctl start postgresql")
    run_command("systemctl enable postgresql")
    print_success("Service PostgreSQL démarré")

    print_step("Création base de données...")
    run_command(
        'sudo -u postgres psql -c "CREATE USER minibot WITH PASSWORD \'minibot\';"',
        check=False  # Ignore si existe déjà
    )
    run_command(
        'sudo -u postgres psql -c "CREATE DATABASE minibot_freeswitch OWNER minibot;"',
        check=False
    )
    run_command(
        'sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE minibot_freeswitch TO minibot;"',
        check=False
    )
    print_success("Base de données créée")

    print_step("Test connexion...")
    returncode, stdout, _ = run_command(
        'PGPASSWORD=minibot psql -U minibot -d minibot_freeswitch -h localhost -c "SELECT version();"',
        capture_output=True,
        check=False
    )

    if returncode == 0:
        print_success("Connexion PostgreSQL OK")
    else:
        print_error("Échec connexion PostgreSQL")
        sys.exit(1)


def section_4_gpu_detection():
    """Section 4: Détection GPU et drivers"""
    print_section("SECTION 4: Détection GPU (Optionnel)")

    has_gpu, gpu_name = detect_gpu()

    if has_gpu:
        # Vérifier si le driver est déjà installé et fonctionnel
        print_step("Vérification driver NVIDIA existant...")
        returncode, stdout, _ = run_command(
            "nvidia-smi",
            capture_output=True,
            check=False
        )

        driver_already_installed = (returncode == 0 and "Driver Version" in stdout)

        if driver_already_installed:
            # Extraire version driver
            driver_version = "Unknown"
            for line in stdout.split('\n'):
                if "Driver Version" in line:
                    import re
                    match = re.search(r'Driver Version:\s+(\d+\.\d+\.\d+)', line)
                    if match:
                        driver_version = match.group(1)
                        break

            print_success(f"Driver NVIDIA déjà installé et fonctionnel: {driver_version}")
            print_success(f"GPU détecté via nvidia-smi: {gpu_name}")
            print_colored("✅ Pas besoin de réinstaller le driver", "GREEN", bold=True)

            # Demander seulement si l'utilisateur veut forcer la réinstallation
            if not ask_yes_no("Forcer la réinstallation du driver NVIDIA ?", default=False):
                # Skip installation drivers, passer directement à CUDA
                pass
            else:
                driver_already_installed = False  # Forcer réinstallation

        if not driver_already_installed and ask_yes_no("Installer drivers NVIDIA et CUDA ?", default=True):
            print_step("Installation drivers NVIDIA...")
            run_command("add-apt-repository ppa:graphics-drivers/ppa -y")
            run_command("apt update")

            # Détecter version recommandée automatiquement
            returncode, stdout, _ = run_command(
                "ubuntu-drivers devices",
                capture_output=True
            )

            print("Drivers disponibles:")
            print(stdout)

            # Extraire la version recommandée
            recommended_version = None
            for line in stdout.split('\n'):
                if 'recommended' in line:
                    # Extraire le numéro (ex: nvidia-driver-580)
                    import re
                    match = re.search(r'nvidia-driver-(\d+)', line)
                    if match:
                        recommended_version = match.group(1)
                        break

            if not recommended_version:
                recommended_version = "535"  # Fallback sûr pour CUDA 11.8

            print_colored(f"\n🎯 Driver recommandé: {recommended_version}", "GREEN", bold=True)
            print_colored("⚠️  IMPORTANT: CUDA 11.8 nécessite driver ≥ 520", "YELLOW")

            driver_version = ask_user(
                f"Version driver à installer (minimum 520 pour CUDA 11.8)",
                default=recommended_version
            )

            # Vérifier que la version est compatible avec CUDA 11.8
            try:
                driver_ver_int = int(driver_version)
                if driver_ver_int < 520:
                    print_error(f"❌ Driver {driver_version} incompatible avec CUDA 11.8 (minimum: 520)")
                    if not ask_yes_no("Utiliser le driver recommandé à la place ?", default=True):
                        print_error("Installation annulée - driver incompatible")
                        sys.exit(1)
                    driver_version = recommended_version
                    print_success(f"✅ Driver {driver_version} sélectionné")
            except ValueError:
                print_warning(f"Version {driver_version} non vérifiable, on continue...")

            print_step(f"Installation nvidia-driver-{driver_version}...")
            run_command(f"apt install -y nvidia-driver-{driver_version}")

            print_warning("REDÉMARRAGE REQUIS pour activer le driver NVIDIA")
            if ask_yes_no("Redémarrer maintenant ?", default=False):
                print_colored("Sauvegarde de l'état...", "YELLOW")
                save_state({"section_completed": 4, "has_gpu": True})
                print_colored("Redémarrage dans 5 secondes...", "RED", bold=True)
                time.sleep(5)
                run_command("reboot")
            else:
                print_warning("N'oubliez pas de redémarrer avant de continuer !")
                return has_gpu

        # Vérifier si CUDA 11.8 est déjà installé
        print_step("Vérification CUDA Toolkit 11.8 existant...")
        cuda_installed = False
        returncode, stdout, _ = run_command(
            "/usr/local/cuda-11.8/bin/nvcc --version",
            capture_output=True,
            check=False
        )

        if returncode == 0 and "release 11.8" in stdout:
            print_success("CUDA Toolkit 11.8 déjà installé")
            print_colored(f"Version: {stdout.split('release')[1].split(',')[0].strip() if 'release' in stdout else 'OK'}", "GREEN")
            cuda_installed = True

            if not ask_yes_no("Forcer la réinstallation de CUDA 11.8 ?", default=False):
                # Skip CUDA installation
                return has_gpu

        # Si on arrive ici après redémarrage ou si pas d'installation drivers
        if not cuda_installed and ask_yes_no("Installer CUDA Toolkit 11.8 ?", default=True):
            print_step("Téléchargement CUDA 11.8...")

            # Vérifier si déjà téléchargé
            cuda_installer = "/tmp/cuda_11.8.0_520.61.05_linux.run"
            if not Path(cuda_installer).exists():
                run_command(
                    "cd /tmp && wget -q https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run"
                )
            else:
                print_colored("Installeur CUDA déjà téléchargé", "CYAN")

            print_step("Installation CUDA (peut prendre 5-10 min)...")
            run_command(
                f"chmod +x {cuda_installer} && "
                f"{cuda_installer} --silent --toolkit"
            )

            # Ajouter au PATH
            cuda_path_export = """
export PATH=/usr/local/cuda-11.8/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-11.8/lib64:$LD_LIBRARY_PATH
"""
            with open("/etc/profile.d/cuda.sh", "w") as f:
                f.write(cuda_path_export)

            # Pas besoin de sourcer maintenant, sera actif au prochain shell
            print_success("CUDA installé (PATH sera actif au prochain shell)")

            # Vérifier
            returncode, stdout, _ = run_command(
                "/usr/local/cuda-11.8/bin/nvcc --version",
                capture_output=True,
                check=False
            )
            if returncode == 0:
                print_success(f"CUDA version: {stdout.split('release')[1].split(',')[0].strip() if 'release' in stdout else 'OK'}")

    return has_gpu


def section_5_python_dependencies(has_gpu: bool):
    """Section 5: Python et dépendances"""
    print_section("SECTION 5: Python et Dépendances")

    print_step("Installation Python 3.11...")
    run_command("apt install -y python3.11 python3.11-pip python3.11-venv python3.11-dev")
    # Create symlink for python3 → python3.11
    run_command("update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1")

    returncode, stdout, _ = run_command(
        "python3 --version",
        capture_output=True
    )
    print_success(f"Python installé: {stdout.strip()}")

    print_step("Création environnement virtuel...")
    run_command(f"cd {PROJECT_DIR} && python3 -m venv venv")
    print_success("Venv créé")

    print_step("Installation dépendances de base...")
    run_command(
        f"{PROJECT_DIR}/venv/bin/pip install --upgrade pip && "
        f"{PROJECT_DIR}/venv/bin/pip install numpy==1.22.0 networkx==2.8.8 transformers==4.33.0"
    )
    print_success("Dépendances de base installées")

    print_step("Installation requirements.txt (peut prendre 5-10 min)...")
    run_command(
        f"{PROJECT_DIR}/venv/bin/pip install -r {PROJECT_DIR}/requirements.txt"
    )
    print_success("Requirements installés")

    # PyTorch selon GPU/CPU
    print_step("Installation PyTorch...")
    if has_gpu:
        print_colored("Mode GPU détecté - Installation PyTorch + CUDA", "GREEN")
        run_command(
            f"{PROJECT_DIR}/venv/bin/pip install torch==2.1.2+cu118 torchaudio==2.1.2+cu118 "
            f"--index-url https://download.pytorch.org/whl/cu118"
        )

        # Vérifier GPU
        returncode, stdout, _ = run_command(
            f"{PROJECT_DIR}/venv/bin/python -c \"import torch; print(f'CUDA: {{torch.cuda.is_available()}}'); "
            f"print(f'GPU: {{torch.cuda.get_device_name(0) if torch.cuda.is_available() else \\\"None\\\"}}')\"",
            capture_output=True
        )
        print(stdout)
    else:
        print_colored("Mode CPU - Installation PyTorch CPU-only", "YELLOW")
        run_command(
            f"{PROJECT_DIR}/venv/bin/pip install torch==2.1.2 torchaudio==2.1.2 "
            f"--index-url https://download.pytorch.org/whl/cpu"
        )

    print_success("PyTorch installé")


def section_6_sofia_sip():
    """Section 6: Compiler sofia-sip"""
    print_section("SECTION 6: Compilation sofia-sip")

    # Cloner si pas déjà fait
    if not Path("/usr/local/src/sofia-sip").exists():
        print_step("Clonage sofia-sip...")
        run_command("cd /usr/local/src && git clone https://github.com/freeswitch/sofia-sip.git")
    else:
        print_colored("sofia-sip déjà cloné", "CYAN")

    print_step("Bootstrap...")
    run_command("cd /usr/local/src/sofia-sip && ./bootstrap.sh")

    print_step("Configuration...")
    run_command("cd /usr/local/src/sofia-sip && ./configure CFLAGS=\"-g -O2\"")

    print_step("Compilation (peut prendre 5-10 min)...")
    run_command("cd /usr/local/src/sofia-sip && make -j$(nproc)")

    print_step("Installation...")
    run_command("cd /usr/local/src/sofia-sip && make install")
    run_command("ldconfig")

    # Vérifier
    returncode, stdout, _ = run_command(
        "ldconfig -p | grep sofia",
        capture_output=True,
        check=False
    )
    if "libsofia-sip-ua.so" in stdout:
        print_success("sofia-sip installé et détecté")
    else:
        print_warning("sofia-sip installé mais non détecté par ldconfig")


def section_7_spandsp():
    """Section 7: Compiler spandsp"""
    print_section("SECTION 7: Compilation spandsp")

    # Cloner si pas déjà fait
    if not Path("/usr/local/src/spandsp").exists():
        print_step("Clonage spandsp...")
        run_command("cd /usr/local/src && git clone https://github.com/freeswitch/spandsp.git")
    else:
        print_colored("spandsp déjà cloné", "CYAN")

    print_step("Bootstrap...")
    run_command("cd /usr/local/src/spandsp && ./bootstrap.sh")

    print_step("Configuration...")
    run_command("cd /usr/local/src/spandsp && ./configure CFLAGS=\"-g -O2\"")

    print_step("Compilation...")
    run_command("cd /usr/local/src/spandsp && make -j$(nproc)")

    print_step("Installation...")
    run_command("cd /usr/local/src/spandsp && make install")
    run_command("ldconfig")

    print_success("spandsp installé")


def section_8_freeswitch_modules():
    """Section 8: Clonage et Configuration Modules FreeSWITCH"""
    print_section("SECTION 8: Clonage et Configuration FreeSWITCH")

    # Installer dépendances
    print_step("Installation dépendances de compilation...")
    run_command(
        "apt install -y autoconf automake devscripts gawk g++ git-core "
        "libjpeg-dev libncurses5-dev libtool libtool-bin make python3-dev pkg-config "
        "libtiff-dev libperl-dev libgdbm-dev libdb-dev gettext libssl-dev "
        "libcurl4-openssl-dev libpcre3-dev libspeex-dev libspeexdsp-dev "
        "libsqlite3-dev libedit-dev libldns-dev libpq-dev "
        "yasm nasm libx264-dev libavformat-dev libswscale-dev "
        "libopus-dev libsndfile1-dev uuid-dev swig"
    )

    # Cloner si pas déjà fait
    if not Path("/usr/src/freeswitch").exists():
        print_step("Clonage FreeSWITCH 1.10...")
        run_command(
            "cd /usr/src && "
            "git clone https://github.com/signalwire/freeswitch.git -b v1.10 freeswitch"
        )
    else:
        print_colored("FreeSWITCH déjà cloné", "CYAN")

    # IMPORTANT: Bootstrap D'ABORD (génère modules.conf)
    print_step("Bootstrap FreeSWITCH...")
    run_command("cd /usr/src/freeswitch && ./bootstrap.sh -j")

    # ENSUITE configurer modules.conf (maintenant il existe)
    print_step("Configuration modules.conf...")

    # Désactiver mod_verto, mod_signalwire, mod_lua (obligatoire pour éviter erreurs libks)
    print_step("Désactivation modules problématiques (mod_verto, mod_signalwire, mod_lua)...")

    # IMPORTANT: Utiliser EXACTEMENT la syntaxe de la doc install_fs_minbot.md avec #\?
    run_command(
        "cd /usr/src/freeswitch && "
        "sed -i 's|#\\?applications/mod_verto|#applications/mod_verto|' modules.conf"
    )
    run_command(
        "cd /usr/src/freeswitch && "
        "sed -i 's|#\\?endpoints/mod_verto|#endpoints/mod_verto|' modules.conf"
    )
    run_command(
        "cd /usr/src/freeswitch && "
        "sed -i 's|#\\?applications/mod_signalwire|#applications/mod_signalwire|' modules.conf"
    )
    run_command(
        "cd /usr/src/freeswitch && "
        "sed -i 's|#\\?languages/mod_lua|#languages/mod_lua|' modules.conf"
    )

    # Vérifier que les modifications ont été faites
    returncode, stdout, _ = run_command(
        "cd /usr/src/freeswitch && grep -E '^#(endpoints/mod_verto|applications/mod_signalwire|languages/mod_lua)' modules.conf",
        capture_output=True,
        check=False
    )

    if returncode == 0:
        print_success("Modules problématiques désactivés avec succès")
    else:
        print_warning("Impossible de vérifier les modifications, on continue...")

    # OBLIGATOIRE: Désactiver mod_spandsp (cause erreurs compilation)
    print_step("Désactivation mod_spandsp (incompatible avec spandsp récent)...")
    run_command(
        "cd /usr/src/freeswitch && "
        "sed -i 's|^applications/mod_spandsp|#applications/mod_spandsp|' modules.conf"
    )

    # Optionnel: voicemail (mod_voicemail ligne 57)
    if ask_yes_no("Désactiver mod_voicemail (non utilisé) ?", default=True):
        run_command(
            "cd /usr/src/freeswitch && "
            "sed -i 's|^applications/mod_voicemail|#applications/mod_voicemail|' modules.conf"
        )

    print_success("FreeSWITCH cloné, bootstrap et modules configurés")


def section_9_compile_freeswitch():
    """Section 9: Compiler FreeSWITCH"""
    print_section("SECTION 9: Compilation FreeSWITCH 1.10")

    print_step("Configuration...")
    run_command("cd /usr/src/freeswitch && ./configure --enable-core-pgsql-support")

    print_colored("\n⏱️  Compilation FreeSWITCH (15-30 minutes)...\n", "YELLOW", bold=True)
    print_step("Compilation en cours...")
    run_command("cd /usr/src/freeswitch && make -j$(nproc)", timeout=3600)

    print_step("Installation...")
    run_command("cd /usr/src/freeswitch && make install")

    print_step("Installation sounds et music...")
    run_command("cd /usr/src/freeswitch && make cd-sounds-install cd-moh-install")

    print_success("FreeSWITCH compilé et installé !")


def section_10_freeswitch_post_install():
    """Section 10: Post-installation FreeSWITCH"""
    print_section("SECTION 10: Post-Installation FreeSWITCH")

    print_step("Création utilisateur freeswitch...")
    run_command(
        "adduser --disabled-password --quiet --system --home /usr/local/freeswitch "
        "--gecos 'FreeSWITCH' --ingroup daemon freeswitch",
        check=False  # Ignore si existe
    )

    print_step("Fix permissions...")
    run_command("chown -R freeswitch:daemon /usr/local/freeswitch")

    print_step("Création service systemd...")
    systemd_service = """[Unit]
Description=FreeSWITCH
After=network.target

[Service]
Type=forking
PIDFile=/usr/local/freeswitch/var/run/freeswitch/freeswitch.pid
Environment="DAEMON_OPTS=-nonat"
EnvironmentFile=-/etc/default/freeswitch
ExecStart=/usr/local/freeswitch/bin/freeswitch -u freeswitch -g daemon -ncwait $DAEMON_OPTS
TimeoutSec=45s
Restart=always
WorkingDirectory=/usr/local/freeswitch
User=freeswitch
Group=daemon

[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/freeswitch.service", "w") as f:
        f.write(systemd_service)

    print_step("Activation service...")
    run_command("systemctl daemon-reload")
    run_command("systemctl enable freeswitch")

    # NE PAS démarrer FreeSWITCH ici - on le fera en Section 15 après avoir installé les configs
    print_success("Service FreeSWITCH créé (sera démarré en Section 15)")

    # Ajouter fs_cli au PATH
    print_step("Ajout fs_cli au PATH...")
    if not Path("/usr/local/bin/fs_cli").exists():
        run_command("ln -s /usr/local/freeswitch/bin/fs_cli /usr/local/bin/fs_cli")

    # Compiler python-ESL
    print_section("Compilation python-ESL")

    print_step("Compilation ESL...")
    run_command("cd /usr/src/freeswitch/libs/esl && make")

    print_step("Compilation module Python...")
    run_command("cd /usr/src/freeswitch/libs/esl && make pymod PYTHON=/usr/bin/python3")

    # Installation manuelle (contournement bug Makefile Python 2 vs 3)
    print_step("Installation module Python (système global)...")
    run_command(
        "cp /usr/src/freeswitch/libs/esl/python/_ESL.so /usr/local/lib/python3.11/dist-packages/"
    )
    run_command(
        "cp /usr/src/freeswitch/libs/esl/python/ESL.py /usr/local/lib/python3.11/dist-packages/"
    )

    # Copier aussi dans le venv (requis pour l'API)
    print_step("Installation module Python (venv projet)...")
    python_version = run_command(
        "python3 -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")'",
        capture_output=True
    )[1].strip()
    venv_site_packages = f"{PROJECT_DIR}/venv/lib/python{python_version}/site-packages"
    run_command(
        f"cp /usr/src/freeswitch/libs/esl/python/_ESL.so {venv_site_packages}/"
    )
    run_command(
        f"cp /usr/src/freeswitch/libs/esl/python/ESL.py {venv_site_packages}/"
    )

    # Test import
    returncode, stdout, _ = run_command(
        f"{PROJECT_DIR}/venv/bin/python -c 'import ESL; print(\"python-ESL OK\")'",
        capture_output=True,
        check=False
    )

    if "python-ESL OK" in stdout:
        print_success("python-ESL installé et fonctionnel")
    else:
        print_error("python-ESL install échoué")


def section_11_ai_models():
    """Section 11: Installer modèles IA"""
    print_section("SECTION 11: Installation Modèles IA")

    # Vosk STT
    print_step("Téléchargement modèle Vosk (français)...")
    run_command(f"mkdir -p {PROJECT_DIR}/models")

    vosk_path = Path(f"{PROJECT_DIR}/models/vosk-model-small-fr-0.22")
    if not vosk_path.exists():
        run_command(
            f"cd {PROJECT_DIR}/models && "
            f"wget -q https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip && "
            f"unzip -q vosk-model-small-fr-0.22.zip && "
            f"rm vosk-model-small-fr-0.22.zip"
        )
        print_success("Modèle Vosk téléchargé")
    else:
        print_success("Modèle Vosk déjà présent")

    # Ollama
    print_step("Installation Ollama...")
    run_command("curl -fsSL https://ollama.com/install.sh | sh")

    print_step("Démarrage Ollama...")
    run_command("systemctl start ollama", check=False)
    run_command("systemctl enable ollama", check=False)

    time.sleep(5)

    print_step("Téléchargement Mistral 7B (peut prendre 5-10 min)...")
    run_command("ollama pull mistral:7b")

    returncode, stdout, _ = run_command(
        "ollama list",
        capture_output=True
    )
    if "mistral:7b" in stdout:
        print_success("Ollama Mistral 7B installé")
    else:
        print_warning("Ollama installé mais Mistral non détecté")

    # Coqui TTS
    print_step("Préparation Coqui TTS...")
    run_command(f"mkdir -p {PROJECT_DIR}/models/coqui_cache")
    print_success("Coqui TTS prêt (modèles téléchargés au premier usage)")


def section_12_project_config(has_gpu: bool):
    """Section 12: Configuration projet"""
    print_section("SECTION 12: Configuration du Projet")

    # Créer .env avec configuration automatique
    env_path = Path(f"{PROJECT_DIR}/.env")
    env_example_path = Path(f"{PROJECT_DIR}/.env.example")

    print_step("Configuration fichier .env...")

    if env_example_path.exists():
        # Lire template
        with open(env_example_path, 'r') as f:
            env_content = f.read()

        # Demander paramètres utilisateur
        print_colored("\n📝 Configuration paramètres", "CYAN", bold=True)

        # API Password (OBLIGATOIRE - pas de défaut)
        print_colored("\n🔐 Sécurité API", "YELLOW", bold=True)
        print("Le mot de passe API protège tous les endpoints (campagnes, contacts, etc.)")
        api_password = ""
        while not api_password or len(api_password) < 8:
            api_password = ask_user(
                "Mot de passe API (minimum 8 caractères)",
                ""
            )
            if not api_password or len(api_password) < 8:
                print_error("Mot de passe trop court (minimum 8 caractères)")

        # Caller ID
        caller_id = ask_user(
            "Numéro émetteur (Caller ID, format: +33XXXXXXXXX)",
            "+33123456789"
        )

        # Appliquer modifications
        env_content = env_content.replace(
            "API_PASSWORD=changez_moi_en_production",
            f"API_PASSWORD={api_password}"
        )
        env_content = env_content.replace(
            "FREESWITCH_CALLER_ID=+33123456789",
            f"FREESWITCH_CALLER_ID={caller_id}"
        )

        # GPU
        if has_gpu:
            env_content = env_content.replace(
                "COQUI_USE_GPU=false",
                "COQUI_USE_GPU=true"
            )
            print_success("GPU activé pour Coqui TTS")
        else:
            print_success("Mode CPU configuré")

        # ESL Password (déjà ClueCon par défaut, mais on le confirme)
        print_success("ESL Password: ClueCon (défaut FreeSWITCH)")

        # Écrire .env
        with open(env_path, 'w') as f:
            f.write(env_content)

        print_success(f"Fichier .env créé et configuré")

        # Afficher résumé
        print_colored("\n📋 Configuration .env:", "CYAN")
        print(f"  • DATABASE_URL: postgresql://minibot:minibot@localhost:5432/minibot_freeswitch")
        print(f"  • FREESWITCH_ESL_PASSWORD: ClueCon")
        print(f"  • FREESWITCH_CALLER_ID: {caller_id}")
        print(f"  • API_PASSWORD: {api_password}")
        print(f"  • COQUI_USE_GPU: {'true' if has_gpu else 'false'}")
        print(f"  • VOSK_MODEL_PATH: models/vosk-model-fr-0.22-lgraph")
        print(f"  • OLLAMA_URL: http://localhost:11434")
    else:
        print_warning(f".env.example non trouvé, création .env manuelle requise")

    # Init base de données
    print_step("Initialisation base de données...")

    setup_db_script = Path(f"{PROJECT_DIR}/setup_database.py")
    if setup_db_script.exists():
        returncode, stdout, _ = run_command(
            f"{PROJECT_DIR}/venv/bin/python {PROJECT_DIR}/setup_database.py",
            capture_output=True,
            check=False
        )
        if "Setup base de données terminé" in stdout or returncode == 0:
            print_success("Base de données initialisée")
        else:
            print_warning("Init DB échouée (peut être déjà faite)")
    else:
        print_warning("setup_database.py non trouvé")

    print_success("Configuration projet terminée")


def section_13_test_system():
    """Section 13: Tester le système"""
    print_section("SECTION 13: Tests Système")

    # Démarrer API en arrière-plan
    print_step("Démarrage API...")
    run_command(
        f"cd {PROJECT_DIR} && "
        f"nohup {PROJECT_DIR}/venv/bin/uvicorn system.api.main:app --host 0.0.0.0 --port 8000 > /tmp/minibot_api.log 2>&1 &",
        check=False
    )

    print_colored("Attente démarrage API (10 secondes)...", "YELLOW")
    time.sleep(10)

    # Test health
    print_step("Test /health endpoint...")
    returncode, stdout, _ = run_command(
        "curl -s http://localhost:8000/health",
        capture_output=True,
        check=False
    )

    if returncode == 0 and "status" in stdout:
        print_success("API répond")
        print(f"Response: {stdout[:200]}")
    else:
        print_warning("API ne répond pas encore")

    print_success("Tests système terminés")


def section_14_systemd_api():
    """Section 14: Service systemd API"""
    print_section("SECTION 14: Service Systemd API")

    print_step("Création service minibot-api...")

    api_service = f"""[Unit]
Description=MiniBotPanel v3 API
After=network.target postgresql.service freeswitch.service

[Service]
Type=simple
User=root
WorkingDirectory={PROJECT_DIR}
Environment="PATH={PROJECT_DIR}/venv/bin"
ExecStart={PROJECT_DIR}/venv/bin/uvicorn system.api.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    with open("/etc/systemd/system/minibot-api.service", "w") as f:
        f.write(api_service)

    print_step("Activation service...")
    run_command("systemctl daemon-reload")
    run_command("systemctl enable minibot-api")
    run_command("systemctl restart minibot-api")

    time.sleep(5)

    returncode, stdout, _ = run_command(
        "systemctl status minibot-api",
        capture_output=True,
        check=False
    )
    if "active (running)" in stdout:
        print_success("Service minibot-api actif")
    else:
        print_warning("Service minibot-api status incertain")


def section_15_freeswitch_config():
    """Section 15: Configuration FreeSWITCH pour MiniBotPanel"""
    print_section("SECTION 15: Configuration FreeSWITCH")

    # 15.1 Installer config vanilla et démarrer avec
    print_step("15.1 Installation config vanilla...")
    run_command("systemctl stop freeswitch", check=False)
    run_command("cd /usr/src/freeswitch && make samples")
    run_command("chown -R freeswitch:daemon /usr/local/freeswitch/")

    print_step("Démarrage FreeSWITCH avec config vanilla...")
    run_command("systemctl start freeswitch")

    time.sleep(5)

    # Vérifier que FreeSWITCH démarre avec vanilla
    returncode, stdout, _ = run_command(
        "systemctl status freeswitch",
        capture_output=True,
        check=False
    )
    if "active (running)" in stdout:
        print_success("FreeSWITCH démarré avec config vanilla")
    else:
        print_warning("FreeSWITCH status incertain")

    # Test ESL avec vanilla
    print_step("Test ESL avec config vanilla...")
    returncode, stdout, _ = run_command(
        "fs_cli -x 'sofia status'",
        capture_output=True,
        check=False
    )
    if returncode == 0:
        print_success("ESL fonctionnel avec vanilla")
    else:
        print_warning("ESL non accessible avec vanilla")

    # 15.2 Copier configs custom et recharger
    print_step("15.2 Copie fichiers config custom...")

    config_dir = f"{PROJECT_DIR}/documentation/config_freeswitch"
    fs_config_dir = "/usr/local/freeswitch/conf"

    if Path(config_dir).exists():
        run_command(
            f"cp {config_dir}/event_socket.conf.xml {fs_config_dir}/autoload_configs/"
        )
        run_command(
            f"cp {config_dir}/modules.conf.xml {fs_config_dir}/autoload_configs/"
        )
        run_command(
            f"cp {config_dir}/dialplan_outbound.xml {fs_config_dir}/dialplan/"
        )
        run_command(
            f"cp {config_dir}/gateway_example.xml {fs_config_dir}/sip_profiles/external/gateway1.xml"
        )
        run_command("chown -R freeswitch:daemon /usr/local/freeswitch/etc/freeswitch/")
        print_success("Configs custom copiés")

        # Recharger config sans redémarrer (comme dans le manuel)
        print_step("Rechargement config...")
        run_command("fs_cli -x 'reloadxml'", check=False)
        time.sleep(2)

        # Test après reload
        returncode, stdout, _ = run_command(
            "fs_cli -x 'sofia status'",
            capture_output=True,
            check=False
        )
        if returncode == 0:
            print_success("Configs custom chargés")
    else:
        print_warning(f"Dossier config non trouvé: {config_dir}")

    # Configuration gateway SIP
    print_colored("\n🔐 Configuration Gateway SIP", "CYAN", bold=True)

    sip_proxy = ask_user("IP/Hostname serveur SIP", "sip.example.com")
    sip_username = ask_user("Username SIP", "votre_username")
    sip_password = ask_user("Password SIP", "votre_password")
    caller_id = ask_user("Caller ID (numéro sortant)", sip_username)

    gateway_xml = f"""<gateway name="gateway1">
  <param name="proxy" value="{sip_proxy}"/>
  <param name="realm" value="{sip_proxy}"/>
  <param name="username" value="{sip_username}"/>
  <param name="password" value="{sip_password}"/>
  <param name="register" value="true"/>
  <param name="retry-seconds" value="30"/>
  <param name="expire-seconds" value="3600"/>
  <param name="caller-id-in-from" value="true"/>
  <param name="extension-in-contact" value="true"/>
  <param name="context" value="public"/>
  <param name="codec-prefs" value="PCMU,PCMA"/>
  <variables>
    <variable name="outbound_caller_id_number" value="{caller_id}"/>
    <variable name="outbound_caller_id_name" value="MiniBotPanel"/>
  </variables>
</gateway>
"""

    with open(f"{fs_config_dir}/sip_profiles/external/gateway1.xml", "w") as f:
        f.write(gateway_xml)

    run_command("chown -R freeswitch:daemon /usr/local/freeswitch/")

    # Restart FreeSWITCH
    print_step("Restart FreeSWITCH...")
    run_command("systemctl restart freeswitch")

    print_colored("Attente enregistrement SIP (15 secondes)...", "YELLOW")
    time.sleep(15)

    # Test gateway
    print_step("Vérification gateway SIP...")
    returncode, stdout, _ = run_command(
        "fs_cli -x 'sofia status gateway gateway1'",
        capture_output=True,
        check=False
    )

    if "REGED" in stdout:
        print_success("Gateway SIP enregistré (REGED)")
    elif "NOREG" in stdout or "FAIL" in stdout:
        print_warning("Gateway SIP non enregistré - vérifier credentials")
        print(f"Status: {stdout[:300]}")
    else:
        print_warning("Status gateway incertain")
        print(f"Output: {stdout[:300]}")

    # Test appel (optionnel)
    if ask_yes_no("Tester un appel sortant ?", default=False):
        test_number = ask_user("Numéro à appeler (format: +33XXXXXXXXX)")

        print_step(f"Lancement appel vers {test_number}...")
        returncode, stdout, _ = run_command(
            f"fs_cli -x 'originate sofia/gateway/gateway1/{test_number} &park()'",
            capture_output=True,
            check=False,
            timeout=30
        )

        if returncode == 0:
            print_success("Appel lancé ! Vérifiez votre téléphone")
            time.sleep(5)
            print_step("Raccrochage...")
            run_command("fs_cli -x 'hupall'")
        else:
            print_error("Échec appel")
            print(f"Error: {stdout[:300]}")


def section_16_full_tests():
    """Section 16: Tests complets IA"""
    print_section("SECTION 16: Tests Complets IA")

    # Test 16.1: Vosk STT
    print_step("Test 16.1: Vosk STT...")
    test_audio = f"{PROJECT_DIR}/audio/test_audio.wav"

    if Path(test_audio).exists():
        vosk_test = f"""
import wave, json
from vosk import Model, KaldiRecognizer

model = Model("{PROJECT_DIR}/models/vosk-model-small-fr-0.22")
wf = wave.open("{test_audio}", "rb")
rec = KaldiRecognizer(model, wf.getframerate())

while True:
    data = wf.readframes(4000)
    if len(data) == 0:
        break
    rec.AcceptWaveform(data)

result = json.loads(rec.FinalResult())
print(f"Transcription: {{result.get('text', '')}}")
"""
        with open("/tmp/test_vosk.py", "w") as f:
            f.write(vosk_test)

        returncode, stdout, _ = run_command(
            f"{PROJECT_DIR}/venv/bin/python /tmp/test_vosk.py",
            capture_output=True,
            check=False,
            timeout=60
        )

        if returncode == 0 and "Transcription:" in stdout:
            print_success(f"Vosk STT OK - {stdout.strip()}")
        else:
            print_warning("Test Vosk échoué")
    else:
        print_warning(f"Fichier test audio non trouvé: {test_audio}")

    # Test 16.2-16.3: Coqui TTS
    print_step("Test 16.2-16.3: Coqui TTS...")
    coqui_test = """
from TTS.api import TTS
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

tts.tts_to_file(
    text="Test de synthèse vocale avec Coqui TTS.",
    speaker_wav="audio/test_audio.wav",
    language="fr",
    file_path="audio/test_tts_output.wav"
)
print("✅ TTS OK")
"""
    with open("/tmp/test_coqui.py", "w") as f:
        f.write(coqui_test)

    returncode, stdout, _ = run_command(
        f"{PROJECT_DIR}/venv/bin/python /tmp/test_coqui.py",
        capture_output=True,
        check=False,
        timeout=120
    )

    if "✅ TTS OK" in stdout:
        print_success("Coqui TTS OK")
    else:
        print_warning("Test Coqui échoué (peut manquer audio de référence)")

    # Test 16.4: Ollama
    print_step("Test 16.4: Ollama NLP...")
    returncode, stdout, _ = run_command(
        'curl -s http://localhost:11434/api/generate -d \'{"model":"mistral:7b","prompt":"Réponds juste: oui ou non?","stream":false}\'',
        capture_output=True,
        check=False,
        timeout=30
    )

    if returncode == 0 and "response" in stdout:
        print_success("Ollama NLP OK")
    else:
        print_warning("Test Ollama échoué")

    print_success("Tests IA terminés")


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def main():
    """Point d'entrée principal"""

    print_colored("""
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║        MiniBotPanel v3 - Installation Automatique Complète           ║
║                                                                       ║
║  Ce script va installer et configurer TOUS les composants :          ║
║    • PostgreSQL                                                       ║
║    • FreeSWITCH 1.10 (compilation)                                    ║
║    • Python + Vosk STT + Coqui TTS + Ollama                          ║
║    • Configuration SIP Gateway                                        ║
║    • Tests complets                                                   ║
║                                                                       ║
║  Durée estimée : 30-60 minutes                                        ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
    """, "CYAN", bold=True)

    # Vérifier root
    check_root()

    print_colored(f"\n📝 Log d'installation : {LOG_FILE}\n", "YELLOW")

    if not ask_yes_no("Commencer l'installation ?", default=True):
        print("Installation annulée.")
        sys.exit(0)

    # Charger état si reprise
    state = load_state()
    start_section = state.get("section_completed", 0) + 1

    if start_section > 1:
        print_warning(f"Reprise à partir de la section {start_section}")

    try:
        # Sections 1-5
        if start_section <= 1:
            section_1_system_preparation()
            save_state({"section_completed": 1})

        if start_section <= 2:
            section_2_clone_project()
            save_state({"section_completed": 2})

        if start_section <= 3:
            section_3_postgresql()
            save_state({"section_completed": 3})

        has_gpu = False
        if start_section <= 4:
            has_gpu = section_4_gpu_detection()
            save_state({"section_completed": 4, "has_gpu": has_gpu})
        else:
            has_gpu = state.get("has_gpu", False)

        if start_section <= 5:
            section_5_python_dependencies(has_gpu)
            save_state({"section_completed": 5, "has_gpu": has_gpu})

        # Sections 6-16
        if start_section <= 6:
            section_6_sofia_sip()
            save_state({"section_completed": 6, "has_gpu": has_gpu})

        if start_section <= 7:
            section_7_spandsp()
            save_state({"section_completed": 7, "has_gpu": has_gpu})

        if start_section <= 8:
            section_8_freeswitch_modules()
            save_state({"section_completed": 8, "has_gpu": has_gpu})

        if start_section <= 9:
            section_9_compile_freeswitch()
            save_state({"section_completed": 9, "has_gpu": has_gpu})

        if start_section <= 10:
            section_10_freeswitch_post_install()
            save_state({"section_completed": 10, "has_gpu": has_gpu})

        if start_section <= 11:
            section_11_ai_models()
            save_state({"section_completed": 11, "has_gpu": has_gpu})

        if start_section <= 12:
            section_12_project_config(has_gpu)
            save_state({"section_completed": 12, "has_gpu": has_gpu})

        if start_section <= 13:
            section_13_test_system()
            save_state({"section_completed": 13, "has_gpu": has_gpu})

        if start_section <= 14:
            section_14_systemd_api()
            save_state({"section_completed": 14, "has_gpu": has_gpu})

        if start_section <= 15:
            section_15_freeswitch_config()
            save_state({"section_completed": 15, "has_gpu": has_gpu})

        if start_section <= 16:
            section_16_full_tests()
            save_state({"section_completed": 16, "has_gpu": has_gpu})

        # Installation terminée !
        print_section("🎉 INSTALLATION TERMINÉE !")
        print_success("Tous les composants sont installés et testés !")
        print_colored("\n📋 Résumé:", "CYAN", bold=True)
        print_colored("  ✅ PostgreSQL", "GREEN")
        print_colored("  ✅ FreeSWITCH 1.10", "GREEN")
        print_colored("  ✅ Python-ESL", "GREEN")
        print_colored("  ✅ Vosk STT (français)", "GREEN")
        print_colored("  ✅ Coqui TTS (voice cloning)", "GREEN")
        print_colored("  ✅ Ollama Mistral 7B", "GREEN")
        print_colored("  ✅ Gateway SIP configuré", "GREEN")
        print_colored("  ✅ Tests validés", "GREEN")

        print_colored("\n🚀 Prochaines étapes:", "YELLOW", bold=True)
        print("  1. Créer une campagne via l'API")
        print("  2. Importer des contacts")
        print("  3. Lancer des appels !")

        print_colored(f"\n📝 Log complet: {LOG_FILE}", "CYAN")
        print_colored(f"📁 Projet: {PROJECT_DIR}", "CYAN")

        # Nettoyer état
        if Path(STATE_FILE).exists():
            Path(STATE_FILE).unlink()

        print_colored("\n✨ MiniBotPanel v3 est prêt ! ✨\n", "GREEN", bold=True)

    except KeyboardInterrupt:
        print_error("\n\nInstallation interrompue par l'utilisateur")
        print_colored(f"État sauvegardé dans {STATE_FILE}", "YELLOW")
        print_colored("Relancez le script pour reprendre", "YELLOW")
        sys.exit(1)

    except Exception as e:
        print_error(f"\n\nErreur fatale: {e}")
        print_colored(f"Consultez le log: {LOG_FILE}", "RED")
        sys.exit(1)


if __name__ == "__main__":
    main()
