#!/usr/bin/env python3
"""
Create Scenario - MiniBotPanel v3 (SIMPLIFIED)

Script interactif simplifié pour créer des scénarios conversationnels.

Workflow:
1. Infos de base (nom, description, objectif)
2. Configuration voix (auto-détection depuis audio/)
3. Configuration questions (nombre + déterminants)
4. Thème objections
5. Configuration barge-in
6. Enregistrement + transcription audio pour chaque étape
7. Génération structure finale

Usage:
    python3 create_scenario.py
"""

import json
import sys
import re
import wave
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import objections database (NOUVEAU SYSTÈME MODULAIRE)
try:
    from system.objections_db import load_objections, list_available_themes
    OBJECTIONS_SYSTEM_AVAILABLE = True
except ImportError:
    import warnings
    warnings.warn("objections_db not found", UserWarning)
    OBJECTIONS_SYSTEM_AVAILABLE = False
    def load_objections(theme_file):
        return []
    def list_available_themes():
        return []

# Import config pour chemins FreeSWITCH
try:
    from system.config import get_freeswitch_audio_path, FREESWITCH_SOUNDS_DIR
    FREESWITCH_CONFIG_AVAILABLE = True
except ImportError:
    FREESWITCH_CONFIG_AVAILABLE = False
    def get_freeswitch_audio_path(voice, audio_type, filename):
        return Path(f"/usr/share/freeswitch/sounds/minibot/{voice}/{audio_type}/{filename}")
    FREESWITCH_SOUNDS_DIR = Path("/usr/share/freeswitch/sounds/minibot")

# Import Vosk pour transcription automatique
try:
    from vosk import Model, KaldiRecognizer
    from system.config import VOSK_MODEL_PATH
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    print_warning = lambda x: print(f"⚠️  {x}")

# Couleurs terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(title: str, char: str = "═"):
    """Affiche un header stylisé"""
    width = 70
    print(f"\n{Colors.CYAN}{char * width}")
    print(f"{title:^{width}}")
    print(f"{char * width}{Colors.END}\n")


def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")


