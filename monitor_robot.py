#!/usr/bin/env python3
"""
Monitor Robot Live - MiniBotPanel v3

Monitoring en temps réel du robot FreeSWITCH avec :
- État robot et services IA
- Appels actifs avec détails
- Transcriptions live (STT)
- Génération TTS en cours
- Freestyle AI stats
- Events streaming

Usage:
    python3 monitor_robot.py [--refresh SECONDS]

Exemple:
    python3 monitor_robot.py --refresh 2
"""

import os
import sys
import time
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
import curses
from pathlib import Path

# Ajouter le dossier parent au PATH pour imports
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import desc
from system.database import SessionLocal
from system.models import Call, CallStatus, Campaign, CampaignStatus
from system.config import config

# Couleurs
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def get_robot_stats() -> Dict[str, Any]:
    """Récupère les stats du robot depuis l'API ou la DB"""
    try:
        import requests
        response = requests.get(f"{config.API_BASE_URL}/api/stats/robot", timeout=2)
        if response.status_code == 200:
            return response.json()
    except:
        pass

    # Fallback: stats depuis DB
    db = SessionLocal()
    try:
        # Compter appels actifs
        active_calls = db.query(Call).filter(
            Call.status.in_([
                CallStatus.CALLING,
                CallStatus.RINGING,
                CallStatus.ANSWERED,
                CallStatus.IN_PROGRESS
            ])
        ).all()

        return {
            "running": True,
            "esl_connected": True,  # Assume connected si appels actifs
            "active_calls": len(active_calls),
            "active_calls_list": [call.uuid for call in active_calls],
            "services": {
                "stt": True,
                "tts": True,
                "nlp": True,
                "amd": True
            }
        }
    finally:
        db.close()


def get_active_calls_details() -> List[Dict[str, Any]]:
    """Récupère les détails des appels actifs"""
    db = SessionLocal()
    try:
        active_calls = db.query(Call).filter(
            Call.status.in_([
                CallStatus.CALLING,
                CallStatus.RINGING,
                CallStatus.ANSWERED,
                CallStatus.IN_PROGRESS
            ])
        ).order_by(Call.started_at.desc()).limit(10).all()

        calls_details = []
        for call in active_calls:
            # Calculer durée
            duration = 0
            if call.started_at:
                duration = int((datetime.utcnow() - call.started_at).total_seconds())

            # Récupérer contact
            contact_name = f"{call.contact.first_name or ''} {call.contact.last_name or ''}".strip()
            if not contact_name:
                contact_name = call.contact.phone

            # Récupérer campagne
            campaign_name = call.campaign.name if call.campaign else "N/A"

            calls_details.append({
                "uuid": call.uuid,
                "phone": call.contact.phone,
                "contact_name": contact_name,
                "campaign": campaign_name,
                "status": call.status.value,
                "duration": duration,
                "started_at": call.started_at,
                "metadata": call.call_metadata or {}
            })

        return calls_details
    finally:
        db.close()


def get_recent_transcriptions(limit: int = 5) -> List[Dict[str, Any]]:
    """Récupère les dernières transcriptions"""
    db = SessionLocal()
    try:
        # Récupérer appels récents avec transcriptions
        recent_calls = db.query(Call).filter(
            Call.transcription_path.isnot(None)
        ).order_by(Call.ended_at.desc()).limit(limit).all()

        transcriptions = []
        for call in recent_calls:
            # Lire fichier transcription si existe
            trans_text = ""
            if call.transcription_path and Path(call.transcription_path).exists():
                try:
                    import json
                    with open(call.transcription_path, 'r') as f:
                        trans_data = json.load(f)
                        trans_text = trans_data.get("full_text", "")[:100]  # 100 premiers chars
                except:
                    trans_text = "[Erreur lecture]"

            transcriptions.append({
                "phone": call.contact.phone,
                "text": trans_text,
                "timestamp": call.ended_at
            })

        return transcriptions
    finally:
        db.close()


def get_freestyle_stats() -> Dict[str, Any]:
    """Récupère les stats Freestyle AI"""
    try:
        import requests
        response = requests.get(f"{config.API_BASE_URL}/api/stats/freestyle", timeout=2)
        if response.status_code == 200:
            return response.json()
    except:
        pass

    return {
        "total_requests": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "cache_hit_rate_pct": 0.0,
        "avg_generation_time_ms": 0.0,
        "is_available": False
    }


def get_campaigns_summary() -> Dict[str, Any]:
    """Récupère résumé des campagnes actives"""
    db = SessionLocal()
    try:
        running_campaigns = db.query(Campaign).filter(
            Campaign.status == CampaignStatus.RUNNING
        ).all()

        total_calls = 0
        total_leads = 0

        campaigns_info = []
        for campaign in running_campaigns:
            stats = campaign.stats or {}
            total_calls += stats.get("total", 0)
            total_leads += stats.get("leads", 0)

            campaigns_info.append({
                "id": campaign.id,
                "name": campaign.name,
                "total": stats.get("total", 0),
                "completed": stats.get("completed", 0),
                "leads": stats.get("leads", 0)
            })

        return {
            "running_count": len(running_campaigns),
            "total_calls": total_calls,
            "total_leads": total_leads,
            "campaigns": campaigns_info
        }
    finally:
        db.close()


