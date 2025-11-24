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
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from system.objection_matcher import ObjectionMatcher

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
        result = matcher.find_best_match(input_text, min_score=0.65, silent=True)

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
# MODE RANDOM - Corpus systématique par longueur
# ═══════════════════════════════════════════════════════════════════════════

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
    # Couverture systématique de toutes les longueurs
    test_corpus = []

    for word in MOTS_SIMPLES:
        test_corpus.append((word, "1_MOT"))
    for expr in EXPRESSIONS_COURTES:
        test_corpus.append((expr, "2-3_MOTS"))
    for phrase in PHRASES_MOYENNES:
        test_corpus.append((phrase, "4-6_MOTS"))
    for phrase in PHRASES_LONGUES:
        test_corpus.append((phrase, "7-10_MOTS"))
    for phrase in PHRASES_TRES_LONGUES:
        test_corpus.append((phrase, "11+_MOTS"))
    for rand in RANDOM_INPUTS:
        test_corpus.append((rand, "RANDOM"))

    # Shuffle
    random.shuffle(test_corpus)

    # Statistics par catégorie détectée
    detected_stats = defaultdict(int)
    score_ranges = {"high": 0, "medium": 0, "low": 0, "none": 0}
    results_by_type = defaultdict(list)

    print("─" * 70)
    print("RÉSULTATS (100 tests)")
    print("─" * 70)
    print()

    for i, (input_text, input_type) in enumerate(test_corpus, 1):
        result = matcher.find_best_match(input_text, min_score=0.65, silent=True)

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
            if overlap < 0.3 and score >= 0.5:
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
        recommendations.append("- Filtrer les matches avec overlap < 0.3")

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
    parser.add_argument("--mode", "-m", choices=["categorized", "random", "multi"], default="random",
                       help="Mode: categorized, random, ou multi (10 runs)")
    parser.add_argument("--runs", "-r", type=int, default=10, help="Nombre de runs pour mode multi")

    args = parser.parse_args()

    if args.mode == "multi":
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
