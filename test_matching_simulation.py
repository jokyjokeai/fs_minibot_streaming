#!/usr/bin/env python3
"""
Script de simulation de matching - Test 100 inputs aléatoires

Teste le ObjectionMatcher avec des mots, phrases et expressions
variés pour analyser le comportement du matching.

Usage:
    python test_matching_simulation.py
    python test_matching_simulation.py --theme objections_finance
    python test_matching_simulation.py --mode random  # Mode génération aléatoire
    python test_matching_simulation.py --mode categorized  # Mode catégorisé (défaut)
"""

import sys
import os
import random
import argparse
import requests
import json
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from system.objection_matcher import ObjectionMatcher

# ═══════════════════════════════════════════════════════════════════════════
# OLLAMA INTEGRATION - Génération via LLM
# ═══════════════════════════════════════════════════════════════════════════

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral:7b"

def generate_with_ollama(prompt: str, max_tokens: int = 100, verbose: bool = False) -> str:
    """Génère du texte avec Ollama/Mistral."""
    if verbose:
        print(f"\n{'='*60}")
        print(f"📤 PROMPT ENVOYÉ À OLLAMA:")
        print(f"{'='*60}")
        print(prompt)
        print(f"{'='*60}")
        print(f"⚙️  max_tokens={max_tokens}, temperature=0.9")

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
        if verbose:
            print(f"📥 Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json().get("response", "").strip()
            if verbose:
                print(f"\n📥 RÉPONSE BRUTE OLLAMA:")
                print(f"{'─'*60}")
                print(result)
                print(f"{'─'*60}")
            return result
        else:
            if verbose:
                print(f"❌ Erreur HTTP: {response.status_code}")
                print(f"   {response.text[:200]}")
    except Exception as e:
        if verbose:
            print(f"❌ Exception: {type(e).__name__}: {e}")
    return ""


def clean_ollama_line(line: str) -> str:
    """Nettoie une ligne générée par Ollama (enlève numérotation, tirets, etc.)"""
    import re
    line = line.strip()
    # Enlever numérotation: "1.", "1)", "1-", "- ", "* "
    line = re.sub(r'^[\d]+[\.\)\-\s]+', '', line)
    line = re.sub(r'^[\-\*]\s+', '', line)
    # Enlever guillemets
    line = line.strip('"\'')
    return line.strip()


def generate_ollama_corpus(count_per_category: int = 15, verbose: bool = False) -> list:
    """Génère un corpus de test complet avec Ollama."""

    corpus = []

    print("🤖 Génération du corpus avec Ollama/Mistral...")
    if verbose:
        print(f"   Objectif: {count_per_category} items par catégorie")
        print(f"   Model: {OLLAMA_MODEL}")
        print(f"   URL: {OLLAMA_URL}")

    # 1. Mots simples (1 mot)
    prompt = f"""Génère {count_per_category} mots français simples qu'une personne pourrait dire au téléphone.
Mélange: réponses (oui, non), questions (quoi, comment), moments (matin, lundi), mots aléatoires.
Format: un mot par ligne, sans numérotation."""

    result = generate_with_ollama(prompt, 200, verbose)
    if verbose:
        print(f"\n🔍 PARSING 1_MOT:")
    words = []
    for w in result.split('\n'):
        cleaned = clean_ollama_line(w)
        word_count = len(cleaned.split()) if cleaned else 0
        if cleaned and word_count == 1:
            words.append(cleaned)
            if verbose:
                print(f"   ✅ '{cleaned}' ({word_count} mot)")
        elif cleaned and verbose:
            print(f"   ❌ '{cleaned}' ({word_count} mots) - rejeté")
    words = words[:count_per_category]
    for w in words:
        corpus.append((w, "1_MOT"))
    print(f"  1_MOT: {len(words)} générés")

    # 2. Expressions courtes (2-3 mots)
    prompt = f"""Génère exactement {count_per_category} expressions françaises de 2 ou 3 mots maximum.
Exemples: "c'est bon", "pas maintenant", "non merci", "d'accord", "trop cher", "le matin", "pas confiance"
IMPORTANT: chaque expression doit faire 2 ou 3 mots UNIQUEMENT.
Format: une expression par ligne, sans explication."""

    result = generate_with_ollama(prompt, 300, verbose)
    if verbose:
        print(f"\n🔍 PARSING 2-3_MOTS:")
    exprs = []
    for e in result.split('\n'):
        cleaned = clean_ollama_line(e)
        word_count = len(cleaned.split()) if cleaned else 0
        if cleaned and 1 < word_count <= 4:
            exprs.append(cleaned)
            if verbose:
                print(f"   ✅ '{cleaned}' ({word_count} mots)")
        elif cleaned and verbose:
            print(f"   ❌ '{cleaned}' ({word_count} mots) - rejeté")
    exprs = exprs[:count_per_category]
    for e in exprs:
        corpus.append((e, "2-3_MOTS"))
    print(f"  2-3_MOTS: {len(exprs)} générés")

    # 3. Phrases moyennes (4-6 mots)
    prompt = f"""Génère {count_per_category} phrases françaises de 4 à 6 mots qu'on dit au téléphone.
Exemples: "je suis pas intéressé", "rappelez-moi plus tard", "c'est trop cher pour moi"
Format: une phrase par ligne."""

    result = generate_with_ollama(prompt, 400, verbose)
    if verbose:
        print(f"\n🔍 PARSING 4-6_MOTS:")
    phrases = []
    for p in result.split('\n'):
        cleaned = clean_ollama_line(p)
        word_count = len(cleaned.split()) if cleaned else 0
        if cleaned and 3 < word_count <= 6:
            phrases.append(cleaned)
            if verbose:
                print(f"   ✅ '{cleaned}' ({word_count} mots)")
        elif cleaned and verbose:
            print(f"   ❌ '{cleaned}' ({word_count} mots) - rejeté")
    phrases = phrases[:count_per_category]
    for p in phrases:
        corpus.append((p, "4-6_MOTS"))
    print(f"  4-6_MOTS: {len(phrases)} générés")

    # 4. Phrases longues (7-10 mots)
    prompt = f"""Génère exactement {count_per_category} phrases françaises de 7 à 10 mots.
Contexte: réponses d'un client à un appel commercial.
Exemples: "je préfère le matin vers dix heures si possible", "je dois d'abord en parler avec ma femme"
IMPORTANT: chaque phrase doit contenir entre 7 et 10 mots.
Format: une phrase par ligne, sans explication."""

    result = generate_with_ollama(prompt, 600, verbose)
    if verbose:
        print(f"\n🔍 PARSING 7-10_MOTS:")
    phrases = []
    for p in result.split('\n'):
        cleaned = clean_ollama_line(p)
        word_count = len(cleaned.split()) if cleaned else 0
        if cleaned and 5 < word_count <= 12:
            phrases.append(cleaned)
            if verbose:
                print(f"   ✅ '{cleaned}' ({word_count} mots)")
        elif cleaned and verbose:
            print(f"   ❌ '{cleaned}' ({word_count} mots) - rejeté")
    phrases = phrases[:count_per_category]
    for p in phrases:
        corpus.append((p, "7-10_MOTS"))
    print(f"  7-10_MOTS: {len(phrases)} générés")

    # 5. Phrases très longues (11+ mots)
    prompt = f"""Génère {count_per_category} phrases françaises longues (11+ mots) qu'on dit au téléphone.
Contexte: réponses détaillées à un démarcheur.
Exemples: "oui ça m'intéresse beaucoup j'aimerais en savoir plus sur votre offre"
Format: une phrase par ligne."""

    result = generate_with_ollama(prompt, 600, verbose)
    if verbose:
        print(f"\n🔍 PARSING 11+_MOTS:")
    phrases = []
    for p in result.split('\n'):
        cleaned = clean_ollama_line(p)
        word_count = len(cleaned.split()) if cleaned else 0
        if cleaned and word_count >= 11:
            phrases.append(cleaned)
            if verbose:
                print(f"   ✅ '{cleaned[:50]}...' ({word_count} mots)")
        elif cleaned and verbose:
            print(f"   ❌ '{cleaned[:50]}...' ({word_count} mots) - rejeté")
    phrases = phrases[:count_per_category]
    for p in phrases:
        corpus.append((p, "11+_MOTS"))
    print(f"  11+_MOTS: {len(phrases)} générés")

    # 6. Random/hors sujet
    prompt = f"""Génère {count_per_category + 10} phrases ou mots français complètement hors sujet (pas liés au téléphone).
Exemples: "pizza", "le chat dort", "il fait beau aujourd'hui", "j'aime la musique"
Inclus aussi du bruit: "euh euh", "bla bla", "123"
Format: un par ligne."""

    result = generate_with_ollama(prompt, 400, verbose)
    if verbose:
        print(f"\n🔍 PARSING RANDOM:")
    randoms = []
    for r in result.split('\n'):
        cleaned = clean_ollama_line(r)
        if cleaned:
            randoms.append(cleaned)
            if verbose:
                print(f"   ✅ '{cleaned}'")
    randoms = randoms[:count_per_category + 10]
    for r in randoms:
        corpus.append((r, "RANDOM"))
    print(f"  RANDOM: {len(randoms)} générés")

    print(f"✅ Corpus total: {len(corpus)} items")
    return corpus

# ═══════════════════════════════════════════════════════════════════════════
# CORPUS DE TEST - 100+ inputs variés
# ═══════════════════════════════════════════════════════════════════════════

# Affirm variations
AFFIRM_INPUTS = [
    "oui", "ouais", "ok", "d'accord", "bien sûr", "absolument",
    "oui oui", "ah oui", "oui bien sûr", "oui pourquoi pas",
    "oui c'est bon", "ok ça marche", "ça me va", "parfait",
    "entendu", "très bien", "c'est noté", "je veux bien",
    "oui allez-y", "oui je vous écoute", "allez-y",
]

# Deny variations
DENY_INPUTS = [
    "non", "non merci", "pas intéressé", "ça m'intéresse pas",
    "non pas du tout", "absolument pas", "certainement pas",
    "je ne suis pas intéressé", "ça ne m'intéresse pas",
    "non vraiment pas", "pas pour moi", "non c'est bon",
]

# Time expressions (should map to "time" intent)
TIME_INPUTS = [
    "matin", "le matin", "demain matin", "ce matin",
    "après-midi", "cet après-midi", "l'après-midi",
    "soir", "ce soir", "demain soir", "en soirée",
    "lundi", "mardi", "mercredi", "jeudi", "vendredi",
    "la semaine prochaine", "cette semaine", "demain",
    "plutôt le matin", "plutôt le soir", "en fin de journée",
]

# Unsure expressions
UNSURE_INPUTS = [
    "je sais pas", "sais pas", "je ne sais pas",
    "pas sûr", "je suis pas sûr", "incertain",
    "euh", "hum", "hmm", "ben", "bah",
    "aucune idée", "chais pas", "jsp",
]

# Objections (should trigger objection responses)
OBJECTION_INPUTS = [
    "c'est trop cher", "trop cher", "pas le budget",
    "j'ai pas le temps", "pas le temps", "je suis occupé",
    "rappeler plus tard", "rappelez plus tard", "pas maintenant",
    "j'ai déjà", "j'en ai déjà un", "j'ai déjà une banque",
    "c'est une arnaque", "arnaque", "vous êtes des arnaqueurs",
    "je dois réfléchir", "faut que je réfléchisse",
    "je dois en parler", "faut que j'en parle à ma femme",
    "envoyez-moi un mail", "par email", "documentation",
]

# FAQ questions
FAQ_INPUTS = [
    "c'est quoi exactement", "c'est quoi votre offre",
    "comment ça marche", "expliquez-moi", "vous faites quoi",
    "c'est qui", "vous êtes qui", "quelle entreprise",
]

# Insults (should trigger immediate hangup)
INSULT_INPUTS = [
    "connard", "enculé", "va te faire foutre",
    "arrêtez de m'appeler", "retirez-moi de votre liste",
    "stop", "bloctel", "je vais porter plainte",
]

# Random/noise inputs (should be NOT_UNDERSTOOD or low score matches)
NOISE_INPUTS = [
    "la météo", "il fait beau", "quoi de neuf",
    "allo", "allô", "pardon", "quoi", "comment",
    "je comprends pas", "répétez", "vous dites",
    "attends", "une seconde", "deux minutes",
    "bonjour", "au revoir", "bonne journée",
    "merci", "s'il vous plaît", "excusez-moi",
    "c'est possible", "peut-être", "on verra",
    "pourquoi", "quand", "où", "qui", "combien",
    "le chat", "la voiture", "le travail", "les enfants",
    "pizza", "café", "vacances", "weekend",
]

# Edge cases - potential false positives
EDGE_CASES = [
    "je suis occupé",  # Could be deny or objection
    "oui mais non",  # Mixed signal
    "non mais oui",  # Mixed signal
    "oui peut-être",  # Affirm + unsure
    "c'est pas cher",  # Contains "cher" but negated
    "j'ai le temps demain",  # Contains time words
    "matin et soir",  # Multiple time words
    "je suis intéressé mais",  # Partial affirm
    "non enfin oui",  # Contradiction
    "ui",  # Partial "oui" - should NOT match
    "ou",  # Partial "oui" - should NOT match
    "no",  # Partial "non" - should NOT match
    "d'acc",  # Partial "d'accord"
    "ok ok ok",  # Repetition
]


def run_simulation(theme: str = "objections_finance", verbose: bool = False, num_tests: int = 100):
    """Run matching simulation on random inputs."""

    print("=" * 70)
    print("🧪 SIMULATION MATCHING - ObjectionMatcher")
    print("=" * 70)
    print(f"Theme: {theme}")
    print(f"Tests: {num_tests}")
    print(f"Verbose: {verbose}")
    print("=" * 70)
    print()

    # Load matcher
    matcher = ObjectionMatcher.load_objections_for_theme(theme)
    if not matcher:
        print("❌ Erreur: Impossible de charger le matcher")
        return

    print(f"✅ Matcher chargé: {len(matcher.objections)} entries, {len(matcher.keyword_lookup)} keywords")
    print()

    # Build test corpus with expected results
    test_corpus = []

    # Add categorized inputs with expected intent
    for inp in AFFIRM_INPUTS:
        test_corpus.append((inp, "affirm"))
    for inp in DENY_INPUTS:
        test_corpus.append((inp, "deny"))
    for inp in TIME_INPUTS:
        test_corpus.append((inp, "time"))
    for inp in UNSURE_INPUTS:
        test_corpus.append((inp, "unsure"))
    for inp in OBJECTION_INPUTS:
        test_corpus.append((inp, "objection"))
    for inp in FAQ_INPUTS:
        test_corpus.append((inp, "question"))
    for inp in INSULT_INPUTS:
        test_corpus.append((inp, "insult"))
    for inp in NOISE_INPUTS:
        test_corpus.append((inp, "noise"))
    for inp in EDGE_CASES:
        test_corpus.append((inp, "edge"))

    # Shuffle and take num_tests
    random.shuffle(test_corpus)
    test_corpus = test_corpus[:num_tests]

    # Statistics
    stats = defaultdict(lambda: {"total": 0, "correct": 0, "wrong": 0})
    results = []

    print("─" * 70)
    print("RÉSULTATS DES TESTS")
    print("─" * 70)

    for i, (input_text, expected_category) in enumerate(test_corpus, 1):
        # Run matching (silent mode to avoid flooding logs)
        result = matcher.find_best_match(input_text, min_score=0.70, silent=True)

        if result:
            detected_intent = result.get("entry_type", "objection")
            score = result["score"]
            keyword = result.get("matched_keyword", "")

            # Map entry_type to intent category
            if detected_intent in ["affirm", "deny", "insult", "time", "unsure"]:
                detected_category = detected_intent
            elif detected_intent == "faq":
                detected_category = "question"
            else:
                detected_category = "objection"
        else:
            detected_intent = "none"
            detected_category = "not_understood"
            score = 0.0
            keyword = ""

        # Determine if correct
        is_correct = False
        if expected_category == "noise":
            # Noise should be not_understood OR low score
            is_correct = detected_category == "not_understood" or score < 0.5
        elif expected_category == "edge":
            # Edge cases - just log, don't count as wrong
            is_correct = True
        else:
            is_correct = detected_category == expected_category

        # Update stats
        stats[expected_category]["total"] += 1
        if is_correct:
            stats[expected_category]["correct"] += 1
        else:
            stats[expected_category]["wrong"] += 1

        # Format result
        status = "✅" if is_correct else "❌"

        if verbose or not is_correct:
            print(f"{status} [{i:3d}] '{input_text}'")
            print(f"       Expected: {expected_category:15} | Got: {detected_category} (score={score:.2f}, kw='{keyword}')")
            if not is_correct:
                print(f"       ⚠️  MISMATCH!")
            print()

        results.append({
            "input": input_text,
            "expected": expected_category,
            "detected": detected_category,
            "score": score,
            "keyword": keyword,
            "correct": is_correct
        })

    # Summary
    print()
    print("=" * 70)
    print("📊 RÉSUMÉ STATISTIQUES")
    print("=" * 70)

    total_correct = sum(s["correct"] for s in stats.values())
    total_tests = sum(s["total"] for s in stats.values())

    print(f"\n{'Catégorie':<15} {'Total':>8} {'Correct':>8} {'Wrong':>8} {'Accuracy':>10}")
    print("-" * 50)

    for category in sorted(stats.keys()):
        s = stats[category]
        accuracy = (s["correct"] / s["total"] * 100) if s["total"] > 0 else 0
        marker = "✅" if accuracy >= 90 else "⚠️" if accuracy >= 70 else "❌"
        print(f"{category:<15} {s['total']:>8} {s['correct']:>8} {s['wrong']:>8} {accuracy:>8.1f}% {marker}")

    print("-" * 50)
    overall_accuracy = (total_correct / total_tests * 100) if total_tests > 0 else 0
    print(f"{'TOTAL':<15} {total_tests:>8} {total_correct:>8} {total_tests - total_correct:>8} {overall_accuracy:>8.1f}%")

    # List failures
    failures = [r for r in results if not r["correct"] and r["expected"] != "edge"]
    if failures:
        print()
        print("=" * 70)
        print(f"❌ ÉCHECS DÉTAILLÉS ({len(failures)})")
        print("=" * 70)
        for f in failures:
            print(f"\n  Input: '{f['input']}'")
            print(f"  Expected: {f['expected']}")
            print(f"  Detected: {f['detected']} (score={f['score']:.2f}, keyword='{f['keyword']}')")

    print()
    print("=" * 70)
    if overall_accuracy >= 95:
        print("🏆 EXCELLENT! Accuracy >= 95%")
    elif overall_accuracy >= 85:
        print("✅ BON. Accuracy >= 85%")
    elif overall_accuracy >= 70:
        print("⚠️  MOYEN. Accuracy >= 70% - Amélioration recommandée")
    else:
        print("❌ PROBLÈME. Accuracy < 70% - Révision nécessaire")
    print("=" * 70)

    return results


# ═══════════════════════════════════════════════════════════════════════════
# MODE RANDOM - Génération aléatoire de phrases
# ═══════════════════════════════════════════════════════════════════════════

# Vocabulaire pour génération aléatoire
VOCAB_SUJETS = ["je", "on", "nous", "vous", "c'est", "ça", "il", "elle", "ils"]
VOCAB_VERBES = ["suis", "veux", "peux", "dois", "vais", "ai", "fais", "comprends", "sais", "préfère", "attends", "rappelle"]
VOCAB_NEGATIONS = ["pas", "plus", "jamais", "vraiment pas", "absolument pas"]
VOCAB_ADVERBES = ["maintenant", "demain", "plus tard", "bientôt", "peut-être", "plutôt", "vraiment", "absolument"]
VOCAB_OBJETS = ["temps", "argent", "intérêt", "besoin", "envie", "confiance", "budget", "moment"]
VOCAB_CONTEXTE = ["au travail", "en réunion", "en voiture", "occupé", "disponible", "intéressé", "pressé"]
VOCAB_TEMPS = ["matin", "soir", "après-midi", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "semaine prochaine"]
VOCAB_FILLER = ["euh", "ben", "hum", "alors", "donc", "bon", "bah", "enfin", "voilà"]
VOCAB_RANDOM = ["pizza", "chat", "météo", "football", "musique", "voiture", "enfants", "travail", "vacances", "film"]

def generate_random_phrase(length_category: str) -> str:
    """Génère une phrase aléatoire selon la catégorie de longueur."""

    if length_category == "1_MOT":
        # Un seul mot aléatoire
        choices = ["oui", "non", "quoi", "comment", "pourquoi", "merci", "pardon",
                   "matin", "soir", "demain", "jamais", "allo", "combien", "peut-être"]
        choices += VOCAB_RANDOM
        return random.choice(choices)

    elif length_category == "2-3_MOTS":
        patterns = [
            lambda: f"{random.choice(['oui', 'non'])} {random.choice(['merci', 'vraiment', 'absolument'])}",
            lambda: f"{random.choice(VOCAB_SUJETS)} {random.choice(VOCAB_VERBES)}",
            lambda: f"pas {random.choice(VOCAB_OBJETS)}",
            lambda: f"c'est {random.choice(['bon', 'cher', 'possible', 'intéressant'])}",
            lambda: f"{random.choice(VOCAB_FILLER)} {random.choice(VOCAB_FILLER)}",
            lambda: f"le {random.choice(VOCAB_TEMPS)}",
        ]
        return random.choice(patterns)()

    elif length_category == "4-6_MOTS":
        patterns = [
            lambda: f"je {random.choice(['suis', 'ne suis'])} pas {random.choice(VOCAB_CONTEXTE)}",
            lambda: f"j'ai pas {random.choice(['le temps', 'le budget', 'confiance', 'envie'])}",
            lambda: f"c'est {random.choice(['trop cher', 'pas le moment', 'une arnaque'])} pour moi",
            lambda: f"rappelez-moi {random.choice(['plus tard', 'demain', 'la semaine prochaine'])}",
            lambda: f"{random.choice(VOCAB_FILLER)} je {random.choice(VOCAB_VERBES)} {random.choice(VOCAB_NEGATIONS)}",
            lambda: f"plutôt le {random.choice(VOCAB_TEMPS)} si possible",
        ]
        return random.choice(patterns)()

    elif length_category == "7-10_MOTS":
        patterns = [
            lambda: f"je préfère le {random.choice(VOCAB_TEMPS)} vers {random.randint(8,18)} heures",
            lambda: f"je dois d'abord en parler avec {random.choice(['ma femme', 'mon mari', 'mon banquier'])}",
            lambda: f"vous pouvez m'envoyer ça par {random.choice(['mail', 'courrier', 'sms'])} s'il vous plaît",
            lambda: f"c'est {random.choice(VOCAB_FILLER)} je suis {random.choice(VOCAB_CONTEXTE)} là maintenant",
            lambda: f"non {random.choice(['merci', 'vraiment'])} {random.choice(VOCAB_FILLER)} c'est pas pour moi",
            lambda: f"oui {random.choice(['pourquoi pas', 'ça peut', 'ça pourrait'])} m'intéresser {random.choice(['peut-être', 'éventuellement'])}",
        ]
        return random.choice(patterns)()

    elif length_category == "11+_MOTS":
        patterns = [
            lambda: f"oui ça m'intéresse beaucoup j'aimerais en savoir plus sur {random.choice(['votre offre', 'ce que vous proposez', 'les détails'])}",
            lambda: f"non vraiment pas du tout ça ne m'intéresse {random.choice(VOCAB_NEGATIONS)} merci {random.choice(['quand même', 'au revoir', 'bonne journée'])}",
            lambda: f"écoutez je suis {random.choice(VOCAB_CONTEXTE)} là je ne peux {random.choice(VOCAB_NEGATIONS)} vous parler maintenant",
            lambda: f"je vais {random.choice(['y réfléchir', 'en parler', 'voir ça'])} et je vous rappelle quand j'aurai pris ma décision",
            lambda: f"rappelez-moi plutôt {random.choice(['en fin de journée', 'demain matin', 'la semaine prochaine'])} ce serait mieux pour moi",
            lambda: f"je ne suis pas sûr que ça corresponde à mes {random.choice(['besoins', 'attentes', 'critères'])} actuels mais pourquoi pas",
        ]
        return random.choice(patterns)()

    else:  # RANDOM - hors sujet
        patterns = [
            lambda: random.choice(VOCAB_RANDOM),
            lambda: f"le {random.choice(VOCAB_RANDOM)} est {random.choice(['bien', 'là', 'parti'])}",
            lambda: f"j'aime {random.choice(['beaucoup', 'bien'])} le {random.choice(VOCAB_RANDOM)}",
            lambda: f"{random.choice(['asdfgh', 'qwerty', '12345', 'bla bla'])}",
            lambda: f"{random.choice(VOCAB_FILLER)} {random.choice(VOCAB_FILLER)} {random.choice(VOCAB_FILLER)}",
        ]
        return random.choice(patterns)()


# Corpus fixe pour comparaison (optionnel)
# 15 mots simples (1 mot)
MOTS_SIMPLES = [
    "oui", "non", "quoi", "comment", "pourquoi", "merci", "pardon",
    "matin", "soir", "demain", "lundi", "jamais", "toujours", "combien", "allo"
]

# 15 expressions courtes (2-3 mots)
EXPRESSIONS_COURTES = [
    "c'est bon", "d'accord", "pas du tout", "bien sûr", "ça marche",
    "pas maintenant", "on verra", "c'est cher", "absolument pas", "non merci",
    "pas intéressé", "trop cher", "je comprends", "bonne journée", "à voir"
]

# 15 phrases moyennes (4-6 mots)
PHRASES_MOYENNES = [
    "je suis pas intéressé", "j'ai pas le temps", "c'est trop cher pour moi",
    "rappelez-moi plus tard", "je suis occupé maintenant", "laissez-moi réfléchir",
    "c'est quoi exactement", "vous êtes qui vous", "envoyez-moi un mail",
    "j'ai déjà une banque", "je dois en parler", "plutôt le matin",
    "la semaine prochaine", "c'est une arnaque", "non vraiment pas du tout"
]

# 15 phrases longues (7-10 mots)
PHRASES_LONGUES = [
    "je préfère le matin vers dix heures si possible",
    "je dois d'abord en parler avec ma femme",
    "vous pouvez m'envoyer ça par mail s'il vous plaît",
    "je ne suis pas sûr que ça corresponde",
    "c'est quoi exactement votre offre je comprends pas",
    "oui la semaine prochaine ça me va bien",
    "plutôt mercredi ou jeudi en fin de matinée",
    "c'est pas le moment là je suis en réunion",
    "bon d'accord allez-y je vous écoute",
    "qu'est-ce que vous voulez exactement de moi",
    "je suis déjà client chez vous depuis longtemps",
    "j'ai pas confiance dans ce genre de proposition",
    "arrêtez de m'appeler j'en ai marre de vous",
    "retirez-moi de votre liste s'il vous plaît",
    "c'est gentil mais j'ai déjà tout ce qu'il faut"
]

# 15 phrases très longues (11+ mots)
PHRASES_TRES_LONGUES = [
    "oui ça m'intéresse beaucoup j'aimerais en savoir plus sur votre offre",
    "non vraiment pas du tout ça ne m'intéresse absolument pas merci quand même",
    "attendez je suis en train de conduire là je ne peux vraiment pas parler maintenant",
    "écoutez je suis au travail je ne peux vraiment pas vous parler là c'est pas possible",
    "rappelez-moi plutôt en fin de journée après dix-huit heures ce serait mieux pour moi",
    "je dois d'abord en parler avec ma femme avant de prendre une décision c'est important",
    "je ne sais pas je vais y réfléchir et je vous rappelle quand j'aurai pris ma décision",
    "je vais porter plainte si vous continuez à m'appeler comme ça c'est du harcèlement",
    "vous pouvez m'envoyer toute la documentation par mail pour que je puisse regarder tranquillement",
    "je ne suis pas sûr que ça corresponde à mes besoins actuels mais pourquoi pas en discuter",
    "c'est une arnaque votre truc j'en suis absolument certain ne me rappelez plus jamais",
    "oui pourquoi pas ça pourrait m'intéresser donnez-moi plus d'informations sur ce que vous proposez",
    "non merci je ne suis vraiment pas intéressé par ce type de service bonne journée au revoir",
    "je préfère attendre un peu avant de me décider c'est un engagement important quand même",
    "écoutez je vais être honnête avec vous ça ne m'intéresse pas du tout mais merci d'avoir appelé"
]

# 25 inputs random/hors sujet (mix de longueurs)
RANDOM_INPUTS = [
    # Mots simples hors sujet
    "pizza", "chat", "météo", "football", "vacances", "café", "musique",
    # Expressions hors sujet
    "il fait beau", "le train arrive", "mon chien dort",
    # Phrases moyennes hors sujet
    "j'ai mangé une pomme ce matin", "paris est une belle ville",
    "les enfants sont à l'école aujourd'hui", "la voiture est au garage",
    # Phrases longues hors sujet
    "j'aime beaucoup la musique classique surtout le piano",
    "le film que j'ai vu hier était vraiment très bien",
    "mon chien s'appelle rex et il adore jouer dans le jardin",
    # Bruit/gibberish
    "asdfghjkl", "123456", "bla bla bla", "euh ben euh", "hum hum",
    "attends attends", "une seconde", "quoi quoi quoi", "allô allô vous m'entendez"
]


def run_random_simulation(theme: str = "objections_finance", run_number: int = 1, collect_issues: list = None):
    """Run random generation simulation - no expected results, just analysis."""

    print("=" * 70)
    print(f"🎲 SIMULATION RANDOM - Run #{run_number}")
    print("=" * 70)
    print(f"Theme: {theme}")
    print("=" * 70)
    print()

    # Load matcher
    matcher = ObjectionMatcher.load_objections_for_theme(theme)
    if not matcher:
        print("❌ Erreur: Impossible de charger le matcher")
        return

    print(f"✅ Matcher chargé: {len(matcher.objections)} entries, {len(matcher.keyword_lookup)} keywords")
    print()

    # Build test corpus: 15+15+15+15+15+25 = 100 total
    # GÉNÉRATION ALÉATOIRE - nouvelles phrases à chaque run
    test_corpus = []

    # Générer des phrases aléatoires pour chaque catégorie
    for _ in range(15):
        test_corpus.append((generate_random_phrase("1_MOT"), "1_MOT"))
    for _ in range(15):
        test_corpus.append((generate_random_phrase("2-3_MOTS"), "2-3_MOTS"))
    for _ in range(15):
        test_corpus.append((generate_random_phrase("4-6_MOTS"), "4-6_MOTS"))
    for _ in range(15):
        test_corpus.append((generate_random_phrase("7-10_MOTS"), "7-10_MOTS"))
    for _ in range(15):
        test_corpus.append((generate_random_phrase("11+_MOTS"), "11+_MOTS"))
    for _ in range(25):
        test_corpus.append((generate_random_phrase("RANDOM"), "RANDOM"))

    # Shuffle
    random.shuffle(test_corpus)


def run_ollama_simulation(theme: str = "objections_finance", run_number: int = 1, collect_issues: list = None, verbose: bool = False):
    """Run simulation with Ollama-generated corpus."""

    print("=" * 70)
    print(f"🤖 SIMULATION OLLAMA - Run #{run_number}")
    print("=" * 70)
    print(f"Theme: {theme}")
    if verbose:
        print(f"🔧 MODE VERBOSE ACTIVÉ - Logs ultra détaillés")
    print("=" * 70)
    print()

    # Load matcher
    matcher = ObjectionMatcher.load_objections_for_theme(theme)
    if not matcher:
        print("❌ Erreur: Impossible de charger le matcher")
        return

    print(f"✅ Matcher chargé: {len(matcher.objections)} entries, {len(matcher.keyword_lookup)} keywords")
    print()

    # Generate corpus with Ollama
    test_corpus = generate_ollama_corpus(count_per_category=15, verbose=verbose)

    if len(test_corpus) < 50:
        print("⚠️  Corpus trop petit, utilisation du fallback...")
        # Fallback to random generation
        test_corpus = []
        for _ in range(15):
            test_corpus.append((generate_random_phrase("1_MOT"), "1_MOT"))
        for _ in range(15):
            test_corpus.append((generate_random_phrase("2-3_MOTS"), "2-3_MOTS"))
        for _ in range(15):
            test_corpus.append((generate_random_phrase("4-6_MOTS"), "4-6_MOTS"))
        for _ in range(15):
            test_corpus.append((generate_random_phrase("7-10_MOTS"), "7-10_MOTS"))
        for _ in range(15):
            test_corpus.append((generate_random_phrase("11+_MOTS"), "11+_MOTS"))
        for _ in range(25):
            test_corpus.append((generate_random_phrase("RANDOM"), "RANDOM"))

    # Shuffle
    random.shuffle(test_corpus)

    # Statistics par catégorie détectée
    detected_stats = defaultdict(int)
    score_ranges = {"high": 0, "medium": 0, "low": 0, "none": 0}
    results_by_type = defaultdict(list)

    print("─" * 70)
    print(f"RÉSULTATS ({len(test_corpus)} tests)")
    print("─" * 70)
    print()

    for i, (input_text, input_type) in enumerate(test_corpus, 1):
        if verbose:
            print(f"\n{'═'*70}")
            print(f"🔍 TEST #{i}: '{input_text}'")
            print(f"   Type: {input_type}")
            print(f"{'─'*70}")

        # Use silent=False when verbose for detailed matching logs
        result = matcher.find_best_match(input_text, min_score=0.70, silent=not verbose)

        if verbose:
            if result:
                print(f"   📊 Résultat brut: {result}")
            else:
                print(f"   📊 Résultat: AUCUN MATCH")

        if result:
            entry_type = result.get("entry_type", "objection")
            score = result["score"]
            keyword = result.get("matched_keyword", "")

            if entry_type in ["affirm", "deny", "insult", "time", "unsure"]:
                detected = entry_type.upper()
            elif entry_type == "faq":
                detected = "FAQ"
            else:
                detected = "OBJECTION"

            if score >= 0.9:
                score_range = "high"
                score_icon = "🟢"
            elif score >= 0.7:
                score_range = "medium"
                score_icon = "🟡"
            else:
                score_range = "low"
                score_icon = "🟠"
        else:
            detected = "NONE"
            score = 0.0
            keyword = ""
            score_range = "none"
            score_icon = "⚪"

        detected_stats[detected] += 1
        score_ranges[score_range] += 1

        # Print result
        print(f"{score_icon} [{i:3d}] [{input_type:12}] '{input_text[:50]}{'...' if len(input_text) > 50 else ''}'")
        print(f"       → {detected:10} | score={score:.2f} | kw='{keyword}'")

        # Log issues
        is_issue = False
        issue_reason = ""

        if input_type in ["1_MOT", "RANDOM"] and 0.65 <= score < 0.7:
            is_issue = True
            issue_reason = f"FUZZY_LOW_SCORE ({score:.2f})"

        if input_type == "RANDOM" and score >= 0.7:
            is_issue = True
            issue_reason = f"RANDOM_HIGH_MATCH ({score:.2f})"

        if score >= 0.5 and len(keyword) > 0:
            input_chars = set(input_text.lower().replace(" ", ""))
            kw_chars = set(keyword.lower().replace(" ", ""))
            overlap = len(input_chars & kw_chars) / max(len(input_chars), len(kw_chars)) if max(len(input_chars), len(kw_chars)) > 0 else 0
            if overlap < 0.15 and score >= 0.5:
                is_issue = True
                issue_reason = f"SEMANTIC_MISMATCH (overlap={overlap:.2f})"

        if is_issue:
            print(f"       ⚠️  ISSUE: {issue_reason}")
            if collect_issues is not None:
                collect_issues.append({
                    "run": run_number,
                    "input": input_text,
                    "input_type": input_type,
                    "detected": detected,
                    "score": score,
                    "keyword": keyword,
                    "reason": issue_reason
                })

        print()

        results_by_type[input_type].append({
            "input": input_text,
            "detected": detected,
            "score": score,
            "keyword": keyword
        })

    # Summary
    print()
    print("=" * 70)
    print("📊 RÉSUMÉ PAR CATÉGORIE DÉTECTÉE")
    print("=" * 70)

    print(f"\n{'Détecté':<15} {'Count':>8} {'%':>8}")
    print("-" * 35)
    for det in sorted(detected_stats.keys()):
        pct = detected_stats[det] / len(test_corpus) * 100
        print(f"{det:<15} {detected_stats[det]:>8} {pct:>7.1f}%")

    print()
    print("=" * 70)
    print("📊 RÉSUMÉ PAR NIVEAU DE SCORE")
    print("=" * 70)

    print(f"\n🟢 High (>=0.9):   {score_ranges['high']:>3}")
    print(f"🟡 Medium (0.7-0.9): {score_ranges['medium']:>3}")
    print(f"🟠 Low (0.65-0.7):  {score_ranges['low']:>3}")
    print(f"⚪ None (<0.65):    {score_ranges['none']:>3}")

    print()
    print("=" * 70)
    print("📊 ANALYSE PAR TYPE D'INPUT")
    print("=" * 70)

    for input_type in ["1_MOT", "2-3_MOTS", "4-6_MOTS", "7-10_MOTS", "11+_MOTS", "RANDOM"]:
        results = results_by_type.get(input_type, [])
        if not results:
            continue
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0
        none_count = sum(1 for r in results if r["detected"] == "NONE")

        print(f"\n{input_type}:")
        print(f"  Score moyen: {avg_score:.2f}")
        print(f"  Non matchés: {none_count}/{len(results)}")

        det_counts = defaultdict(int)
        for r in results:
            det_counts[r["detected"]] += 1
        top_det = sorted(det_counts.items(), key=lambda x: -x[1])[:3]
        print(f"  Top détections: {', '.join([f'{d}({c})' for d, c in top_det])}")

    print()
    print("=" * 70)
    print("✅ Simulation terminée")
    print("=" * 70)

    return detected_stats, score_ranges, results_by_type

    # Statistics par catégorie détectée
    detected_stats = defaultdict(int)
    score_ranges = {"high": 0, "medium": 0, "low": 0, "none": 0}
    results_by_type = defaultdict(list)

    print("─" * 70)
    print("RÉSULTATS (100 tests)")
    print("─" * 70)
    print()

    for i, (input_text, input_type) in enumerate(test_corpus, 1):
        result = matcher.find_best_match(input_text, min_score=0.70, silent=True)

        if result:
            entry_type = result.get("entry_type", "objection")
            score = result["score"]
            keyword = result.get("matched_keyword", "")

            # Map to category
            if entry_type in ["affirm", "deny", "insult", "time", "unsure"]:
                detected = entry_type.upper()
            elif entry_type == "faq":
                detected = "FAQ"
            else:
                detected = "OBJECTION"

            # Score range
            if score >= 0.9:
                score_range = "high"
                score_icon = "🟢"
            elif score >= 0.7:
                score_range = "medium"
                score_icon = "🟡"
            else:
                score_range = "low"
                score_icon = "🟠"
        else:
            detected = "NONE"
            score = 0.0
            keyword = ""
            score_range = "none"
            score_icon = "⚪"

        detected_stats[detected] += 1
        score_ranges[score_range] += 1

        # Print result with detailed logging
        print(f"{score_icon} [{i:3d}] [{input_type:12}] '{input_text[:40]}{'...' if len(input_text) > 40 else ''}'")
        print(f"       → {detected:10} | score={score:.2f} | kw='{keyword}' (len={len(keyword)})")

        # Log potential issues
        is_issue = False
        issue_reason = ""

        # Issue 1: Low score match on simple words (fuzzy false positive)
        if input_type in ["MOT_SIMPLE", "RANDOM"] and 0.4 <= score < 0.7:
            is_issue = True
            issue_reason = f"FUZZY_LOW_SCORE ({score:.2f})"

        # Issue 2: RANDOM input matched with high score (should be NONE)
        if input_type == "RANDOM" and score >= 0.7:
            is_issue = True
            issue_reason = f"RANDOM_HIGH_MATCH ({score:.2f})"

        # Issue 3: Semantic mismatch (keyword doesn't relate to input)
        if score >= 0.5 and len(keyword) > 0:
            # Check if keyword shares any significant chars with input
            input_chars = set(input_text.lower().replace(" ", ""))
            kw_chars = set(keyword.lower().replace(" ", ""))
            overlap = len(input_chars & kw_chars) / max(len(input_chars), len(kw_chars))
            if overlap < 0.15 and score >= 0.5:
                is_issue = True
                issue_reason = f"SEMANTIC_MISMATCH (overlap={overlap:.2f})"

        if is_issue:
            print(f"       ⚠️  ISSUE: {issue_reason}")
            if collect_issues is not None:
                collect_issues.append({
                    "run": run_number,
                    "input": input_text,
                    "input_type": input_type,
                    "detected": detected,
                    "score": score,
                    "keyword": keyword,
                    "reason": issue_reason
                })

        print()

        results_by_type[input_type].append({
            "input": input_text,
            "detected": detected,
            "score": score,
            "keyword": keyword
        })

    # Summary
    print()
    print("=" * 70)
    print("📊 RÉSUMÉ PAR CATÉGORIE DÉTECTÉE")
    print("=" * 70)

    print(f"\n{'Détecté':<15} {'Count':>8} {'%':>8}")
    print("-" * 35)
    for det in sorted(detected_stats.keys()):
        pct = detected_stats[det] / 100 * 100
        print(f"{det:<15} {detected_stats[det]:>8} {pct:>7.1f}%")

    print()
    print("=" * 70)
    print("📊 RÉSUMÉ PAR NIVEAU DE SCORE")
    print("=" * 70)

    print(f"\n🟢 High (>=0.9):   {score_ranges['high']:>3}")
    print(f"🟡 Medium (0.7-0.9): {score_ranges['medium']:>3}")
    print(f"🟠 Low (0.4-0.7):   {score_ranges['low']:>3}")
    print(f"⚪ None (<0.4):     {score_ranges['none']:>3}")

    # Analysis par type d'input
    print()
    print("=" * 70)
    print("📊 ANALYSE PAR TYPE D'INPUT")
    print("=" * 70)

    for input_type in ["1_MOT", "2-3_MOTS", "4-6_MOTS", "7-10_MOTS", "11+_MOTS", "RANDOM"]:
        results = results_by_type[input_type]
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0
        none_count = sum(1 for r in results if r["detected"] == "NONE")

        print(f"\n{input_type}:")
        print(f"  Score moyen: {avg_score:.2f}")
        print(f"  Non matchés: {none_count}/{len(results)}")

        # Top detections
        det_counts = defaultdict(int)
        for r in results:
            det_counts[r["detected"]] += 1
        top_det = sorted(det_counts.items(), key=lambda x: -x[1])[:3]
        print(f"  Top détections: {', '.join([f'{d}({c})' for d, c in top_det])}")

    print()
    print("=" * 70)
    print("✅ Simulation terminée")
    print("=" * 70)

    return detected_stats, score_ranges, results_by_type


def run_multiple_simulations(theme: str = "objections_finance", num_runs: int = 10):
    """Run multiple simulations and collect all issues for analysis."""

    print("=" * 70)
    print(f"🔄 ANALYSE MULTI-RUN - {num_runs} exécutions")
    print("=" * 70)
    print()

    all_issues = []

    for run in range(1, num_runs + 1):
        print(f"\n{'#' * 70}")
        print(f"# RUN {run}/{num_runs}")
        print(f"{'#' * 70}\n")

        run_random_simulation(theme=theme, run_number=run, collect_issues=all_issues)

    # Final analysis
    print("\n" + "=" * 70)
    print("📊 ANALYSE GLOBALE - TOUS LES RUNS")
    print("=" * 70)

    if not all_issues:
        print("\n✅ Aucun problème détecté sur les {num_runs} runs!")
        return

    # Count issues by type
    issue_counts = defaultdict(int)
    issue_by_input = defaultdict(list)
    issue_by_keyword = defaultdict(int)

    for issue in all_issues:
        reason_type = issue["reason"].split(" ")[0]
        issue_counts[reason_type] += 1
        issue_by_input[issue["input"]].append(issue)
        issue_by_keyword[issue["keyword"]] += 1

    print(f"\n📈 Total issues détectées: {len(all_issues)}")
    print(f"   Issues par run: {len(all_issues) / num_runs:.1f}")

    print("\n📊 Issues par type:")
    print("-" * 40)
    for reason, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
        print(f"   {reason}: {count}")

    print("\n🔥 TOP 10 inputs problématiques (récurrents):")
    print("-" * 60)
    sorted_inputs = sorted(issue_by_input.items(), key=lambda x: -len(x[1]))[:10]
    for inp, issues in sorted_inputs:
        print(f"\n   '{inp}' ({len(issues)} occurrences)")
        # Show what it matched to
        matches = defaultdict(int)
        for iss in issues:
            matches[f"{iss['detected']}:{iss['keyword']}"] += 1
        for match, cnt in sorted(matches.items(), key=lambda x: -x[1]):
            print(f"      → {match} (x{cnt})")

    print("\n🎯 TOP 10 keywords qui causent des faux positifs:")
    print("-" * 60)
    sorted_kw = sorted(issue_by_keyword.items(), key=lambda x: -x[1])[:10]
    for kw, count in sorted_kw:
        print(f"   '{kw}': {count} faux positifs")

    print("\n" + "=" * 70)
    print("📝 RECOMMANDATIONS:")
    print("=" * 70)

    # Generate recommendations based on issues
    recommendations = []

    # Check for common patterns
    if issue_counts.get("FUZZY_LOW_SCORE", 0) > num_runs * 5:
        recommendations.append("- Augmenter min_score de 0.4 à 0.5 ou 0.6")

    if issue_counts.get("SEMANTIC_MISMATCH", 0) > num_runs * 3:
        recommendations.append("- Ajouter word boundary check plus strict")
        recommendations.append("- Filtrer les matches avec overlap < 0.15")

    if issue_counts.get("RANDOM_HIGH_MATCH", 0) > num_runs * 2:
        recommendations.append("- Vérifier les keywords trop courts ou génériques")

    # Check specific problematic keywords
    for kw, count in sorted_kw[:5]:
        if count >= num_runs * 2:
            recommendations.append(f"- Réviser le keyword '{kw}' (trop de faux positifs)")

    if recommendations:
        for rec in recommendations:
            print(rec)
    else:
        print("- Aucune recommandation majeure")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Test ObjectionMatcher avec inputs aléatoires")
    parser.add_argument("--theme", default="objections_finance", help="Theme file à charger")
    parser.add_argument("--verbose", "-v", action="store_true", help="Afficher tous les résultats")
    parser.add_argument("--num", "-n", type=int, default=100, help="Nombre de tests")
    parser.add_argument("--mode", "-m", choices=["categorized", "random", "multi", "ollama"], default="random",
                       help="Mode: categorized, random, multi, ou ollama (génération LLM)")
    parser.add_argument("--runs", "-r", type=int, default=10, help="Nombre de runs pour mode multi")

    args = parser.parse_args()

    if args.mode == "ollama":
        run_ollama_simulation(theme=args.theme, verbose=args.verbose)
    elif args.mode == "multi":
        run_multiple_simulations(theme=args.theme, num_runs=args.runs)
    elif args.mode == "random":
        run_random_simulation(theme=args.theme)
    else:
        run_simulation(
            theme=args.theme,
            verbose=args.verbose,
            num_tests=args.num
        )


if __name__ == "__main__":
    main()
