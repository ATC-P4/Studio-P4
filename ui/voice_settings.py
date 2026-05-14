from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout
# ... continued (L-Z)
from PySide6.QtWidgets import QLabel, QPushButton, QSlider
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent

# class-level, matches _focusable order
SETTING_NAMES = ["enabled", "rate", "volume"]  

# Non-linear rate steps: 0.5 to 1.0 in 0.1 steps, 1.0 to 3.0 in 0.25 steps
RATE_STEPS = [round(x * 0.1, 1) for x in range(5, 11)] + [round(x * 0.25, 2) + 1 for x in range(1, 9)]

class VoiceConfigDialog(QDialog):


    # For "enabled" (bool), float < 0 -> False, float >= 0 -> True    
    voice_setting_value = Signal(str, float)

    def __init__(self, current: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration de la voix")
        self.setMinimumWidth(350)
        
        layout = QFormLayout(self)

        # --- Enable/disable toggle (reuses QPushButton as a toggle) ---
        def e_button(self: VoiceConfigDialog) -> None:
            self._update_enable_label()
            new_val = 1.0 if self.enable_btn.isChecked() else -1.0
            self.voice_setting_value.emit(SETTING_NAMES[0], new_val)

        self.enable_btn = QPushButton()
        self.enable_btn.setCheckable(True)
        self.enable_btn.setChecked(current.get("enabled", True))
        self._update_enable_label()
        self.enable_btn.toggled.connect(lambda _: e_button(self))
        layout.addRow("Voix activée :", self.enable_btn)

        # --- Rate slider ---
        def r_slider(self: VoiceConfigDialog, v: int) -> None:
            new_val = RATE_STEPS[v]
            self.rate_label.setText(f"{new_val:.2f}")
            self.voice_setting_value.emit(SETTING_NAMES[1], new_val)

        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setMinimum(0)
        self.rate_slider.setMaximum(len(RATE_STEPS) - 1)
        rate_idx = self._rate_to_index(current.get("rate", 1.0))
        self.rate_slider.setValue(rate_idx)
        self.rate_label = QLabel(f"{RATE_STEPS[rate_idx]:.2f}")
        self.rate_slider.valueChanged.connect(lambda v: r_slider(self, v))
        rate_row = QHBoxLayout()
        rate_row.addWidget(self.rate_slider)
        rate_row.addWidget(self.rate_label)
        layout.addRow("Vitesse :", rate_row)

        # --- Volume slider ---
        def v_slider(self: VoiceConfigDialog, v: int) -> None:
            new_val = v / 100
            self.vol_label.setText(f"{new_val:.2f}")
            self.voice_setting_value.emit(SETTING_NAMES[2], new_val)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setMinimum(0)
        self.vol_slider.setMaximum(100)
        self.vol_slider.setValue(int(current.get("volume", 0.5) * 100))
        self.vol_label = QLabel(f"{self.vol_slider.value() / 100:.2f}")
        self.vol_slider.valueChanged.connect(lambda v: v_slider(self, v))
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
        self._focusable: list[QPushButton | QSlider] = [self.enable_btn, self.rate_slider, self.vol_slider]
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
        closest = min(range(len(RATE_STEPS)), key=lambda i: abs(RATE_STEPS[i] - rate))
        return closest

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key.Key_Up:
            self._focus_idx = (self._focus_idx - 1) % len(self._focusable)
            self._focusable[self._focus_idx].setFocus()
            item = SETTING_NAMES[self._focus_idx]
            value = self._current_value()
            self.voice_setting_value.emit(item, value)
            self._update_focus_highlight()

        elif key == Qt.Key.Key_Down:
            self._focus_idx = (self._focus_idx + 1) % len(self._focusable)
            self._focusable[self._focus_idx].setFocus()
            item = SETTING_NAMES[self._focus_idx]
            value = self._current_value()
            self.voice_setting_value.emit(item, value)
            self._update_focus_highlight()

        elif key == Qt.Key.Key_Left:
            w = self._focusable[self._focus_idx]
            if isinstance(w, QSlider):
                w.setValue(max(w.minimum(), w.value() - 1))
            elif isinstance(w, QPushButton) and w.isCheckable():
                w.setChecked(not w.isChecked())

        elif key == Qt.Key.Key_Right:
            w = self._focusable[self._focus_idx]
            if isinstance(w, QSlider):
                w.setValue(min(w.maximum(), w.value() + 1))
            elif isinstance(w, QPushButton) and w.isCheckable():
                w.setChecked(not w.isChecked())

        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()

        elif key == Qt.Key.Key_Escape:
            self.reject()

        else:
            super().keyPressEvent(event)

    def get_values(self) -> dict:
        return {
            "enabled": self.enable_btn.isChecked(),
            "rate": RATE_STEPS[self.rate_slider.value()],
            "volume": self.vol_slider.value() / 100.0,
        }
    
    def _update_focus_highlight(self):
        for i, w in enumerate(self._focusable):
            if i == self._focus_idx:
                w.setStyleSheet("border: 2px solid palette(highlight);")
            else:
                w.setStyleSheet("")

    def _current_value(self) -> float:
        w = self._focusable[self._focus_idx]
        if w is self.rate_slider:
            return RATE_STEPS[self.rate_slider.value()]
        elif w is self.vol_slider:
            return self.vol_slider.value() / 100.0
        elif w is self.enable_btn:
            if self.enable_btn.isChecked():
                return 1.0
            else:
                return -1.0
        # Shouldn't ever reach this
        return 0.0