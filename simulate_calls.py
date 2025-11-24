#!/usr/bin/env python3
"""
Simulateur d'appels téléphoniques pour tester le scénario et le matching.

Usage:
    python3 simulate_calls.py --profile affirm_all --runs 10 -v
    python3 simulate_calls.py --profile all --runs 5
    python3 simulate_calls.py --list-profiles
"""

import json
import random
import argparse
import requests
import sys
import os
from datetime import datetime
from collections import defaultdict

# Add system path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from system.objection_matcher import ObjectionMatcher

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral:7b"

# ═══════════════════════════════════════════════════════════════════════════
# PROFILS DE TEST
# ═══════════════════════════════════════════════════════════════════════════

TEST_PROFILES = {
    "affirm_all": {
        "description": "Répond toujours oui/d'accord/ok",
        "response_type": "affirm",
        "examples": ["oui", "d'accord", "ok", "bien sûr", "parfait", "oui oui", "très bien"]
    },
    "deny_all": {
        "description": "Répond toujours non/pas intéressé",
        "response_type": "deny",
        "examples": ["non", "non merci", "pas intéressé", "ça ne m'intéresse pas", "non non"]
    },
    "silence_all": {
        "description": "Ne répond jamais (teste timeouts)",
        "response_type": "silence",
        "examples": ["", "   ", None]
    },
    "barge_in": {
        "description": "Interrompt pendant l'audio (réponses rapides)",
        "response_type": "barge_in",
        "examples": ["oui oui", "non non", "attendez", "stop", "une seconde"]
    },
    "objections": {
        "description": "Donne des objections variées",
        "response_type": "objection",
        "prompt": "Génère une objection française courte à un démarcheur téléphonique"
    },
    "questions": {
        "description": "Pose des questions (FAQ)",
        "response_type": "question",
        "prompt": "Génère une question courte qu'on pose à un démarcheur téléphonique"
    },
    "insults": {
        "description": "Réponses agressives/insultes",
        "response_type": "insult",
        "examples": ["arrêtez de m'appeler", "foutez-moi la paix", "vous me faites chier"]
    },
    "time_responses": {
        "description": "Donne des créneaux horaires",
        "response_type": "time",
        "examples": ["demain matin", "lundi", "vers 14h", "la semaine prochaine", "mercredi après-midi"]
    },
    "unsure": {
        "description": "Réponses hésitantes",
        "response_type": "unsure",
        "examples": ["euh...", "je sais pas", "peut-être", "bah...", "hum", "je ne suis pas sûr"]
    },
    "max_turns": {
        "description": "Teste les limites de tours autonomes (objections répétées)",
        "response_type": "max_turns",
        "prompt": "Génère une objection ou question pour pousser le robot à ses limites"
    },
    "random": {
        "description": "Réponses Ollama 100% aléatoires",
        "response_type": "random",
        "prompt": "Génère une réponse française courte et naturelle à un appel téléphonique commercial"
    },
    "mixed": {
        "description": "Mélange de tous les types",
        "response_type": "mixed",
        "mix_profiles": ["affirm_all", "deny_all", "objections", "questions", "unsure", "time_responses"]
    },
    "realistic": {
        "description": "Simulation réaliste d'un vrai appel",
        "response_type": "realistic",
        "prompt": "Simule une réponse naturelle française à un démarcheur téléphonique"
    },
    "chaos": {
        "description": "Mode CHAOS - Réponses 100% aléatoires à chaque étape",
        "response_type": "chaos",
        "chaos_weights": {
            "affirm_all": 20,
            "deny_all": 15,
            "silence_all": 10,
            "objections": 20,
            "questions": 10,
            "unsure": 15,
            "time_responses": 5,
            "insults": 3,
            "barge_in": 2
        }
    },
    "chaos_extreme": {
        "description": "Mode CHAOS EXTRÊME - Vraiment n'importe quoi",
        "response_type": "chaos_extreme",
        "chaos_weights": {
            "affirm_all": 10,
            "deny_all": 10,
            "silence_all": 20,
            "objections": 15,
            "questions": 10,
            "unsure": 15,
            "time_responses": 5,
            "insults": 10,
            "barge_in": 5
        }
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# GÉNÉRATEUR DE RÉPONSES
# ═══════════════════════════════════════════════════════════════════════════

def generate_with_ollama(prompt: str, max_tokens: int = 50) -> str:
    """Génère une réponse avec Ollama/Mistral."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.9
                }
            },
            timeout=30
        )
        if response.status_code == 200:
            result = response.json().get("response", "").strip()
            # Clean up - take first line only
            result = result.split('\n')[0].strip()
            # Remove quotes
            result = result.strip('"\'')
            return result
    except Exception as e:
        pass
    return ""


def weighted_random_choice(weights: dict) -> str:
    """Sélection aléatoire pondérée."""
    items = list(weights.keys())
    weights_list = [weights[k] for k in items]
    total = sum(weights_list)
    r = random.uniform(0, total)
    cumsum = 0
    for item, weight in zip(items, weights_list):
        cumsum += weight
        if r <= cumsum:
            return item
    return items[-1]


def generate_response(step_name: str, step_data: dict, profile: dict, verbose: bool = False) -> str:
    """Génère une réponse selon le profil de test."""

    response_type = profile.get("response_type", "random")

    if verbose:
        print(f"      📝 Génération réponse type: {response_type}")

    # Chaos modes - pick random profile for each response
    if response_type in ["chaos", "chaos_extreme"]:
        chaos_weights = profile.get("chaos_weights", {})
        sub_profile_name = weighted_random_choice(chaos_weights)
        sub_profile = TEST_PROFILES.get(sub_profile_name, TEST_PROFILES["random"])
        if verbose:
            print(f"      🎲 CHAOS: sélectionné → {sub_profile_name}")
        return generate_response(step_name, step_data, sub_profile, verbose)

    # Silence
    if response_type == "silence":
        return ""

    # From examples
    if "examples" in profile:
        response = random.choice(profile["examples"])
        if verbose:
            print(f"      📝 Exemple choisi: '{response}'")
        return response if response else ""

    # Mixed - pick random profile
    if response_type == "mixed":
        sub_profile_name = random.choice(profile.get("mix_profiles", ["random"]))
        sub_profile = TEST_PROFILES.get(sub_profile_name, TEST_PROFILES["random"])
        return generate_response(step_name, step_data, sub_profile, verbose)

    # Generate with Ollama
    if "prompt" in profile:
        base_prompt = profile["prompt"]

        # Add context about current step
        step_message = step_data.get("message_text", "")
        full_prompt = f"""Context: Le robot dit "{step_message}"
{base_prompt}
Réponds en une seule phrase courte et naturelle:"""

        response = generate_with_ollama(full_prompt)
        if verbose:
            print(f"      📝 Ollama généré: '{response}'")
        return response

    # Default random
    return generate_with_ollama("Génère une réponse courte française à un appel téléphonique")


# ═══════════════════════════════════════════════════════════════════════════
# SIMULATEUR D'APPEL
# ═══════════════════════════════════════════════════════════════════════════

class CallSimulator:
    """Simule un appel téléphonique avec le scénario."""

    def __init__(self, scenario_path: str, theme: str = "objections_finance", verbose: bool = False):
        self.verbose = verbose
        self.scenario = self._load_scenario(scenario_path)
        self.matcher = ObjectionMatcher.load_objections_for_theme(theme)

        # State
        self.current_step = "hello"
        self.call_log = []
        self.stats = defaultdict(int)
        self.autonomous_turns = defaultdict(int)
        self.return_step_stack = []

    def _load_scenario(self, path: str) -> dict:
        """Charge le scénario JSON."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _log(self, level: str, message: str):
        """Ajoute une entrée au log."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = f"[{timestamp}] [{level:8}] {message}"
        self.call_log.append(entry)
        if self.verbose:
            print(entry)

    def simulate(self, profile: dict, max_steps: int = 50) -> dict:
        """Simule un appel complet."""

        profile_name = profile.get("description", "Unknown")
        self._log("INFO", f"{'='*60}")
        self._log("INFO", f"DÉBUT SIMULATION - Profil: {profile_name}")
        self._log("INFO", f"{'='*60}")

        steps_executed = 0

        while steps_executed < max_steps:
            # Get current step data
            step_data = self.scenario["steps"].get(self.current_step)
            if not step_data:
                self._log("ERROR", f"Step '{self.current_step}' not found!")
                break

            steps_executed += 1
            self.stats["total_steps"] += 1

            # Log step info
            self._log("STEP", f"{'─'*50}")
            self._log("STEP", f"📍 Step: {self.current_step}")
            self._log("STEP", f"   Message: {step_data.get('message_text', '')[:60]}...")
            self._log("STEP", f"   Timeout: {step_data.get('timeout', 15)}s, Barge-in: {step_data.get('barge_in', True)}")

            # Check if terminal
            if step_data.get("is_terminal", False):
                result = step_data.get("result", "unknown")
                self._log("END", f"🏁 APPEL TERMINÉ - Résultat: {result}")
                self.stats["call_result"] = result
                break

            # Generate user response
            user_response = generate_response(self.current_step, step_data, profile, self.verbose)

            # Handle silence
            if not user_response or user_response.strip() == "":
                self._log("INPUT", f"🔇 SILENCE détecté")
                self.stats["silences"] += 1
                detected_intent = "silence"
                match_result = None
            else:
                self._log("INPUT", f"🎤 User: '{user_response}'")

                # Process through matcher
                match_result = self.matcher.find_best_match(
                    user_response.lower(),
                    min_score=0.70,
                    silent=not self.verbose
                )

                if match_result:
                    entry_type = match_result.get("entry_type", "objection")
                    score = match_result["score"]
                    keyword = match_result.get("matched_keyword", "")

                    self._log("MATCH", f"   ✅ Match: {entry_type.upper()} (score={score:.2f}, kw='{keyword}')")

                    # Determine intent from entry_type
                    if entry_type in ["affirm", "deny", "insult", "time", "unsure"]:
                        detected_intent = entry_type
                    elif entry_type in ["objection", "faq"]:
                        # Handle autonomous turns
                        detected_intent = self._handle_autonomous_response(entry_type, match_result)
                    else:
                        detected_intent = "*"
                else:
                    self._log("MATCH", f"   ❌ No match found")
                    detected_intent = "*"
                    self.stats["no_matches"] += 1

            # Determine next step
            intent_mapping = step_data.get("intent_mapping", {})
            next_step = intent_mapping.get(detected_intent, intent_mapping.get("*", "bye_failed"))

            # Handle template variables
            if "{{return_step}}" in str(next_step):
                if self.return_step_stack:
                    next_step = self.return_step_stack.pop()
                    self._log("FLOW", f"   ↩️  Return to: {next_step}")
                else:
                    next_step = "hello"

            # Handle retry/fallback steps - save return step
            if next_step in ["retry_silence", "retry_global", "not_understood"]:
                self.return_step_stack.append(self.current_step)
                self._log("FLOW", f"   💾 Saved return step: {self.current_step}")
                self.stats["retries"] += 1

            self._log("FLOW", f"   ➡️  Intent: {detected_intent} → Next: {next_step}")

            # Move to next step
            self.current_step = next_step

        # Final stats
        self._log("INFO", f"{'='*60}")
        self._log("STATS", f"📊 STATISTIQUES:")
        self._log("STATS", f"   Steps: {self.stats['total_steps']}")
        self._log("STATS", f"   Silences: {self.stats['silences']}")
        self._log("STATS", f"   Retries: {self.stats['retries']}")
        self._log("STATS", f"   No matches: {self.stats['no_matches']}")
        self._log("STATS", f"   Autonomous turns: {dict(self.autonomous_turns)}")
        self._log("STATS", f"   Result: {self.stats.get('call_result', 'incomplete')}")
        self._log("INFO", f"{'='*60}")

        return {
            "profile": profile_name,
            "steps": self.stats["total_steps"],
            "result": self.stats.get("call_result", "incomplete"),
            "silences": self.stats["silences"],
            "retries": self.stats["retries"],
            "no_matches": self.stats["no_matches"],
            "autonomous_turns": dict(self.autonomous_turns),
            "log": self.call_log
        }

    def _handle_autonomous_response(self, entry_type: str, match_result: dict) -> str:
        """Gère les réponses autonomes (objections/FAQ) avec limite de tours."""

        step_data = self.scenario["steps"].get(self.current_step, {})
        max_turns = step_data.get("max_autonomous_turns", 2)

        current_turns = self.autonomous_turns[self.current_step]

        if current_turns < max_turns:
            # Can respond autonomously
            self.autonomous_turns[self.current_step] += 1
            self.stats["autonomous_responses"] = self.stats.get("autonomous_responses", 0) + 1

            audio_file = match_result.get("audio_file", "")
            self._log("AUTO", f"   🤖 Réponse autonome #{current_turns + 1}/{max_turns}")
            self._log("AUTO", f"      Audio: {audio_file}")

            # Stay on same step (return current step name to continue)
            return "*"  # Wildcard to stay or use default mapping
        else:
            # Max turns reached, continue to next step
            self._log("AUTO", f"   ⚠️  Max turns atteint ({max_turns}), passage à la suite")
            return "*"


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def run_simulation(scenario_path: str, profile_name: str, num_runs: int = 1, verbose: bool = False):
    """Lance les simulations."""

    if profile_name not in TEST_PROFILES:
        print(f"❌ Profil inconnu: {profile_name}")
        print(f"   Profils disponibles: {', '.join(TEST_PROFILES.keys())}")
        return

    profile = TEST_PROFILES[profile_name]

    print("=" * 70)
    print(f"🚀 SIMULATION D'APPELS")
    print("=" * 70)
    print(f"Profil: {profile_name} - {profile['description']}")
    print(f"Runs: {num_runs}")
    print("=" * 70)
    print()

    results = []

    for i in range(num_runs):
        print(f"\n{'─'*70}")
        print(f"RUN {i+1}/{num_runs}")
        print(f"{'─'*70}")

        simulator = CallSimulator(scenario_path, verbose=verbose)
        result = simulator.simulate(profile)
        results.append(result)

        if not verbose:
            print(f"  Result: {result['result']}, Steps: {result['steps']}, Retries: {result['retries']}")

    # Summary
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ GLOBAL")
    print("=" * 70)

    outcomes = defaultdict(int)
    total_steps = 0
    total_retries = 0
    total_silences = 0

    for r in results:
        outcomes[r["result"]] += 1
        total_steps += r["steps"]
        total_retries += r["retries"]
        total_silences += r["silences"]

    print(f"\nRésultats des appels:")
    for outcome, count in outcomes.items():
        pct = count / len(results) * 100
        print(f"  {outcome}: {count} ({pct:.1f}%)")

    print(f"\nMoyennes:")
    print(f"  Steps/appel: {total_steps / len(results):.1f}")
    print(f"  Retries/appel: {total_retries / len(results):.1f}")
    print(f"  Silences/appel: {total_silences / len(results):.1f}")

    print("\n" + "=" * 70)
    print("✅ Simulation terminée")
    print("=" * 70)


def run_all_profiles(scenario_path: str, num_runs: int = 1, verbose: bool = False):
    """Lance tous les profils."""

    for profile_name in TEST_PROFILES.keys():
        print("\n" + "=" * 70)
        print(f"PROFIL: {profile_name}")
        print("=" * 70)
        run_simulation(scenario_path, profile_name, num_runs, verbose)


def main():
    parser = argparse.ArgumentParser(description="Simulateur d'appels téléphoniques")
    parser.add_argument("--scenario", "-s", default="scenarios/scen_test.json",
                       help="Chemin vers le scénario JSON")
    parser.add_argument("--profile", "-p", default="random",
                       help="Profil de test (ou 'all' pour tous)")
    parser.add_argument("--runs", "-r", type=int, default=1,
                       help="Nombre de simulations")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Afficher les logs détaillés")
    parser.add_argument("--list-profiles", "-l", action="store_true",
                       help="Lister les profils disponibles")

    args = parser.parse_args()

    if args.list_profiles:
        print("Profils de test disponibles:\n")
        for name, profile in TEST_PROFILES.items():
            print(f"  {name:20} - {profile['description']}")
        return

    if args.profile == "all":
        run_all_profiles(args.scenario, args.runs, args.verbose)
    else:
        run_simulation(args.scenario, args.profile, args.runs, args.verbose)


if __name__ == "__main__":
    main()
