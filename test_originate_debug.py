#!/usr/bin/env python3
"""
Script de debug pour tester la commande originate FreeSWITCH
"""
import sys
sys.path.insert(0, '/usr/share/freeswitch/scripts')
from ESL import ESLconnection
import time

# Configuration
ESL_HOST = "localhost"
ESL_PORT = 8021
ESL_PASSWORD = "ClueCon"
GATEWAY = "gateway1"
PHONE = "33743130341"

print("=" * 60)
print("🔍 DEBUG ORIGINATE - Test direct ESL")
print("=" * 60)

# Connexion ESL
print(f"\n📡 Connexion à FreeSWITCH ESL ({ESL_HOST}:{ESL_PORT})...")
conn = ESLconnection(ESL_HOST, str(ESL_PORT), ESL_PASSWORD)

if not conn.connected():
    print("❌ Échec connexion ESL")
    exit(1)

print("✅ Connecté à FreeSWITCH ESL")

# Test 1: Vérifier le gateway
print(f"\n🔍 Test 1: Vérification gateway '{GATEWAY}'")
result = conn.api("sofia status gateway " + GATEWAY)
status_body = result.getBody() if hasattr(result, 'getBody') else str(result)
print(f"Réponse: {status_body}")

# Test 2: Commande originate simple (sans variables)
print(f"\n🔍 Test 2: Originate SIMPLE (sans variables)")
dial_string_simple = f"sofia/gateway/{GATEWAY}/{PHONE}"
cmd_simple = f"originate {dial_string_simple} &park()"
print(f"Commande: {cmd_simple}")

result = conn.api(cmd_simple)
result_body = result.getBody() if hasattr(result, 'getBody') else str(result)
print(f"✅ Réponse FreeSWITCH:\n{result_body}")
print(f"Type de réponse: {type(result_body)}")

if "+OK" in result_body:
    print("✅ Appel lancé avec succès !")
    parts = result_body.split()
    if len(parts) > 1:
        uuid = parts[1].strip()
        print(f"UUID: {uuid}")
        time.sleep(2)
        # Vérifier le statut du canal
        check_result = conn.api(f"uuid_getvar {uuid} call_uuid")
        print(f"État du canal: {check_result.getBody()}")
else:
    print(f"❌ Échec appel: {result_body}")

# Test 3: Avec variables (comme dans le code)
print(f"\n🔍 Test 3: Originate AVEC VARIABLES (comme le code)")
vars_str = "campaign_id=0,scenario=dfdf,retry_count=0"
dial_string_vars = f"{{{vars_str}}}sofia/gateway/{GATEWAY}/{PHONE}"
cmd_vars = f"originate {dial_string_vars} &park()"
print(f"Commande: {cmd_vars}")

result2 = conn.api(cmd_vars)
result2_body = result2.getBody() if hasattr(result2, 'getBody') else str(result2)
print(f"✅ Réponse FreeSWITCH:\n{result2_body}")

if "+OK" in result2_body:
    print("✅ Appel lancé avec succès !")
else:
    print(f"❌ Échec appel: {result2_body}")

print("\n" + "=" * 60)
print("✅ Tests terminés")
print("=" * 60)
