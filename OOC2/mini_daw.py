"""
Mini DAW - A simple DAW-inspired GUI built with PyQt6.

Architecture:
  - MiniDAW        : top-level controller / main window
  - TransportBar   : record + play/pause + BPM widget
  - BPMWidget      : display & edit the current BPM
  - TrackWidget    : represents one audio track

Run:
    pip install PyQt6
    python mini_daw.py
"""

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox,
    QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QTimer
from PyQt6.QtGui import QColor, QPalette, QKeySequence, QShortcut, QPainter
import keyboard, threading, time, sys, mido, fluidsynth
import classes2 as classes
import functions as f
import states as s
mido.set_backend("mido.backends.rtmidi")


# ──────────────────────────────────────────────
# Palette helpers
# ──────────────────────────────────────────────

DARK_BG       = "#1e1e2e"
PANEL_BG      = "#2a2a3e"
TRACK_BG      = "#252538"
ACCENT_RED    = "#e06c75"
ACCENT_GREEN  = "#98c379"
ACCENT_BLUE   = "#61afef"
TEXT_PRIMARY  = "#cdd6f4"
TEXT_DIM      = "#6c7086"
BORDER_COLOR  = "#313244"


def _apply_dark_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(DARK_BG))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base,            QColor(PANEL_BG))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(TRACK_BG))
    palette.setColor(QPalette.ColorRole.Text,            QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button,          QColor(PANEL_BG))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT_BLUE))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(DARK_BG))
    app.setPalette(palette)


# ──────────────────────────────────────────────
# DAWButton
# ──────────────────────────────────────────────
class DAWButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

# ──────────────────────────────────────────────
# BPMWidget + custom BPMSpinBox
# ──────────────────────────────────────────────

class BPMSpinBox(QSpinBox):
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            event.ignore()  # swallow the keypress, don't pass it to QSpinBox
            return
        super().keyPressEvent(event)  # let the spinbox handle the keystroke first
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.clearFocus()

class BPMWidget(QWidget):
    """Displays and edits the current BPM."""

    bpm_changed = pyqtSignal(int)   # emitted whenever the value changes

    def __init__(self, initial_bpm: int = 120, parent=None):
        super().__init__(parent)
        self._build_ui(initial_bpm)

    def _build_ui(self, initial_bpm: int) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("BPM")
        label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-weight: bold;")

        self._spinbox = BPMSpinBox()
        self._spinbox.setRange(20, 300)
        self._spinbox.setValue(initial_bpm)
        self._spinbox.setFixedWidth(72)
        self._spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spinbox.setStyleSheet(f"""
            QSpinBox {{
                background: {DARK_BG};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                padding: 4px;
                font-size: 16px;
                font-weight: bold;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 0;
                height: 0;
            }}
        """)

        self._spinbox.valueChanged.connect(self._on_value_changed)

        layout.addWidget(label)
        layout.addWidget(self._spinbox)

        # self._spinbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    # ── public API ──

    @property
    def bpm(self) -> int:
        return self._spinbox.value()

    @bpm.setter
    def bpm(self, value: int) -> None:
        self._spinbox.setValue(value)

    # ── slots ──

    def _on_value_changed(self, value: int) -> None:
        """Relay the spinbox signal. Connect real logic here later."""
        self.bpm_changed.emit(value)


# ──────────────────────────────────────────────
# TransportBar
# ──────────────────────────────────────────────

