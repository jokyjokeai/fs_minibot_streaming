#!/usr/bin/env python3
"""
Test Barge-in Transcription Fix
================================

Vérifie que le fix extrait bien le canal CLIENT et pas le robot.
"""

import sys
sys.path.insert(0, '.')
from system.services.faster_whisper_stt import FasterWhisperSTT

# Initialiser service
print('🚀 Initializing FasterWhisperSTT...')
stt = FasterWhisperSTT(model_name='small', device='cpu', compute_type='int8')

# Tester avec fichier barge-in stereo
bargein_file = '/usr/local/freeswitch/recordings/bargein_0a02b069-5325-4dcd-ae0f-649ad1a302cc_1762802795.wav'

print(f'\n📝 Testing transcription on: {bargein_file}')
print('Expected: Client speech (NOT robot hello.wav)')
print('')

result = stt.transcribe_file(bargein_file)

print('\n=== RESULT ===')
print(f'Text: {result["text"]}')
print(f'Confidence: {result.get("confidence", 0):.2f}')
print('')

# Vérifier si c'est le robot ou le client
robot_keywords = ['Bonjour, je suis Thierry', 'Association France Patrimoine', 'épargnants']
client_keywords = ['coupé', 'petit peu']

robot_match = any(keyword.lower() in result['text'].lower() for keyword in robot_keywords)
client_match = any(keyword.lower() in result['text'].lower() for keyword in client_keywords)

if robot_match:
    print('❌ BUG STILL PRESENT: Transcribed ROBOT audio!')
    print(f'   Found robot keywords in: {result["text"][:100]}')
elif client_match:
    print('✅ FIX WORKS: Transcribed CLIENT audio correctly!')
    print(f'   Client text: {result["text"]}')
else:
    print('⚠️  UNCLEAR: Text does not match robot or expected client keywords')
    print(f'   Got: {result["text"]}')