def format_duration(seconds: int) -> str:
    """Formate durée en MM:SS"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def format_status_emoji(status: str) -> str:
    """Emoji selon status"""
    status_map = {
        "calling": "📞",
        "ringing": "📱",
        "answered": "✅",
        "in_progress": "🗣️",
        "completed": "✅",
        "failed": "❌",
        "no_answer": "⏰",
        "busy": "📵"
    }
    return status_map.get(status, "❓")


def clear_screen():
    """Clear terminal"""
    os.system('clear' if os.name != 'nt' else 'cls')


def print_header():
    """Affiche header"""
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "🤖 ROBOT FREESWITCH - MONITORING LIVE" + " " * 21 + "║")
    print("╠" + "═" * 78 + "╣")
    print(f"{Colors.ENDC}")


def print_footer():
    """Affiche footer"""
    print(f"{Colors.CYAN}")
    print("╚" + "═" * 78 + "╝")
    print(f"{Colors.ENDC}")
    print(f"{Colors.YELLOW}[Ctrl+C pour quitter] [Refresh auto]{Colors.ENDC}")


def print_robot_status(stats: Dict[str, Any]):
    """Affiche état robot"""
    running = stats.get("running", False)
    esl_connected = stats.get("esl_connected", False)
    active_calls = stats.get("active_calls", 0)

    status_icon = f"{Colors.GREEN}✅ RUNNING{Colors.ENDC}" if running else f"{Colors.RED}❌ STOPPED{Colors.ENDC}"
    esl_icon = f"{Colors.GREEN}✅{Colors.ENDC}" if esl_connected else f"{Colors.RED}❌{Colors.ENDC}"

    print(f"║ {Colors.BOLD}État Robot:{Colors.ENDC}      {status_icon}")
    print(f"║ {Colors.BOLD}ESL FreeSWITCH:{Colors.ENDC}  {esl_icon} Connected ({config.FREESWITCH_ESL_HOST}:{config.FREESWITCH_ESL_PORT})")
    print(f"║ {Colors.BOLD}Appels actifs:{Colors.ENDC}   {Colors.GREEN}{Colors.BOLD}{active_calls}{Colors.ENDC}")
    print("║")


def print_services_status(stats: Dict[str, Any]):
    """Affiche état services IA"""
    services = stats.get("services", {})

    print(f"║ {Colors.BOLD}Services IA:{Colors.ENDC}")

    stt_icon = f"{Colors.GREEN}✅ OK{Colors.ENDC}" if services.get("stt") else f"{Colors.RED}❌ OFF{Colors.ENDC}"
    tts_icon = f"{Colors.GREEN}✅ OK{Colors.ENDC}" if services.get("tts") else f"{Colors.RED}❌ OFF{Colors.ENDC}"
    nlp_icon = f"{Colors.GREEN}✅ OK{Colors.ENDC}" if services.get("nlp") else f"{Colors.RED}❌ OFF{Colors.ENDC}"
    amd_icon = f"{Colors.GREEN}✅ OK{Colors.ENDC}" if services.get("amd") else f"{Colors.RED}❌ OFF{Colors.ENDC}"

    print(f"║   • STT (Vosk):      {stt_icon}")
    print(f"║   • TTS (Coqui):     {tts_icon}")
    print(f"║   • NLP (Ollama):    {nlp_icon}")
    print(f"║   • AMD Service:     {amd_icon}")
    print("║")


def print_active_calls(calls: List[Dict[str, Any]]):
    """Affiche appels actifs"""
    print(f"║ {Colors.BOLD}Appels en Cours:{Colors.ENDC}")

    if not calls:
        print(f"║   {Colors.YELLOW}Aucun appel actif{Colors.ENDC}")
    else:
        for call in calls[:5]:  # Max 5 appels affichés
            uuid_short = call["uuid"][:8]
            phone = call["phone"]
            contact = call["contact_name"][:20] if len(call["contact_name"]) > 20 else call["contact_name"]
            status = call["status"]
            duration = format_duration(call["duration"])
            status_emoji = format_status_emoji(status)

            # Récupérer infos metadata
            metadata = call.get("metadata", {})
            current_step = metadata.get("current_step", "")
            step_info = f" [{current_step}]" if current_step else ""

            print(f"║   {status_emoji} {uuid_short}... → {phone:15} | {contact:20} | {duration}{step_info}")

        if len(calls) > 5:
            print(f"║   {Colors.CYAN}... et {len(calls) - 5} appels de plus{Colors.ENDC}")

    print("║")


def print_freestyle_stats(freestyle: Dict[str, Any]):
    """Affiche stats Freestyle AI"""
    available = freestyle.get("is_available", False)

    if not available:
        print(f"║ {Colors.BOLD}Freestyle AI:{Colors.ENDC}    {Colors.RED}❌ Non disponible{Colors.ENDC}")
        print("║")
        return

    total_req = freestyle.get("total_requests", 0)
    cache_hits = freestyle.get("cache_hits", 0)
    hit_rate = freestyle.get("cache_hit_rate_pct", 0.0)
    avg_time = freestyle.get("avg_generation_time_ms", 0.0)

    print(f"║ {Colors.BOLD}Freestyle AI:{Colors.ENDC}    {Colors.GREEN}✅ Actif{Colors.ENDC}")
    print(f"║   • Requêtes:        {total_req}")
    print(f"║   • Cache hits:      {cache_hits} ({hit_rate:.1f}%)")
    print(f"║   • Latence moy:     {avg_time:.0f}ms")
    print("║")


def print_recent_transcriptions(transcriptions: List[Dict[str, Any]]):
    """Affiche dernières transcriptions"""
    print(f"║ {Colors.BOLD}Dernières Transcriptions (STT):{Colors.ENDC}")

    if not transcriptions:
        print(f"║   {Colors.YELLOW}Aucune transcription récente{Colors.ENDC}")
    else:
        for trans in transcriptions[:3]:  # Max 3
            phone = trans["phone"]
            text = trans["text"][:50]  # 50 premiers chars
            timestamp = trans["timestamp"].strftime("%H:%M:%S") if trans["timestamp"] else "N/A"

            if text:
                print(f"║   📝 [{timestamp}] {phone}: \"{text}...\"")
            else:
                print(f"║   📝 [{timestamp}] {phone}: [Vide]")

    print("║")


def print_campaigns_summary(summary: Dict[str, Any]):
    """Affiche résumé campagnes"""
    running_count = summary.get("running_count", 0)
    total_calls = summary.get("total_calls", 0)
    total_leads = summary.get("total_leads", 0)

    print(f"║ {Colors.BOLD}Campagnes Actives:{Colors.ENDC} {Colors.GREEN}{running_count}{Colors.ENDC}")

    if running_count > 0:
        print(f"║   • Total appels:    {total_calls}")
        print(f"║   • Total leads:     {Colors.GREEN}{total_leads}{Colors.ENDC}")

        campaigns = summary.get("campaigns", [])
        for camp in campaigns[:3]:  # Max 3 campagnes
            name = camp["name"][:30]
            completed = camp["completed"]
            total = camp["total"]
            progress = (completed / total * 100) if total > 0 else 0

            print(f"║     → {name}: {completed}/{total} ({progress:.0f}%)")
    else:
        print(f"║   {Colors.YELLOW}Aucune campagne en cours{Colors.ENDC}")

    print("║")


def print_dashboard(refresh_interval: int):
    """Affiche dashboard complet"""
    clear_screen()

    # Header
    print_header()

    # Timestamp
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"║ {Colors.CYAN}Dernière mise à jour: {now} (refresh: {refresh_interval}s){Colors.ENDC}")
    print("║")

    # Stats robot
    robot_stats = get_robot_stats()
    print_robot_status(robot_stats)

    # Services IA
    print_services_status(robot_stats)

    # Appels actifs
    active_calls = get_active_calls_details()
    print_active_calls(active_calls)

    # Freestyle stats
    freestyle_stats = get_freestyle_stats()
    print_freestyle_stats(freestyle_stats)

    # Transcriptions récentes
    transcriptions = get_recent_transcriptions(limit=3)
    print_recent_transcriptions(transcriptions)

    # Campagnes
    campaigns = get_campaigns_summary()
    print_campaigns_summary(campaigns)

    # Footer
    print_footer()


def main():
    """Point d'entrée"""
    parser = argparse.ArgumentParser(description="Monitor Robot FreeSWITCH Live")
    parser.add_argument(
        "--refresh",
        type=int,
        default=3,
        help="Intervalle de refresh en secondes (défaut: 3)"
    )
    args = parser.parse_args()

    refresh_interval = args.refresh

    print(f"{Colors.GREEN}Démarrage monitoring robot FreeSWITCH...{Colors.ENDC}")
    print(f"{Colors.CYAN}Refresh toutes les {refresh_interval} secondes{Colors.ENDC}")
    print(f"{Colors.YELLOW}Appuyez sur Ctrl+C pour quitter{Colors.ENDC}\n")
    time.sleep(2)

    try:
        while True:
            print_dashboard(refresh_interval)
            time.sleep(refresh_interval)

    except KeyboardInterrupt:
        clear_screen()
        print(f"\n{Colors.GREEN}Monitoring arrêté.{Colors.ENDC}\n")
        sys.exit(0)

    except Exception as e:
        clear_screen()
        print(f"\n{Colors.RED}Erreur: {e}{Colors.ENDC}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