def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Pose une question oui/non"""
    suffix = "[O/n]" if default else "[o/N]"
    while True:
        response = input(f"{question} {suffix}: ").strip().lower()
        if not response:
            return default
        if response in ['o', 'oui', 'y', 'yes']:
            return True
        if response in ['n', 'non', 'no']:
            return False
        print_error("Réponse invalide. Utilisez O (oui) ou N (non)")


def ask_text(question: str, default: str = "", required: bool = True) -> str:
    """Pose une question texte"""
    while True:
        if default:
            response = input(f"{question} [{default}]: ").strip()
            result = response if response else default
        else:
            response = input(f"{question}: ").strip()
            result = response

        if result or not required:
            return result
        print_error("Ce champ est requis")


def ask_int(question: str, default: int = None, min_val: int = None, max_val: int = None) -> int:
    """Pose une question numérique"""
    while True:
        if default is not None:
            response = input(f"{question} [{default}]: ").strip()
            if not response:
                return default
        else:
            response = input(f"{question}: ").strip()

        try:
            value = int(response)
            if min_val is not None and value < min_val:
                print_error(f"Valeur minimale: {min_val}")
                continue
            if max_val is not None and value > max_val:
                print_error(f"Valeur maximale: {max_val}")
                continue
            return value
        except ValueError:
            print_error("Entrez un nombre valide")


def ask_choice(question: str, choices: List[str], default: int = 1) -> int:
    """Pose une question à choix multiples"""
    print(f"\n{question}")
    for i, choice in enumerate(choices, 1):
        prefix = "→" if i == default else " "
        print(f"  {prefix} {i}) {choice}")

    while True:
        response = input(f"\nChoix [{default}]: ").strip()
        if not response:
            return default
        try:
            choice = int(response)
            if 1 <= choice <= len(choices):
                return choice
        except ValueError:
            pass
        print_error(f"Choix invalide. Entrez un nombre entre 1 et {len(choices)}")


class ScenarioBuilderV3:
    """Constructeur de scénario simplifié - MiniBotPanel v3"""

    def __init__(self):
        self.scenario = {
            "metadata": {
                "name": "",
                "description": "",
                "version": "3.0",
                "theme_file": "",  # Nouveau système: theme_file au lieu de thematique
                "voice": "",
                "barge_in_default": True
            },
            "variables": {
                "first_name": "{{first_name}}",
                "company_name": "",
                "agent_name": ""
            },
            "steps": {},
            "flow_summary": {}
        }
        self.num_questions = 3
        self.determinant_questions = []  # Indices des questions déterminantes (ex: [1, 3])
        self.voice_name = ""
        self.theme = ""
        self.max_turns = 2  # Nombre max de tours pour objections/questions
        self.audio_files = {}  # {step_name: {"audio_path": "...", "transcription": "..."}}
        self.vosk_model = None  # Modèle Vosk pour transcription

    def run(self):
        """Lance le processus interactif complet"""
        print(f"{Colors.BOLD}")
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║       🤖 MiniBotPanel v3 - Scenario Creator (Simplified)        ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(Colors.END)

        print_info("Création de scénario: HELLO → Q1...Qn → IS_LEADS → CONFIRM → BYE\n")

        # 1. Informations de base
        self._ask_basic_info()

        # 2. Configuration voix
        self._ask_voice_config()

        # 3. Configuration questions
        self._ask_questions_config()

        # 4. Thème pour objections
        self._ask_theme_for_objections()

        # 5. Configuration barge-in
        self._ask_barge_in_config()

        # 6. Configuration max_autonomous_turns
        self._ask_max_turns_config()

        # 7. Enregistrement audio pour chaque étape
        print_header("📹 ENREGISTREMENT AUDIO DES ÉTAPES")
        print_warning("Pour chaque étape, vous devrez enregistrer un fichier audio.")
        print_info("Le système utilisera Vosk pour transcrire l'audio automatiquement.\n")

        self._record_all_audio_files()

        # 7. Construction de la structure
        self._build_all_steps()

        # 8. Sauvegarder (pas de qualification_rules, le flow décide)
        self._save_scenario()

        print_success(f"\n🎉 Scénario créé avec succès!")
        print_info(f"   Fichier: scenarios/{self.scenario['metadata']['name']}.json")

    def _ask_basic_info(self):
        """Demande les informations de base"""
        print_header("📋 INFORMATIONS DE BASE")

        # Nom du scénario
        self.scenario["metadata"]["name"] = ask_text(
            "Nom du scénario (ex: rdv_energie, demo_saas)",
            required=True
        )

        # Description
        self.scenario["metadata"]["description"] = ask_text(
            "Description courte",
            default="Scénario de prospection téléphonique",
            required=False
        )

        # Objectif
        objective = ask_text(
            "Objectif de la campagne (ex: prise de RDV, qualification, vente)",
            default="Prise de rendez-vous",
            required=False
        )
        self.scenario["metadata"]["objective"] = objective

        # Variables
        self.scenario["variables"]["company_name"] = ask_text(
            "Nom de l'entreprise",
            default="Entreprise Example"
        )

        self.scenario["variables"]["agent_name"] = ask_text(
            "Nom de l'agent virtuel",
            default="Julie"
        )

        print_success("Informations de base enregistrées")

    def _ask_voice_config(self):
        """Détection automatique des voix disponibles depuis audio/"""
        print_header("🎙️ CONFIGURATION VOIX")

        # Chercher dossiers dans audio/
        audio_dir = Path("audio")
        if not audio_dir.exists():
            print_warning("Dossier audio/ introuvable. Création...")
            audio_dir.mkdir(parents=True, exist_ok=True)
            print_error("Veuillez créer un dossier audio/{voice_name}/ avec les fichiers audio")
            sys.exit(1)

        # Lister voix disponibles
        voices = [d.name for d in audio_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

        if not voices:
            print_error("Aucune voix trouvée dans audio/")
            print_info("Créez un dossier audio/{voice_name}/ avec les sous-dossiers base/ et objections/")
            sys.exit(1)

        print_info(f"Voix disponibles: {', '.join(voices)}")

        if len(voices) == 1:
            self.voice_name = voices[0]
            print_success(f"Voix sélectionnée automatiquement: {self.voice_name}")
        else:
            choice = ask_choice(
                "Quelle voix utiliser ?",
                voices,
                default=1
            )
            self.voice_name = voices[choice - 1]
            print_success(f"Voix sélectionnée: {self.voice_name}")

        self.scenario["metadata"]["voice"] = self.voice_name

    def _ask_questions_config(self):
        """Configuration du nombre de questions et déterminants"""
        print_header("❓ CONFIGURATION QUESTIONS")

        # Nombre de questions
        self.num_questions = ask_int(
            "Combien de questions voulez-vous poser au prospect ?",
            default=3,
            min_val=1,
            max_val=10
        )

        print_success(f"Le scénario aura {self.num_questions} questions (Q1 à Q{self.num_questions})")
        print_info("\n💡 Vous configurerez si chaque question est déterminante après l'enregistrement audio")

    def _ask_theme_for_objections(self):
        """Sélection du thème pour la base d'objections (NOUVEAU SYSTÈME MODULAIRE)"""
        print_header("🎯 THÈME POUR OBJECTIONS")

        if not OBJECTIONS_SYSTEM_AVAILABLE:
            print_warning("Système d'objections non disponible - utilisation thème par défaut")
            self.theme = "objections_general"
            self.scenario["metadata"]["theme_file"] = self.theme
            return

        # Lister thématiques disponibles depuis system/objections_db/
        available_themes = list_available_themes()

        if not available_themes:
            print_warning("Aucune thématique trouvée - utilisation 'objections_general'")
            self.theme = "objections_general"
            self.scenario["metadata"]["theme_file"] = self.theme
            return

        print_info("Thématiques disponibles (détectées automatiquement):")
        for i, theme in enumerate(available_themes, 1):
            # Afficher nom simplifié (sans "objections_")
            display_name = theme.replace("objections_", "")
            print(f"  {i}) {display_name} [{theme}]")

        # Chercher index de general pour défaut
        default_idx = 1
        if "objections_general" in available_themes:
            default_idx = available_themes.index("objections_general") + 1

        choice = ask_choice(
            "Quel thème pour la base d'objections ?",
            [t.replace("objections_", "") for t in available_themes],
            default=default_idx
        )

        # Récupérer nom complet du fichier (avec "objections_")
        self.theme = available_themes[choice - 1]
        self.scenario["metadata"]["theme_file"] = self.theme

        print_success(f"Thème sélectionné: {self.theme}")

        # Vérifier nombre d'objections disponibles
        try:
            objections = load_objections(self.theme)
            print_info(f"   {len(objections)} objections disponibles (general + thématique)")
        except Exception as e:
            print_warning(f"   Impossible de charger les objections: {e}")

    def _ask_barge_in_config(self):
        """Configuration barge-in (une seule question globale)"""
        print_header("🔇 CONFIGURATION BARGE-IN")

        print_info("Le barge-in permet au client d'interrompre le robot pendant qu'il parle.")

        barge_in_enabled = ask_yes_no(
            "Activer le barge-in pour toutes les étapes ?",
            default=True
        )

        self.scenario["metadata"]["barge_in_default"] = barge_in_enabled

        if barge_in_enabled:
            print_success("Barge-in activé globalement")
        else:
            print_warning("Barge-in désactivé (le client devra attendre que le robot finisse)")

    def _ask_max_turns_config(self):
        """Configuration max_autonomous_turns (gestion objections/questions)"""
        print_header("🔄 CONFIGURATION MAX TURNS (Objections)")

        print_info("Le 'max_autonomous_turns' définit combien de fois le robot peut gérer")
        print_info("des objections/questions avant de passer à l'étape suivante.\n")

        print(f"{Colors.YELLOW}Exemples:{Colors.END}")
        print(f"  • {Colors.BOLD}0{Colors.END} = Pas de gestion d'objections (robot ignore et continue)")
        print(f"  • {Colors.BOLD}1{Colors.END} = Répond 1 fois aux objections puis continue")
        print(f"  • {Colors.BOLD}2{Colors.END} = Répond jusqu'à 2 fois (recommandé)")
        print(f"  • {Colors.BOLD}3+{Colors.END} = Répond plusieurs fois (attention aux boucles)\n")

        while True:
            try:
                max_turns_input = input(f"Nombre de max_autonomous_turns [2]: ").strip()

                if not max_turns_input:
                    max_turns = 2  # Défaut
                else:
                    max_turns = int(max_turns_input)

                if max_turns < 0:
                    print_error("Le nombre doit être >= 0")
                    continue

                if max_turns > 5:
                    print_warning(f"Valeur élevée ({max_turns}) - risque de boucles longues")
                    if not ask_yes_no("Confirmer cette valeur ?", default=False):
                        continue

                self.max_turns = max_turns
                break

            except ValueError:
                print_error("Entrez un nombre valide")

        # Messages d'information
        if self.max_turns == 0:
            print_warning("⚠️  max_turns = 0 : Le robot n'utilisera PAS le système d'objections")
            print_info("    → Il suivra uniquement l'intent_mapping de manière linéaire")
            print_info("    → Pas besoin de fichiers audio objections")
        elif self.max_turns == 1:
            print_success(f"✅ max_turns = {self.max_turns} : Gestion d'objections légère")
        else:
            print_success(f"✅ max_turns = {self.max_turns} : Gestion d'objections complète")

        print_info(f"    → Le robot répondra jusqu'à {self.max_turns} fois aux objections/questions par étape")

    def _transcribe_audio_with_vosk(self, audio_path: Path) -> Optional[str]:
        """
        Transcrit un fichier audio avec Vosk.

        Args:
            audio_path: Chemin vers le fichier audio WAV

        Returns:
            Transcription du fichier ou None si erreur
        """
        if not VOSK_AVAILABLE:
            return None

        try:
            # Charger le modèle Vosk une seule fois
            if self.vosk_model is None:
                print_info(f"  📥 Chargement modèle Vosk...")
                self.vosk_model = Model(VOSK_MODEL_PATH)

            # Ouvrir le fichier audio
            wf = wave.open(str(audio_path), "rb")

            # Vérifier le format
            if wf.getnchannels() != 1:
                print_warning(f"  ⚠️  Audio doit être mono, transcription peut être imprécise")

            # Créer le recognizer avec le sample rate du fichier
            rec = KaldiRecognizer(self.vosk_model, wf.getframerate())
            rec.SetWords(True)

            # Transcrire
            transcription_parts = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if result.get("text"):
                        transcription_parts.append(result["text"])

            # Résultat final
            final_result = json.loads(rec.FinalResult())
            if final_result.get("text"):
                transcription_parts.append(final_result["text"])

            wf.close()

            transcription = " ".join(transcription_parts).strip()
            return transcription if transcription else None

        except Exception as e:
            print_warning(f"  ⚠️  Erreur transcription Vosk: {e}")
            return None

    def _record_all_audio_files(self):
        """Enregistre et transcrit les fichiers audio pour toutes les étapes"""
        print_header("🎤 ENREGISTREMENT AUDIO")

        # Liste des étapes de base nécessaires
        base_steps = [
            ("hello", "Introduction initiale"),
            ("retry_hello", "Retry après refus initial"),
            ("retry_silence", "Retry après silence"),
        ]

        # Ajouter questions dynamiques
        for i in range(1, self.num_questions + 1):
            base_steps.append((f"q{i}", f"Question {i}"))

        # Ajouter étapes finales
        base_steps.extend([
            ("is_leads", "Proposition finale / qualification"),
            ("retry_is_leads", "Retry si hésitation sur proposition"),
            ("confirm_time", "Confirmation horaire RDV"),
            ("bye", "Clôture succès"),
            ("bye_failed", "Clôture échec"),
            ("not_understood", "Fallback incompréhension")
        ])

        print_info(f"Vous devez enregistrer {len(base_steps)} fichiers audio.\n")

        for step_name, step_desc in base_steps:
            print(f"\n{Colors.BOLD}Étape: {step_name}{Colors.END} - {step_desc}")

            # Utiliser chemin FreeSWITCH automatiquement
            freeswitch_audio_path = get_freeswitch_audio_path(
                self.voice_name,
                "base",
                f"{step_name}.wav"
            )

            # Chemin fichier source (pour transcription Vosk)
            source_audio_path = Path(f"audio/{self.voice_name}/base/{step_name}.wav")

            # Afficher chemin utilisé
            print_info(f"  Chemin FreeSWITCH: {freeswitch_audio_path}")

            # Vérifier existence fichier source pour transcription
            if not source_audio_path.exists():
                print_warning(f"  ⚠️  Fichier source non trouvé")
                print_info(f"  📝 Placez le fichier source dans: {source_audio_path}")
                print_info(f"  📝 Puis lancez: python3 setup_audio.py")
                transcription = ""
            else:
                # Transcription automatique avec Vosk (sur fichier SOURCE, pas FreeSWITCH)
                print_info("  🎤 Transcription automatique avec Vosk...")
                transcription = self._transcribe_audio_with_vosk(source_audio_path)

                if transcription:
                    print_success(f"  ✅ Transcription: {transcription[:100]}{'...' if len(transcription) > 100 else ''}")

                    # Demander confirmation ou modification
                    confirm = ask_yes_no("  Transcription correcte ?", default=True)
                    if not confirm:
                        print_info("  📝 Saisie manuelle:")
                        transcription = ask_text(
                            f"  Texte de '{step_name}'",
                            default=transcription,
                            required=True
                        )
                else:
                    print_warning("  ⚠️  Transcription automatique échouée, saisie manuelle:")
                    transcription = ask_text(
                        f"  Texte de '{step_name}'",
                        required=True
                    )

            # Enregistrer avec chemin FreeSWITCH
            self.audio_files[step_name] = {
                "audio_path": str(freeswitch_audio_path),
                "transcription": transcription
            }

            print_success(f"  ✅ {step_name} enregistré")

        print_success(f"\n🎉 {len(base_steps)} fichiers audio configurés")

    def _build_all_steps(self):
        """Construit la structure complète des steps"""
        print_header("🏗️  CONSTRUCTION STRUCTURE")

        steps = {}

        # ─────────────────────────────────────────────────────────────────
        # HELLO
        # ─────────────────────────────────────────────────────────────────
        steps["hello"] = {
            "message_text": self.audio_files["hello"]["transcription"],
            "audio_file": self.audio_files["hello"]["audio_path"],
            "audio_type": "audio",
            "voice": self.voice_name,
            "barge_in": self.scenario["metadata"]["barge_in_default"],
            "timeout": 15,
            "max_autonomous_turns": self.max_turns,
            "intent_mapping": {
                # Intents de base (Ollama NLP)
                "affirm": "q1",         # Oui, d'accord, ok
                "deny": "retry_hello",  # Non, pas intéressé
                "unsure": "q1",         # Peut-être, je ne sais pas
                "silence": "retry_silence",
                # objection/question gérés automatiquement par matcher
                "*": "retry_hello"
            }
        }

        # ─────────────────────────────────────────────────────────────────
        # RETRY_HELLO
        # ─────────────────────────────────────────────────────────────────
        steps["retry_hello"] = {
            "message_text": self.audio_files["retry_hello"]["transcription"],
            "audio_file": self.audio_files["retry_hello"]["audio_path"],
            "audio_type": "audio",
            "voice": self.voice_name,
            "barge_in": self.scenario["metadata"]["barge_in_default"],
            "timeout": 15,
            "max_autonomous_turns": self.max_turns,
            "intent_mapping": {
                # Deuxième chance: si affirm → q1, sinon → bye_failed
                "affirm": "q1",
                "deny": "bye_failed",
                "unsure": "q1",
                "silence": "bye_failed",
                "*": "bye_failed"
            }
        }

        # ─────────────────────────────────────────────────────────────────
        # RETRY_SILENCE
        # ─────────────────────────────────────────────────────────────────
        steps["retry_silence"] = {
            "message_text": self.audio_files["retry_silence"]["transcription"],
            "audio_file": self.audio_files["retry_silence"]["audio_path"],
            "audio_type": "audio",
            "voice": self.voice_name,
            "barge_in": self.scenario["metadata"]["barge_in_default"],
            "timeout": 10,
            "max_autonomous_turns": self.max_turns,
            "intent_mapping": {
                "affirm": "q1",
                "deny": "bye_failed",
                "unsure": "q1",
                "silence": "end",  # 2ème silence → hangup direct
                "*": "q1"
            }
        }

        # ─────────────────────────────────────────────────────────────────
        # Q1, Q2, Q3... Qn (QUESTIONS DYNAMIQUES)
        # ─────────────────────────────────────────────────────────────────
        print_info("\n📋 Configuration des questions qualifiantes")
        print_info("Pour chaque question, indiquez si elle est DÉTERMINANTE")
        print_info("(un refus élimine le lead) ou NON-DÉTERMINANTE (refus accepté)\n")

        for i in range(1, self.num_questions + 1):
            step_name = f"q{i}"
            next_step = f"q{i+1}" if i < self.num_questions else "is_leads"

            # Demander si déterminante
            print(f"\n{'─'*60}")
            print(f"Question Q{i}: {self.audio_files[step_name]['transcription'][:60]}...")
            print("─"*60)
            is_determinant = input(f"  Cette question est-elle DÉTERMINANTE (refus = élimination) ? (oui/non) : ").lower() == "oui"

            # Générer intent_mapping selon déterminante
            if is_determinant:
                print_success("  ✅ Déterminante : Un refus → bye_failed")
                intent_mapping = {
                    "affirm": next_step,
                    "deny": "bye_failed",     # Refus = éliminé
                    "unsure": next_step,
                    "silence": "retry_silence",
                    "*": "bye_failed"
                }
            else:
                print_info("  ℹ️  Non-déterminante : Toute réponse acceptée")
                intent_mapping = {
                    "affirm": next_step,
                    "deny": next_step,        # Refus accepté
                    "unsure": next_step,
                    "silence": "retry_silence",
                    "*": next_step
                }

            steps[step_name] = {
                "message_text": self.audio_files[step_name]["transcription"],
                "audio_file": self.audio_files[step_name]["audio_path"],
                "audio_type": "audio",
                "voice": self.voice_name,
                "barge_in": self.scenario["metadata"]["barge_in_default"],
                "timeout": 15,
                "max_autonomous_turns": self.max_turns,
                "intent_mapping": intent_mapping
            }

        # ─────────────────────────────────────────────────────────────────
        # IS_LEADS
        # ─────────────────────────────────────────────────────────────────
        print(f"\n{'─'*60}")
        print(f"Étape IS_LEADS: {self.audio_files['is_leads']['transcription'][:60]}...")
        print("─"*60)
        is_leads_determinant = input(f"  Cette étape est-elle DÉTERMINANTE (refus = élimination) ? (oui/non) : ").lower() == "oui"

        if is_leads_determinant:
            print_success("  ✅ Déterminante : Un refus → retry_is_leads (puis bye_failed)")
            is_leads_mapping = {
                "affirm": "confirm_time",
                "deny": "retry_is_leads",
                "unsure": "confirm_time",
                "silence": "retry_silence",  # Silence = problème technique, pas refus
                "*": "retry_is_leads"
            }
        else:
            print_info("  ℹ️  Non-déterminante : Toute réponse → confirm_time")
            is_leads_mapping = {
                "affirm": "confirm_time",
                "deny": "confirm_time",
                "unsure": "confirm_time",
                "silence": "retry_silence",  # Silence → retry quand même
                "*": "confirm_time"
            }

        steps["is_leads"] = {
            "message_text": self.audio_files["is_leads"]["transcription"],
            "audio_file": self.audio_files["is_leads"]["audio_path"],
            "audio_type": "audio",
            "voice": self.voice_name,
            "barge_in": self.scenario["metadata"]["barge_in_default"],
            "timeout": 15,
            "max_autonomous_turns": self.max_turns,
            "intent_mapping": is_leads_mapping
        }

        # ─────────────────────────────────────────────────────────────────
        # RETRY_IS_LEADS
        # ─────────────────────────────────────────────────────────────────
        steps["retry_is_leads"] = {
            "message_text": self.audio_files["retry_is_leads"]["transcription"],
            "audio_file": self.audio_files["retry_is_leads"]["audio_path"],
            "audio_type": "audio",
            "voice": self.voice_name,
            "barge_in": self.scenario["metadata"]["barge_in_default"],
            "timeout": 15,
            "max_autonomous_turns": self.max_turns,
            "intent_mapping": {
                # Retry proposition: dernière chance
                "affirm": "confirm_time",
                "deny": "bye_failed",
                "unsure": "confirm_time",
                "silence": "retry_silence",  # Silence = problème technique, pas refus
                "*": "bye_failed"
            }
        }

        # ─────────────────────────────────────────────────────────────────
        # CONFIRM_TIME
        # ─────────────────────────────────────────────────────────────────
        print(f"\n{'─'*60}")
        print(f"Étape CONFIRM_TIME: {self.audio_files['confirm_time']['transcription'][:60]}...")
        print("─"*60)
        confirm_determinant = input(f"  Cette étape est-elle DÉTERMINANTE (refus = élimination) ? (oui/non) : ").lower() == "oui"

        if confirm_determinant:
            print_success("  ✅ Déterminante : Un refus → bye_failed")
            confirm_mapping = {
                "affirm": "bye",
                "deny": "bye_failed",
                "unsure": "bye",
                "silence": "retry_silence",  # Silence = problème technique, pas refus
                "*": "bye"
            }
        else:
            print_info("  ℹ️  Non-déterminante : Toute réponse → bye")
            confirm_mapping = {
                "affirm": "bye",
                "deny": "bye",
                "unsure": "bye",
                "silence": "retry_silence",  # Silence → retry quand même
                "*": "bye"
            }

        steps["confirm_time"] = {
            "message_text": self.audio_files["confirm_time"]["transcription"],
            "audio_file": self.audio_files["confirm_time"]["audio_path"],
            "audio_type": "audio",
            "voice": self.voice_name,
            "barge_in": self.scenario["metadata"]["barge_in_default"],
            "timeout": 15,
            "max_autonomous_turns": self.max_turns,
            "intent_mapping": confirm_mapping
        }

        # ─────────────────────────────────────────────────────────────────
        # BYE (succès)
        # ─────────────────────────────────────────────────────────────────
        steps["bye"] = {
            "message_text": self.audio_files["bye"]["transcription"],
            "audio_file": self.audio_files["bye"]["audio_path"],
            "audio_type": "audio",
            "voice": self.voice_name,
            "barge_in": False,
            "timeout": 5,
            "result": "completed",
            "intent_mapping": {
                "*": "end"
            }
        }

        # ─────────────────────────────────────────────────────────────────
        # BYE_NO_ANSWER supprimé - redirection directe vers "end" maintenant
        # ─────────────────────────────────────────────────────────────────

        # ─────────────────────────────────────────────────────────────────
        # BYE_FAILED
        # ─────────────────────────────────────────────────────────────────
        steps["bye_failed"] = {
            "message_text": self.audio_files["bye_failed"]["transcription"],
            "audio_file": self.audio_files["bye_failed"]["audio_path"],
            "audio_type": "audio",
            "voice": self.voice_name,
            "barge_in": False,
            "timeout": 5,
            "result": "failed",
            "intent_mapping": {
                "*": "end"
            }
        }

        # ─────────────────────────────────────────────────────────────────
        # NOT_UNDERSTOOD (fallback)
        # ─────────────────────────────────────────────────────────────────
        steps["not_understood"] = {
            "message_text": self.audio_files["not_understood"]["transcription"],
            "audio_file": self.audio_files["not_understood"]["audio_path"],
            "audio_type": "audio",
            "voice": self.voice_name,
            "barge_in": True,
            "timeout": 15,
            "intent_mapping": {
                "*": "bye_failed"
            }
        }

        # ─────────────────────────────────────────────────────────────────
        # END (terminal)
        # ─────────────────────────────────────────────────────────────────
        steps["end"] = {
            "message_text": "",
            "audio_type": "none",
            "voice": self.voice_name,
            "barge_in": False,
            "timeout": 0,
            "result": "ended",
            "intent_mapping": {}
        }

        self.scenario["steps"] = steps
        print_success(f"Structure créée avec {len(steps)} étapes")


    def _save_scenario(self):
        """Sauvegarde le scénario dans scenarios/"""
        print_header("💾 SAUVEGARDE")

        # Créer dossier scenarios/ si besoin
        scenarios_dir = Path("scenarios")
        scenarios_dir.mkdir(exist_ok=True)

        filename = f"{self.scenario['metadata']['name']}.json"
        filepath = scenarios_dir / filename

        # Sauvegarder
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.scenario, f, indent=2, ensure_ascii=False)

        print_success(f"Scénario sauvegardé: {filepath}")


def main():
    """Point d'entrée"""
    try:
        builder = ScenarioBuilderV3()
        builder.run()
    except KeyboardInterrupt:
        print("\n\n❌ Annulé par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print_error(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