class TransportBar(QWidget):
    """Record button + BPM widget + Play/Pause button."""

    record_clicked    = pyqtSignal()
    play_pause_clicked = pyqtSignal()
    bpm_changed       = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_playing   = False
        self._is_recording = False
        self._build_ui()

    def _build_ui(self) -> None:
        self.setFixedHeight(64)
        self.setStyleSheet(f"""
            TransportBar {{
                background: {PANEL_BG};
                border-bottom: 1px solid {BORDER_COLOR};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # ── Record button ──
        self._record_btn = DAWButton("⏺  Record")
        self._record_btn.setFixedSize(110, 40)
        self._record_btn.setCheckable(True)
        self._record_btn.setStyleSheet(self._record_style(active=False))
        self._record_btn.clicked.connect(self._on_record_clicked)

        # ── BPM widget ──
        self._bpm_widget = BPMWidget()
        self._bpm_widget.bpm_changed.connect(self.bpm_changed)

        # ── Spacer ──
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # ── Play / Pause button ──
        self._play_btn = DAWButton("▶  Play")
        self._play_btn.setFixedSize(110, 40)
        self._play_btn.setStyleSheet(self._play_style(playing=False))
        self._play_btn.clicked.connect(self._on_play_pause_clicked)

        layout.addWidget(self._record_btn)
        layout.addWidget(self._bpm_widget)
        layout.addWidget(spacer)
        layout.addWidget(self._play_btn)

        # Accessibility

        # Start or end a recording
        self._record_btn.setAccessibleName("Enregistrer")
        self._record_btn.setAccessibleDescription("Démarre ou arrête l'enregistrement en appuyant sur R")
        
        # Set BPM
        self._bpm_widget.setAccessibleName("BPM")
        self._bpm_widget.setAccessibleDescription("Ajuster le BPM en appuyant sur B, entrer le nouveau BPM puis appuyer sur retour")

        # Play/pause
        self._play_btn.setAccessibleName("Play")
        self._play_btn.setAccessibleDescription("Play ou pause un track déjà enregistré en appuyant sur espace")

        # Mute
        self._play_btn.setAccessibleName("Mute")
        self._play_btn.setAccessibleDescription("Mute ou unmute ce track")

        # Solo
        self._play_btn.setAccessibleName("Solo")
        self._play_btn.setAccessibleDescription("Rend ce track solo ou bien permet aux autres tracks de jouer")

    # ── styles ──

    @staticmethod
    def _record_style(active: bool) -> str:
        bg = ACCENT_RED if active else PANEL_BG
        border = ACCENT_RED
        return f"""
            DAWButton {{
                background: {bg};
                color: {TEXT_PRIMARY};
                border: 1px solid {border};
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            DAWButton:hover {{ background: {ACCENT_RED}; }}
        """

    @staticmethod
    def _play_style(playing: bool) -> str:
        bg = ACCENT_GREEN if playing else PANEL_BG
        border = ACCENT_GREEN
        return f"""
            DAWButton {{
                background: {bg};
                color: {TEXT_PRIMARY};
                border: 1px solid {border};
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            DAWButton:hover {{ background: {ACCENT_GREEN}; }}
        """

    # ── slots ──

    def _on_record_clicked(self) -> None:
        """Toggle recording state. Wire real logic here later."""
        self._is_recording = self._record_btn.isChecked()
        self._record_btn.setStyleSheet(self._record_style(active=self._is_recording))
        self.record_clicked.emit()

    def _on_play_pause_clicked(self) -> None:
        """Toggle play/pause state. Wire real logic here later."""
        self._is_playing = not self._is_playing
        label = "⏸  Pause" if self._is_playing else "▶  Play"
        self._play_btn.setText(label)
        self._play_btn.setStyleSheet(self._play_style(playing=self._is_playing))
        self.play_pause_clicked.emit()

    # ── public API ──

    @property
    def bpm(self) -> int:
        return self._bpm_widget.bpm


# ──────────────────────────────────────────────
# TrackWidget
# ──────────────────────────────────────────────

class TrackWidget(QWidget):
    """
    Represents a single audio track.
    Currently a visual stub — connect buttons to real track logic later.
    """

    mute_clicked   = pyqtSignal(bool)   # True = muted
    solo_clicked   = pyqtSignal(bool)   # True = soloed

    def __init__(self, track_name: str = "Track 1", parent=None):
        super().__init__(parent)
        self._track_name = track_name
        self._build_ui()

    def _build_ui(self) -> None:
        self.setFixedHeight(80)
        self.setStyleSheet(f"""
            TrackWidget {{
                background: {TRACK_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # ── Track label ──
        name_label = QLabel(self._track_name)
        name_label.setFixedWidth(80)
        name_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold; font-size: 13px;")

        # ── Mute button ──
        self._mute_btn = DAWButton("M")
        self._mute_btn.setFixedSize(32, 32)
        self._mute_btn.setCheckable(True)
        self._mute_btn.setToolTip("Mute")
        self._mute_btn.setStyleSheet(self._small_btn_style(ACCENT_RED))
        self._mute_btn.toggled.connect(self.mute_clicked)

        # ── Solo button ──
        self._solo_btn = DAWButton("S")
        self._solo_btn.setFixedSize(32, 32)
        self._solo_btn.setCheckable(True)
        self._solo_btn.setToolTip("Solo")
        self._solo_btn.setStyleSheet(self._small_btn_style(ACCENT_BLUE))
        self._solo_btn.toggled.connect(self.solo_clicked)

        # ── Clip area (placeholder) ──
        self.clip_area = TrackClipArea(100, self)
        self.clip_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.clip_area.setStyleSheet(f"""
            QFrame {{
                background: {DARK_BG};
                border: 1px dashed {BORDER_COLOR};
                border-radius: 4px;
            }}
        """)
        clip_label = QLabel("No track")
        clip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clip_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        clip_layout = QHBoxLayout(self.clip_area)
        clip_layout.addWidget(clip_label)

        layout.addWidget(name_label)
        layout.addWidget(self._mute_btn)
        layout.addWidget(self._solo_btn)
        layout.addWidget(self.clip_area)

    @staticmethod
    def _small_btn_style(accent: str) -> str:
        return f"""
            DAWButton {{
                background: {PANEL_BG};
                color: {TEXT_DIM};
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }}
            DAWButton:checked {{
                background: {accent};
                color: {DARK_BG};
                border: 1px solid {accent};
            }}
            DAWButton:hover {{ border-color: {accent}; }}
        """
    
class TrackClipArea(QWidget):

    def __init__(self, track_d: float, parent: QWidget):
        super().__init__(parent)
        self._track_duration = track_d
        self._total_duration = 500
        self._playhead_position = 0


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # background
        painter.fillRect(self.rect(), QColor(DARK_BG))

        # filled region proportional to track length
        ratio = self._track_duration / self._total_duration
        filled_width = int(self.width() * ratio)
        clip_rect = QRect(0, 0, filled_width, self.height())
        painter.fillRect(clip_rect, QColor(ACCENT_BLUE))

        # playhead
        if self._total_duration > 0:
            ratio = self._playhead_position / self._total_duration
            x = int(self.width() * ratio)
            painter.setPen(QColor("white"))
            painter.drawLine(x, 0, x, self.height())

    def set_track_duration(self, seconds: float):
        self._track_duration = seconds
        self.update()  # triggers a repaint

    def set_playhead_position(self, seconds: float):
        self._playhead_position = seconds
        self.update()


# ──────────────────────────────────────────────
# MiniDAW  (main window / controller)
# ──────────────────────────────────────────────

class MiniDAW(QMainWindow):
    """
    Top-level controller.  All inter-widget wiring lives here.
    Subclass or extend this to attach real audio engine logic.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini DAW")
        self.setMinimumSize(800, 300)
        self._build_ui()
        self._connect_signals()
        # self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setStyleSheet(f"background: {DARK_BG};")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Transport bar (top)
        self._transport = TransportBar()
        root_layout.addWidget(self._transport)

        # Track area
        track_area = QWidget()
        track_area.setStyleSheet(f"background: {DARK_BG};")
        track_layout = QVBoxLayout(track_area)
        track_layout.setContentsMargins(16, 16, 16, 16)
        track_layout.setSpacing(8)

        self._track = TrackWidget("Track 1")
        self._playhead_pos = 0
        self._clip_area = self._track.clip_area
        track_layout.addWidget(self._track)
        track_layout.addStretch()

        self._playback_timer = QTimer()
        self._playback_timer.setInterval(2)  # update every 2ms
        self._playback_timer.timeout.connect(self._tick_playhead)

        root_layout.addWidget(track_area)

        # Status bar
        self.statusBar().setStyleSheet(
            f"background: {PANEL_BG}; color: {TEXT_DIM}; font-size: 11px;"
        )
        self.statusBar().showMessage("Ready  |  BPM: 120")

        # All keyboard shortcuts
        QShortcut(QKeySequence("r"), self).activated.connect(self._transport._record_btn.click)
        QShortcut(QKeySequence("space"), self).activated.connect(self._transport._on_play_pause_clicked)
        QShortcut(QKeySequence("b"), self).activated.connect(lambda: 
            (self._transport._bpm_widget._spinbox.setFocus(), 
            self._transport._bpm_widget._spinbox.selectAll()))
        QShortcut(QKeySequence("m"), self).activated.connect(self._track._mute_btn.click)
        QShortcut(QKeySequence("s"), self).activated.connect(self._track._solo_btn.click)



    def _connect_signals(self) -> None:
        self._transport.record_clicked.connect(self._on_record)
        self._transport.play_pause_clicked.connect(self._on_play_pause)
        self._transport.bpm_changed.connect(self._on_bpm_changed)
        self._track.mute_clicked.connect(self._on_mute)
        self._track.solo_clicked.connect(self._on_solo)

    # ── stub handlers — replace with real engine calls ──

    def _on_record(self) -> None:
        """Called when the Record button is toggled."""
        # TODO: start / stop audio recording
        # self._playback_timer.timeout.connect(self._tick_playhead)
        if s.record_flag is True:
            print("Stopping recording...")
            s.record_flag = False
        else:
            print("Starting recording...")
            s.record_flag = True
            record_thread = threading.Thread(target=f.record, daemon=True)
            record_thread.start()
        self.statusBar().showMessage("Recording toggled  (stub)")

    def _on_play_pause(self) -> None:
        """Called when Play/Pause is toggled."""

        # TODO: start / stop audio playback
        if self._playback_timer.isActive():
            self._playback_timer.stop()
        else:
            self._playback_timer.start()

        self.statusBar().showMessage("Play/Pause toggled  (stub)")

    def _on_bpm_changed(self, bpm: int) -> None:
        """Called whenever the BPM spinbox value changes."""
        # TODO: notify audio engine of new tempo
        self.statusBar().showMessage(f"BPM changed → {bpm}  (stub)")

    def _on_mute(self, muted: bool) -> None:
        state = "muted" if muted else "unmuted"
        self.statusBar().showMessage(f"Track 1 {state}  (stub)")

    def _on_solo(self, soloed: bool) -> None:
        state = "soloed" if soloed else "un-soloed"
        self.statusBar().showMessage(f"Track 1 {state}  (stub)")

    def _tick_playhead(self):
        self._playhead_pos += 0.005  # advance by 2ms
        self._clip_area.set_playhead_position(self._playhead_pos)


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _apply_dark_palette(app)

    # Create a project and a track for testing
    s.m_p = f.create_project("My First Project")
    s.s_t = f.create_track("Piano Track", s.m_p)
    s.s_t.length = 4
    s.s_t.midi_file_name = "piano_track.mid"

    #initiating the time tracking
    record_start_time = time.time()
    s.last_msg_time = record_start_time
    s.midi_track = mido.MidiTrack()
    mid = mido.MidiFile(ticks_per_beat=s.m_p.tpb)
    mid.tracks.append(s.midi_track)

    # Port discovery
    port_thread = threading.Thread(target=f.port_discovery, daemon=True)
    port_thread.start()

    #starts the keyboard listener in a separate thread 
    # listener_thread = threading.Thread(target=f.keyboard_listener, daemon=True)
    # listener_thread.start()

    # keyboard.wait('esc')  # Main thread waits for 'esc' to exit the program
    # s.terminate_flag = True
    # port_thread.join()
    # listener_thread.join()
    # print("Program terminated.")    

    window = MiniDAW()
    window.show()
    window.setFocus()    
    sys.exit(app.exec())






if __name__ == "__main__":
    main()