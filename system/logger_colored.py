# -*- coding: utf-8 -*-
"""
Colored Logger Module - MiniBotPanel v3 🎨

Module de logging colorisé avec rich pour améliorer la lisibilité des logs.
Design futuriste avec panels, bordures, et effets visuels.

Usage:
    from system.logger_colored import ColoredLogger

    clog = ColoredLogger()
    clog.phase1_start(uuid="abc123")
    clog.transcription("Bonjour!", uuid="abc123")
    clog.latency(150.5, "Recording", uuid="abc123")
    clog.phase1_end(3077, uuid="abc123")
"""

import logging
from typing import Optional

# Try to import rich, fallback to standard logging if not available
try:
    from rich.console import Console
    from rich.text import Text
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)


class ColoredLogger:
    """
    Colored Logger using Rich - Futuristic Design 🚀

    Provides colored logging with panels, borders, and visual effects.
    Falls back to standard logging if rich is not available.
    """

    # Color scheme (futuristic cyberpunk theme)
    COLORS = {
        # Phases
        "phase1": "bold yellow",           # AMD
        "phase1_border": "yellow",
        "phase2": "bold green",             # PLAYING
        "phase2_border": "green",
        "phase3": "bold magenta",           # WAITING
        "phase3_border": "magenta",

        # Information types
        "transcription": "bold cyan",       # Texte transcrit
        "latency": "bold red",              # Latences/métriques
        "latency_good": "bold green",       # Latence < 2000ms
        "latency_warning": "bold yellow",   # Latence 2000-3000ms
        "latency_bad": "bold red",          # Latence > 3000ms
        "success": "bold green",            # Succès
        "warning": "bold orange1",          # Avertissements
        "error": "bold red",                # Erreurs
        "info": "white",                    # Info standard
        "debug": "dim white",               # Debug
    }

    # Box styles pour les panels
    BOX_STYLES = {
        "phase1": box.DOUBLE_EDGE,      # AMD - Double bordure
        "phase2": box.HEAVY,            # PLAYING - Bordure épaisse
        "phase3": box.ROUNDED,          # WAITING - Bordure arrondie
        "transcription": box.SIMPLE,    # Transcription - Simple
        "latency": box.MINIMAL,         # Latency - Minimal
    }

    def __init__(self, enabled: bool = True):
        """
        Initialize ColoredLogger

        Args:
            enabled: Enable colored output (default: True)
        """
        self.enabled = enabled and RICH_AVAILABLE

        if self.enabled:
            self.console = Console()
            logger.debug("ColoredLogger initialized with rich support 🎨")
        else:
            self.console = None
            if not RICH_AVAILABLE:
                logger.warning(
                    "rich library not available, falling back to standard logging"
                )

    def _log_simple(
        self,
        message: str,
        color: str = "white",
        emoji: str = "",
        uuid: Optional[str] = None,
        level: str = "INFO"
    ):
        """
        Simple log method (no panel)

        Args:
            message: Message to log
            color: Color from COLORS dict
            emoji: Emoji prefix
            uuid: Short UUID (8 chars)
            level: Log level
        """
        uuid_prefix = f"[{uuid}] " if uuid else ""
        emoji_prefix = f"{emoji} " if emoji else ""
        full_message = f"{emoji_prefix}{uuid_prefix}{message}"

        if self.enabled and self.console:
            text = Text(full_message, style=color)
            self.console.print(text)
        else:
            log_method = getattr(logger, level.lower(), logger.info)
            log_method(full_message)

    def _log_panel(
        self,
        message: str,
        title: str,
        color: str,
        box_style: box.Box,
        emoji: str = "",
        uuid: Optional[str] = None
    ):
        """
        Log with panel (futuristic design)

        Args:
            message: Panel content
            title: Panel title
            color: Border color
            box_style: Box style (DOUBLE_EDGE/HEAVY/ROUNDED)
            emoji: Emoji for title
            uuid: Short UUID (8 chars)
        """
        if not self.enabled or not self.console:
            # Fallback
            self._log_simple(f"{title}: {message}", color=color, emoji=emoji, uuid=uuid)
            return

        # Format title with UUID
        uuid_str = f" [{uuid}]" if uuid else ""
        full_title = f"{emoji} {title}{uuid_str}"

        # Create panel
        panel = Panel(
            Text(message, style=color),
            title=full_title,
            title_align="left",
            border_style=color,
            box=box_style,
            padding=(0, 1)
        )

        self.console.print(panel)

    # ========== PHASE 1: AMD ==========

    def phase1_start(self, uuid: Optional[str] = None):
        """
        Log PHASE 1 START with futuristic panel (YELLOW)
        """
        self._log_panel(
            message="Answering Machine Detection - Recording + Transcription",
            title="PHASE 1: AMD START",
            color=self.COLORS["phase1_border"],
            box_style=self.BOX_STYLES["phase1"],
            emoji="🎧",
            uuid=uuid
        )

    def phase1_end(self, total_ms: float, uuid: Optional[str] = None):
        """
        Log PHASE 1 END with total latency (YELLOW)
        """
        # Choose color based on latency
        if total_ms < 2500:
            status = "EXCELLENT"
            color = self.COLORS["latency_good"]
        elif total_ms < 3200:
            status = "GOOD"
            color = self.COLORS["latency_warning"]
        else:
            status = "SLOW"
            color = self.COLORS["latency_bad"]

        message = f"Total: {total_ms:.0f}ms - Status: {status}"
        self._log_panel(
            message=message,
            title="PHASE 1: AMD END",
            color=self.COLORS["phase1_border"],
            box_style=self.BOX_STYLES["phase1"],
            emoji="✅",
            uuid=uuid
        )

    def phase1(self, message: str, uuid: Optional[str] = None, emoji: str = "🎧"):
        """
        Log PHASE 1 message (simple, no panel) in YELLOW
        """
        self._log_simple(message, color=self.COLORS["phase1"], emoji=emoji, uuid=uuid)

    # ========== PHASE 2: PLAYING ==========

    def phase2_start(
        self,
        audio_file: str,
        uuid: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ):
        """
        Log PHASE 2 START with futuristic panel (GREEN)

        Args:
            audio_file: Audio file name
            uuid: Short UUID (8 chars)
            duration_seconds: Audio duration in seconds (for verification)
        """
        # Format message with duration if available
        if duration_seconds:
            message = f"Playing: {audio_file} (duration: {duration_seconds:.2f}s) - Barge-in: ENABLED"
        else:
            message = f"Playing: {audio_file} - Barge-in: ENABLED"

        self._log_panel(
            message=message,
            title="PHASE 2: PLAYING START",
            color=self.COLORS["phase2_border"],
            box_style=self.BOX_STYLES["phase2"],
            emoji="🎙️",
            uuid=uuid
        )

    def phase2_end(self, total_ms: float, uuid: Optional[str] = None):
        """
        Log PHASE 2 END with total latency and status (GREEN)
        """
        # Choose status based on latency
        if total_ms < 4000:
            status = "EXCELLENT"
            color = self.COLORS["latency_good"]
        elif total_ms < 6000:
            status = "GOOD"
            color = self.COLORS["latency_warning"]
        else:
            status = "SLOW"
            color = self.COLORS["latency_bad"]

        message = f"Total: {total_ms:.0f}ms - Status: {status}"
        self._log_panel(
            message=message,
            title="PHASE 2: PLAYING END",
            color=self.COLORS["phase2_border"],
            box_style=self.BOX_STYLES["phase2"],
            emoji="✅",
            uuid=uuid
        )

    def phase2(self, message: str, uuid: Optional[str] = None, emoji: str = "🎙️"):
        """
        Log PHASE 2 message (simple, no panel) in GREEN
        """
        self._log_simple(message, color=self.COLORS["phase2"], emoji=emoji, uuid=uuid)

    # ========== PHASE 3: WAITING ==========

    def phase3_start(self, uuid: Optional[str] = None):
        """
        Log PHASE 3 START with futuristic panel (MAGENTA)
        """
        self._log_panel(
            message="Listening for client response - Silence detection: ENABLED",
            title="PHASE 3: WAITING START",
            color=self.COLORS["phase3_border"],
            box_style=self.BOX_STYLES["phase3"],
            emoji="👂",
            uuid=uuid
        )

    def phase3_end(self, total_ms: float, uuid: Optional[str] = None):
        """
        Log PHASE 3 END with total latency and status (MAGENTA)
        """
        # Choose status based on latency
        if total_ms < 2000:
            status = "EXCELLENT"
            color = self.COLORS["latency_good"]
        elif total_ms < 3000:
            status = "GOOD"
            color = self.COLORS["latency_warning"]
        else:
            status = "SLOW"
            color = self.COLORS["latency_bad"]

        message = f"Total: {total_ms:.0f}ms - Status: {status}"
        self._log_panel(
            message=message,
            title="PHASE 3: WAITING END",
            color=self.COLORS["phase3_border"],
            box_style=self.BOX_STYLES["phase3"],
            emoji="✅",
            uuid=uuid
        )

    def phase3(self, message: str, uuid: Optional[str] = None, emoji: str = "👂"):
        """
        Log PHASE 3 message (simple, no panel) in MAGENTA
        """
        self._log_simple(message, color=self.COLORS["phase3"], emoji=emoji, uuid=uuid)

    # ========== TRANSCRIPTION (BLUE/CYAN) ==========

    def transcription(
        self,
        text: str,
        uuid: Optional[str] = None,
        latency_ms: Optional[float] = None
    ):
        """
        Log transcription with panel (CYAN)

        Args:
            text: Transcribed text
            uuid: Short UUID (8 chars)
            latency_ms: Optional transcription latency
        """
        # Truncate if too long
        display_text = text if len(text) <= 100 else f"{text[:100]}..."

        # Add latency if provided
        if latency_ms:
            message = f"'{display_text}' (latency: {latency_ms:.0f}ms)"
        else:
            message = f"'{display_text}'"

        self._log_panel(
            message=message,
            title="TRANSCRIPTION",
            color=self.COLORS["transcription"],
            box_style=self.BOX_STYLES["transcription"],
            emoji="📝",
            uuid=uuid
        )

    # ========== LATENCY (RED/ORANGE/GREEN) ==========

    def latency(
        self,
        latency_ms: float,
        component: str = "",
        uuid: Optional[str] = None
    ):
        """
        Log latency metric with colored indicator

        Args:
            latency_ms: Latency in milliseconds
            component: Component name
            uuid: Short UUID (8 chars)
        """
        # Choose color based on latency
        if latency_ms < 1000:
            color = self.COLORS["latency_good"]
            indicator = "🟢"
        elif latency_ms < 2000:
            color = self.COLORS["latency_warning"]
            indicator = "🟡"
        else:
            color = self.COLORS["latency_bad"]
            indicator = "🔴"

        if component:
            message = f"{indicator} {component}: {latency_ms:.0f}ms"
        else:
            message = f"{indicator} Latency: {latency_ms:.0f}ms"

        self._log_simple(message, color=color, emoji="⏱️", uuid=uuid)

    def latency_table(
        self,
        latencies: dict,
        uuid: Optional[str] = None
    ):
        """
        Log multiple latencies in a table (futuristic!)

        Args:
            latencies: Dict {component: latency_ms}
            uuid: Short UUID (8 chars)

        Example:
            clog.latency_table({
                "Recording": 2418,
                "Transcription": 242,
                "Total": 3077
            }, uuid="abc123")
        """
        if not self.enabled or not self.console:
            # Fallback
            for comp, lat in latencies.items():
                self.latency(lat, comp, uuid=uuid)
            return

        # Create table
        table = Table(
            title=f"⏱️ LATENCY METRICS [{uuid}]" if uuid else "⏱️ LATENCY METRICS",
            box=box.ROUNDED,
            border_style="bright_red",
            show_header=True,
            header_style="bold bright_red"
        )

        table.add_column("Component", style="cyan", justify="left")
        table.add_column("Latency", style="bold bright_red", justify="right")
        table.add_column("Status", justify="center")

        # Add rows
        for component, latency_ms in latencies.items():
            # Status indicator
            if latency_ms < 1000:
                status = "🟢 FAST"
                style = "bold green"
            elif latency_ms < 2000:
                status = "🟡 OK"
                style = "bold yellow"
            else:
                status = "🔴 SLOW"
                style = "bold red"

            table.add_row(
                component,
                f"{latency_ms:.0f}ms",
                Text(status, style=style)
            )

        self.console.print(table)

    # ========== SUCCESS / WARNING / ERROR ==========

    def success(self, message: str, uuid: Optional[str] = None):
        """Log success message in GREEN"""
        self._log_simple(message, color=self.COLORS["success"], emoji="✅", uuid=uuid)

    def warning(self, message: str, uuid: Optional[str] = None):
        """Log warning message in ORANGE"""
        self._log_simple(
            message,
            color=self.COLORS["warning"],
            emoji="⚠️",
            uuid=uuid,
            level="WARNING"
        )

    def error(self, message: str, uuid: Optional[str] = None):
        """Log error message in RED"""
        self._log_simple(
            message,
            color=self.COLORS["error"],
            emoji="❌",
            uuid=uuid,
            level="ERROR"
        )

    def info(self, message: str, uuid: Optional[str] = None, emoji: str = ""):
        """Log standard info message"""
        self._log_simple(message, color=self.COLORS["info"], emoji=emoji, uuid=uuid)

    def debug(self, message: str, uuid: Optional[str] = None):
        """Log debug message"""
        self._log_simple(
            message,
            color=self.COLORS["debug"],
            emoji="🔍",
            uuid=uuid,
            level="DEBUG"
        )


