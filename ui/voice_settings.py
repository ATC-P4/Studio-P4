from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout
# ... continued (L-Z)
from PySide6.QtWidgets import QLabel, QPushButton, QSlider
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent

class VoiceConfigDialog(QDialog):
    # Non-linear rate steps: 0.2 to 1.0 in 0.1 steps, 1.0 to 3.0 in 0.25 steps
    RATE_STEPS = [round(x * 0.1, 1) for x in range(5, 11)] + [round(x * 0.25, 2) + 1 for x in range(1, 9)]

    # {"enabled": bool, "rate": float, "volume": float}
    voice_settings_changed = Signal(dict)
    voice_settings_opened = Signal()
    # True if settings confirmed else False
    voice_settings_close = Signal(bool)
    # For "enabled" (bool), float < 0 -> False, float >= 0 -> True
    voice_setting_selected = Signal(str, float)

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