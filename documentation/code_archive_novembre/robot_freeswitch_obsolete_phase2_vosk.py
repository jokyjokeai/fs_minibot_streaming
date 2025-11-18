"""
Archive du code obsolète - robot_freeswitch.py
Date: 2025-11-17
Raison: Fonction _execute_phase_playing_vosk jamais utilisée

Cette fonction utilisait mod_vosk (FreeSWITCH module) pour le barge-in en Phase 2.
Elle a été remplacée par _execute_phase_playing_streaming qui utilise uuid_audio_fork
+ WebSocket Vosk, architecture plus flexible et performante.

Archivé pour référence historique, ne pas utiliser dans le code actif.
"""

def _execute_phase_playing_vosk(
    self,
    call_uuid: str,
    audio_path: str,
    enable_barge_in: bool = True
) -> Dict[str, Any]:
    """
    Phase 2: PLAYING avec mod_vosk (alternative streaming native)

    Utilise mod_vosk pour barge-in streaming natif au lieu de WebRTC VAD.

    Avantages vs méthode actuelle (WebRTC VAD):
    - Latence réduite: ~150ms vs ~600ms
    - Transcription native temps réel (pas de snapshots)
    - Événements FreeSWITCH natifs (DETECTED_SPEECH)
    - Pas de gestion complexe threads VAD

    Architecture:
    1. Créer grammar XML barge-in
    2. Lancer play_and_detect_speech avec mod_vosk
    3. Écouter événements DETECTED_SPEECH
    4. Détecter parole >1.5s → uuid_break
    5. Retourner transcription

    Args:
        call_uuid: UUID appel
        audio_path: Chemin fichier audio à jouer
        enable_barge_in: Activer barge-in (True par défaut)

    Returns:
        {
            "barged_in": bool,
            "transcription": str,
            "audio_duration": float,
            "latency_ms": float
        }
    """
    short_uuid = call_uuid[:8]
    phase_start = time.time()

    # PHASE 2 START - Colored log
    self.clog.phase2_start(Path(audio_path).name, uuid=short_uuid)

    # État détection
    detection_state = {
        "barged_in": False,
        "transcription": "",
        "speech_duration": 0.0,
        "audio_finished": False
    }

    grammar_path = None

    try:
        # Vérifier mod_vosk disponible
        if not self.vosk_service.check_module_loaded(self.esl_conn_api):
            logger.warning(
                f"⚠️ [{short_uuid}] mod_vosk not loaded, "
                f"falling back to WebRTC VAD method"
            )
            return self._execute_phase_playing(
                call_uuid, audio_path, enable_barge_in
            )

        # Étape 1: Créer grammar barge-in
        grammar_xml = self.vosk_service.create_bargein_grammar(
            grammar_id="bargein",
            keywords=config.VOSK_BARGEIN_GRAMMAR_KEYWORDS
        )

        grammar_filename = f"bargein_{call_uuid}.xml"
        grammar_path = self.vosk_service.save_grammar_file(
            grammar_xml, grammar_filename
        )

        logger.info(
            f"📝 [{short_uuid}] Vosk grammar created: {grammar_path} "
            f"({len(config.VOSK_BARGEIN_GRAMMAR_KEYWORDS)} keywords)"
        )

        # Étape 2: Lancer play_and_detect_speech
        if enable_barge_in:
            esl_commands = self.vosk_service.get_esl_commands_for_detection(
                call_uuid, audio_path, grammar_path
            )

            # SOLUTION PRO: Transfer call to dialplan with detect_speech
            # This is the ONLY way to use detect_speech from ESL external

            # Set channel variables for dialplan
            logger.info(f"🔧 [{short_uuid}] Setting channel variables for Vosk dialplan:")
            logger.info(f"   - vosk_grammar_name: default")
            logger.info(f"   - vosk_grammar_path: {grammar_path}")
            logger.info(f"   - audio_file_path: {audio_path}")

            self._execute_esl_command(f"uuid_setvar {call_uuid} vosk_grammar_name default")
            self._execute_esl_command(f"uuid_setvar {call_uuid} vosk_grammar_path {grammar_path}")
            self._execute_esl_command(f"uuid_setvar {call_uuid} audio_file_path {audio_path}")

            # Vérifier que fichier audio existe
            if not Path(audio_path).exists():
                logger.error(f"❌ [{short_uuid}] Audio file does not exist: {audio_path}")
                return self._execute_phase_playing(call_uuid, audio_path, enable_barge_in)

            # Transfer to vosk_detect dialplan
            logger.info(f"🎙️ [{short_uuid}] Transferring to Vosk dialplan for streaming detection...")
            transfer_result = self._execute_esl_command(f"uuid_transfer {call_uuid} vosk_detect XML default")

            if not transfer_result or "+OK" not in transfer_result:
                logger.error(
                    f"❌ [{short_uuid}] uuid_transfer to vosk_detect failed: {transfer_result}"
                )
                # Fallback vers méthode classique
                return self._execute_phase_playing(
                    call_uuid, audio_path, enable_barge_in
                )

            logger.info(f"✅ [{short_uuid}] Vosk streaming detection started via dialplan transfer")

            # Vérifier connexion ESL events avant de commencer
            if not self.esl_conn_events:
                logger.error(f"❌ [{short_uuid}] ESL events connection is None, cannot monitor")
                # Fallback: méthode classique
                return self._execute_phase_playing(call_uuid, audio_path, enable_barge_in)

            logger.debug(f"🔍 [{short_uuid}] Starting event monitoring loop...")

            # Étape 3: Écouter événements DETECTED_SPEECH
            speech_start_time = None
            cumulative_text = []

            # Timeout = durée audio estimée + marge
            # TODO: Calculer durée réelle du fichier audio
            timeout = 30.0  # 30s max par défaut

            monitoring_start = time.time()

            logger.debug(f"🔍 [{short_uuid}] Entering while loop (timeout: {timeout}s)...")

            while (time.time() - monitoring_start) < timeout:
                # Recevoir événement avec timeout 100ms
                try:
                    event = self.esl_conn_events.recvEventTimed(100)
                except Exception as e:
                    logger.error(f"❌ [{short_uuid}] Error receiving event: {e}")
                    continue

                if not event:
                    # Pas d'événement, continuer
                    continue

                # Parser événement DETECTED_SPEECH avec protection
                detection = None
                try:
                    # Log event type pour debug
                    event_name = event.getHeader("Event-Name") if event else None
                    if event_name:
                        logger.debug(f"📥 [{short_uuid}] Received event: {event_name}")

                    detection = self.vosk_service.parse_detected_speech_event(event)
                except Exception as e:
                    logger.error(
                        f"❌ [{short_uuid}] Error parsing event: {e}",
                        exc_info=True
                    )
                    # Continue loop même si parsing échoue
                    detection = None

                if detection:
                    logger.debug(
                        f"🎙️ [{short_uuid}] Vosk: '{detection.text}' "
                        f"(confidence: {detection.confidence:.2f})"
                    )

                    # Filtrer par seuil de confiance
                    if detection.confidence < config.VOSK_CONFIDENCE_THRESHOLD:
                        logger.debug(
                            f"⏭️  [{short_uuid}] Low confidence, ignoring"
                        )
                        continue

                    # Accumuler texte
                    if detection.text and detection.text not in cumulative_text:
                        cumulative_text.append(detection.text)
                        detection_state["transcription"] = " ".join(cumulative_text)

                    # Détecter début de parole
                    if not speech_start_time:
                        speech_start_time = time.time()
                        logger.info(
                            f"🗣️ [{short_uuid}] Speech detected, monitoring duration..."
                        )

                    # Calculer durée parole
                    speech_duration = time.time() - speech_start_time
                    detection_state["speech_duration"] = speech_duration

                    # Vérifier seuil barge-in
                    if speech_duration >= config.BARGE_IN_THRESHOLD:
                        logger.info(
                            f"⚡ [{short_uuid}] BARGE-IN triggered! "
                            f"(speech: {speech_duration:.1f}s > {config.BARGE_IN_THRESHOLD}s)"
                        )

                        # Smooth delay
                        logger.info(
                            f"🔉 [{short_uuid}] Smooth delay: "
                            f"{config.BARGE_IN_SMOOTH_DELAY}s..."
                        )
                        time.sleep(config.BARGE_IN_SMOOTH_DELAY)

                        # Arrêter playback
                        stop_result = self._execute_esl_command(
                            esl_commands["stop"]
                        )
                        logger.info(f"🔇 [{short_uuid}] Audio stopped")

                        detection_state["barged_in"] = True
                        break

                # Vérifier si audio terminé
                # (event PLAYBACK_STOP ou fin timeout)
                if event:
                    try:
                        event_name = event.getHeader("Event-Name")
                        if event_name == "PLAYBACK_STOP":
                            logger.info(
                                f"🔊 [{short_uuid}] Audio playback finished "
                                f"(no barge-in)"
                            )
                            detection_state["audio_finished"] = True
                            break
                    except Exception as e:
                        logger.debug(f"⚠️  [{short_uuid}] Error checking PLAYBACK_STOP: {e}")

        else:
            # Barge-in désactivé: simple playback
            logger.info(f"🔊 [{short_uuid}] Playing audio (no barge-in)...")
            self._execute_esl_command(f"uuid_broadcast {call_uuid} {audio_path}")

            # Attendre durée audio (estimation)
            # TODO: Calculer durée réelle
            time.sleep(10.0)

        # Cleanup grammar
        if grammar_path and grammar_path.exists():
            try:
                grammar_path.unlink()
            except:
                pass

        # Total latency
        total_latency = (time.time() - phase_start) * 1000

        # Transcription log
        if detection_state["transcription"]:
            self.clog.transcription(
                detection_state["transcription"], uuid=short_uuid
            )

        # PHASE 2 END
        self.clog.phase2_end(total_latency, uuid=short_uuid)

        return {
            "barged_in": detection_state["barged_in"],
            "transcription": detection_state["transcription"],
            "audio_duration": total_latency / 1000.0,
            "latency_ms": total_latency
        }

    except Exception as e:
        logger.error(f"❌ [{short_uuid}] Vosk PLAYING error: {e}")
        import traceback
        traceback.print_exc()

        # Cleanup
        if grammar_path and grammar_path.exists():
            try:
                grammar_path.unlink()
            except:
                pass

        # Fallback vers méthode classique
        logger.warning(
            f"⚠️ [{short_uuid}] Falling back to WebRTC VAD method"
        )
        return self._execute_phase_playing(
            call_uuid, audio_path, enable_barge_in
        )
