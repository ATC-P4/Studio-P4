"""Per-track row widget displaying mute, 
group and instrument controls, synced to the 
backend state."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QCheckBox, QRadioButton, QComboBox
from PySide6.QtCore import Signal, Qt
import os

class TrackWidget(QWidget):
    # Define the signals this widget will emit to the MainWindow
    mute_toggled = Signal(int, bool) # track_id, is_muted
    armed = Signal(int)              # track_id
    instrument_changed = Signal(int, str) # track_id, program_id

    def __init__(self, track_id: int, name: str, available_instruments: dict):
        """Builds the track row with arm, mute, group, and instrument controls.

        Args:
            track_id (int): Numeric identifier used when emitting signals.
            name (str): Display name for the track.
            available_instruments (dict): Grouped instrument dictionary from get_available_instruments().
        """
        super().__init__()
        self.track_id = track_id
        self.available_instruments = available_instruments
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus) 

        layout = QHBoxLayout(self)
        
        self.arm_radio = QRadioButton()
        self.name_label = QLabel(name)
        self.mute_checkbox = QCheckBox("Mute")
        
        # --- NEW: Two-Tier Combo Boxes ---
        self.group_combo = QComboBox()
        self.instrument_combo = QComboBox()

        # Populate groups
        for group_name in self.available_instruments.keys():
            self.group_combo.addItem(group_name)

        layout.addWidget(self.arm_radio)
        layout.addWidget(self.name_label)
        layout.addWidget(self.mute_checkbox)
        layout.addWidget(self.group_combo)
        layout.addWidget(self.instrument_combo)

        # Prevent stealing MIDI focus
        self.arm_radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mute_checkbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.group_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.instrument_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.mute_checkbox.toggled.connect(lambda state: self.mute_toggled.emit(self.track_id, state))
        self.arm_radio.clicked.connect(lambda: self.armed.emit(self.track_id))
        self.instrument_combo.currentIndexChanged.connect(self._on_instrument_changed)

    def update_from_dto(self, track_dto: dict) -> None:
        """Syncs all widget controls to the values in the backend state dictionary, suppressing outgoing signals during the update.

        Args:
            track_dto (dict): Track state slice from LooperAPI.get_state_dto().
        """
        self.blockSignals(True)
        self.mute_checkbox.blockSignals(True)
        self.arm_radio.blockSignals(True)
        self.group_combo.blockSignals(True)
        self.instrument_combo.blockSignals(True)

        self.name_label.setText(track_dto["name"])
        self.mute_checkbox.setChecked(track_dto["is_muted"])
        self.arm_radio.setChecked(track_dto["is_armed"])

        # --- NEW: Sync Combo Boxes to the sf2_path ---
        current_path = track_dto.get("sf2_path", "")
        
        # 1. Figure out which group this path belongs to
        active_group = list(self.available_instruments.keys())[0]
        for group, sf2_list in self.available_instruments.items():
            if current_path in sf2_list:
                active_group = group
                break
                
        # 2. Set the Group Combo Box
        group_idx = self.group_combo.findText(active_group)
        if group_idx >= 0:
            self.group_combo.setCurrentIndex(group_idx)
            
        # 3. Populate the Instrument Combo Box with ONLY this group's files
        self.instrument_combo.clear()
        for sf2_path in self.available_instruments[active_group]:
            inst_name = os.path.basename(sf2_path).replace(".sf2", "").title().replace("_", " ")
            self.instrument_combo.addItem(inst_name, sf2_path)
            
        # 4. Set the active instrument
        inst_idx = self.instrument_combo.findData(current_path)
        if inst_idx >= 0:
            self.instrument_combo.setCurrentIndex(inst_idx)

        if track_dto["is_armed"]:
            self.setStyleSheet("background-color: #3a3a3a; border: 1px solid #55aaff;")
        else:
            self.setStyleSheet("")

        self.instrument_combo.blockSignals(False)
        self.group_combo.blockSignals(False)
        self.arm_radio.blockSignals(False)
        self.mute_checkbox.blockSignals(False)
        self.blockSignals(False)


    def _on_instrument_changed(self, index: int) -> None:
        """Emits instrument_changed with the sf2 path stored in the combo box item data.

        Args:
            index (int): Currently selected index in the instrument combo box.
        """
        sf2_path = self.instrument_combo.itemData(index)
        self.instrument_changed.emit(self.track_id, sf2_path)

    