# Global instance for convenience
_clog_instance = None


def get_colored_logger() -> ColoredLogger:
    """
    Get global ColoredLogger instance (singleton)

    Returns:
        ColoredLogger instance
    """
    global _clog_instance
    if _clog_instance is None:
        _clog_instance = ColoredLogger()
    return _clog_instance


# Unit tests
if __name__ == "__main__":
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich import box

    console = Console()

    # Header futuriste
    header = Panel(
        Text("COLOREDLOGGER - FUTURISTIC DESIGN TEST 🚀", style="bold cyan", justify="center"),
        box=box.DOUBLE,
        border_style="bold bright_cyan",
        padding=(1, 2)
    )
    console.print(header)

    clog = ColoredLogger()
    uuid = "abc12345"

    # Test PHASE 1
    console.print("\n")
    clog.phase1_start(uuid=uuid)
    clog.phase1("RTP stream primed, ready to record", uuid=uuid)
    clog.phase1("Recording 2.3s audio (STEREO)...", uuid=uuid)
    clog.latency(2418, "Recording", uuid=uuid)
    clog.phase1("Extracting client audio (left channel)...", uuid=uuid)
    clog.transcription("Oui, allô, j'écoute !", uuid=uuid, latency_ms=242)
    clog.success("AMD: HUMAN detected (confidence: 0.95)", uuid=uuid)
    clog.phase1_end(3063, uuid=uuid)

    # Test PHASE 2
    console.print("\n")
    clog.phase2_start("hello.wav", uuid=uuid)
    clog.phase2("Audio playback started", uuid=uuid)
    clog.phase2("VAD monitoring started", uuid=uuid)
    clog.warning("Barge-in detected!", uuid=uuid)
    clog.phase2_end(1547, uuid=uuid)

    # Test PHASE 3
    console.print("\n")
    clog.phase3_start(uuid=uuid)
    clog.phase3("Listening for client response...", uuid=uuid)
    clog.latency(350, "Silence detection", uuid=uuid)
    clog.transcription("Je suis intéressé par votre offre.", uuid=uuid, latency_ms=289)
    clog.phase3_end(2134, uuid=uuid)

    # Test latency table
    console.print("\n")
    clog.latency_table({
        "Recording": 2418,
        "Audio Extract": 65,
        "Volume Check": 10,
        "Transcription": 242,
        "AMD Detection": 5,
        "Total AMD": 3077
    }, uuid=uuid)

    # Test errors
    console.print("\n")
    clog.error("Recording file not found!", uuid=uuid)
    clog.warning("AMD: SILENCE detected by volume check", uuid=uuid)
    clog.info("Call cleanup completed", uuid=uuid)
    clog.debug("Volume check: -21.4dB", uuid=uuid)

    # Footer
    console.print("\n")
    footer = Panel(
        Text("✅ TESTS COMPLETED - DESIGN FUTURISTE ACTIVÉ!", style="bold green", justify="center"),
        box=box.HEAVY,
        border_style="bold bright_green",
        padding=(1, 2)
    )
    console.print(footer)
