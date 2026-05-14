# QtWidgets A-K imports
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout
# ... continued (L-Z)
from PySide6.QtWidgets import QLabel, QMainWindow, QPushButton, QSlider, QVBoxLayout, QWidget
from PySide6.QtCore import Signal, Qt
from ui.track_widget import TrackWidget
from PySide6.QtGui import QKeyEvent

class MainWindow(QMainWindow):
    # These signals perfectly match the connections we set up in main.py
    record_requested = Signal()
    play_requested = Signal()
    save_requested = Signal()
    metronome_toggled = Signal(bool)
    track_muted = Signal(int, bool)
    track_armed = Signal(int)
    instrument_changed = Signal(int, str)
    add_track_requested = Signal()
    backend_state_changed = Signal(dict)
    # {"enabled": bool, "rate": float, "volume": float}
    voice_settings_changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Live Looper")
        self.setMinimumSize(450, 300)

        # signal from the backhand that something changed
        self.backend_state_changed.connect(self.update_ui)

        # Set up the main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        # --- Top Control Bar ---
        control_layout = QHBoxLayout()
        
        self.record_btn = QPushButton("🔴 Record")
        self.play_btn = QPushButton("▶ Play")
        self.metro_checkbox = QCheckBox("Metronome")
        self.status_label = QLabel("STOPPED | 120 BPM")
        self.add_track = QPushButton("➕ Add Track") 
        self.save_btn = QPushButton("💾 Save")              # Save project
        self.voice_btn = QPushButton("🎙 Voice")            # Change voice settings

        control_layout.addWidget(self.record_btn)
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.metro_checkbox)
        control_layout.addWidget(self.status_label)
        control_layout.addWidget(self.add_track)
        control_layout.addWidget(self.save_btn)
        control_layout.addWidget(self.voice_btn)
        
        self.main_layout.addLayout(control_layout)

        # --- Tracks Container ---
        self.tracks_layout = QVBoxLayout()
        self.main_layout.addLayout(self.tracks_layout)
        
        self.track_widgets = {} # Dictionary tracking {track_id: TrackWidget_Instance}

        # Add the button to your layout (e.g., self.layout.addWidget(self.reset_map_btn))

        # Wire top bar clicks to our MainWindow signals
        self.record_btn.clicked.connect(self.record_requested.emit)
        self.play_btn.clicked.connect(self.play_requested.emit)
        self.metro_checkbox.toggled.connect(self.metronome_toggled.emit)
        self.add_track.clicked.connect(self.add_track_requested.emit)
        self.save_btn.clicked.connect(self.save_requested.emit)
        self.voice_btn.clicked.connect(self._open_voice_config)

    def update_ui(self, dto: dict):
        """Consumes the 'dumb' dictionary from the core API and redraws the screen."""
        
        # 1. Update Global Status
        state = dto["current_state"]
        self.status_label.setText(f"{state} | {dto['bpm']} BPM")
        
        # Update colors based on transport state
        if state == "RECORDING":
            self.record_btn.setStyleSheet("background-color: red; color: white;")
            self.play_btn.setStyleSheet("")
        elif state == "PLAYING":
            self.play_btn.setStyleSheet("background-color: green; color: white;")
            self.record_btn.setStyleSheet("")
        elif state == "COUNT_IN":
            self.record_btn.setStyleSheet("background-color: orange; color: black;")
            self.play_btn.setStyleSheet("")
        else:
            self.record_btn.setStyleSheet("")
            self.play_btn.setStyleSheet("")

        # Safely update Metronome
        self.metro_checkbox.blockSignals(True)
        self.metro_checkbox.setChecked(dto["metronome_on"])
        self.metro_checkbox.blockSignals(False)

        available_instruments = dto.get("available_instruments", [])

        # 2. Update Tracks dynamically
        for track_dto in dto["tracks"]:
            t_id = track_dto["id"]
            
            # If a new track was added to the backend, create a widget for it
            if t_id not in self.track_widgets:
                tw = TrackWidget(t_id, track_dto["name"], available_instruments)
                self.tracks_layout.addWidget(tw)
                self.track_widgets[t_id] = tw
                
                # Route the child widget's signals up through the MainWindow
                tw.mute_toggled.connect(self.track_muted.emit)
                tw.armed.connect(self.track_armed.emit)
                tw.instrument_changed.connect(self.instrument_changed.emit)

            # Push the data down to the specific track widget
            self.track_widgets[t_id].update_from_dto(track_dto)

    def handle_midi_navigation(self, command: str):
        """Routes abstract string commands from your hardware knobs into Qt Focus."""
        if command in ["NAV_DOWN", "NAV_RIGHT"]:
            self.focusNextChild()
        elif command in ["NAV_UP", "NAV_LEFT"]:
            self.focusPreviousChild()
        elif command == "ACTION_ENTER":
            # If the user presses an "Enter" hardware button while a track is focused, Arm it.
            focused_widget = QApplication.focusWidget()
            if isinstance(focused_widget, TrackWidget):
                self.track_armed.emit(focused_widget.track_id)

    def _open_voice_config(self):
        current = getattr(self, "_voice_settings", {"enabled": True, "rate": 1.0, "volume": 0.5})
        dialog = VoiceConfigDialog(current, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._voice_settings = dialog.get_values()
            self.voice_settings_changed.emit(self._voice_settings)


class VoiceConfigDialog(QDialog):
    # Non-linear rate steps: 0.2 to 1.0 in 0.1 steps, 1.0 to 3.0 in 0.25 steps
    RATE_STEPS = [round(x * 0.1, 1) for x in range(5, 11)] + [round(x * 0.25, 2) + 1 for x in range(1, 9)] # [1.25, 1.5, 1.75, 2.0, ]

    def __init__(self, current: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration de la voix")
        self.setMinimumWidth(350)

        layout = QFormLayout(self)

        # --- Enable/disable toggle (reuses QPushButton as a toggle) ---
        self.enable_btn = QPushButton()
        self.enable_btn.setCheckable(True)
        self.enable_btn.setChecked(current.get("enabled", True))
        self._update_enable_label()
        self.enable_btn.toggled.connect(lambda _: self._update_enable_label())
        layout.addRow("Voix activée :", self.enable_btn)

        # --- Rate slider ---
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setMinimum(0)
        self.rate_slider.setMaximum(len(self.RATE_STEPS) - 1)
        rate_idx = self._rate_to_index(current.get("rate", 1.0))
        self.rate_slider.setValue(rate_idx)
        self.rate_label = QLabel(f"{self.RATE_STEPS[rate_idx]:.2f}")
        self.rate_slider.valueChanged.connect(
            lambda v: self.rate_label.setText(f"{self.RATE_STEPS[v]:.2f}")
        )
        rate_row = QHBoxLayout()
        rate_row.addWidget(self.rate_slider)
        rate_row.addWidget(self.rate_label)
        layout.addRow("Vitesse :", rate_row)

        # --- Volume slider ---
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setMinimum(0)
        self.vol_slider.setMaximum(100)
        self.vol_slider.setValue(int(current.get("volume", 0.5) * 100))
        self.vol_label = QLabel(f"{self.vol_slider.value() / 100:.2f}")
        self.vol_slider.valueChanged.connect(
            lambda v: self.vol_label.setText(f"{v / 100:.2f}")
        )
        vol_row = QHBoxLayout()
        vol_row.addWidget(self.vol_slider)
        vol_row.addWidget(self.vol_label)
        layout.addRow("Volume :", vol_row)

        # --- OK / Cancel ---
        buttons = QDialogButtonBox(standardButtons=QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        # Focus order for up/down navigation
        self._focusable = [self.enable_btn, self.rate_slider, self.vol_slider]
        self._focus_idx = 0
        self._focusable[0].setFocus()
        self._update_focus_highlight()

        for w in self._focusable:
            w.installEventFilter(self)


    def eventFilter(self, watched, event):
        if event.type() == event.Type.KeyPress:
            self.keyPressEvent(event)
            return True  # Consume the event so the widget doesn't also handle it
        return super().eventFilter(watched, event)

    def _update_enable_label(self):
        self.enable_btn.setText("Activée" if self.enable_btn.isChecked() else "Désactivée")

    def _rate_to_index(self, rate: float) -> int:
        closest = min(range(len(self.RATE_STEPS)), key=lambda i: abs(self.RATE_STEPS[i] - rate))
        return closest

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key.Key_Up:
            self._focus_idx = (self._focus_idx - 1) % len(self._focusable)
            self._focusable[self._focus_idx].setFocus()
            self._update_focus_highlight()

        elif key == Qt.Key.Key_Down:
            self._focus_idx = (self._focus_idx + 1) % len(self._focusable)
            self._focusable[self._focus_idx].setFocus()
            self._update_focus_highlight()

        elif key == Qt.Key.Key_Left:
            w = self._focusable[self._focus_idx]
            if isinstance(w, QSlider):
                w.setValue(max(w.minimum(), w.value() - 1))
            elif isinstance(w, QPushButton) and w.isCheckable():
                w.setChecked(False)

        elif key == Qt.Key.Key_Right:
            w = self._focusable[self._focus_idx]
            if isinstance(w, QSlider):
                w.setValue(min(w.maximum(), w.value() + 1))
            elif isinstance(w, QPushButton) and w.isCheckable():
                w.setChecked(True)

        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()

        elif key == Qt.Key.Key_Escape:
            self.reject()

        else:
            super().keyPressEvent(event)

    def get_values(self) -> dict:
        return {
            "enabled": self.enable_btn.isChecked(),
            "rate": self.RATE_STEPS[self.rate_slider.value()],
            "volume": self.vol_slider.value() / 100.0,
        }
    
    def _update_focus_highlight(self):
        for i, w in enumerate(self._focusable):
            if i == self._focus_idx:
                w.setStyleSheet("border: 2px solid palette(highlight);")
            else:
                w.setStyleSheet("")