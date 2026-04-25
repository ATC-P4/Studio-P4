#100% vibe coded

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QCheckBox, QRadioButton, QComboBox
from PySide6.QtCore import Signal, Qt

class TrackWidget(QWidget):
    # Define the signals this widget will emit to the MainWindow
    mute_toggled = Signal(int, bool) # track_id, is_muted
    armed = Signal(int)              # track_id
    instrument_changed = Signal(int, str) # track_id, program_id

    def __init__(self, track_id: int, name: str, available_instruments: list):
        super().__init__()
        self.track_id = track_id
        self.available_instruments = available_instruments

        # Allow the main track container to be selected via MIDI navigation
        self.setFocusPolicy(Qt.StrongFocus) 

        layout = QHBoxLayout(self)
        
        # Create UI Elements
        self.arm_radio = QRadioButton()
        self.name_label = QLabel(name)
        self.mute_checkbox = QCheckBox("Mute")
        self.instrument_combo = QComboBox()

        # take the list of names form the sf2 file in the sf2 folder, and add them to the combo box as instruments option
         
        list_of_sf2 = available_instruments
        instruments = {}
        for sf2_path in list_of_sf2:
            # Extract instrument name from sf2 path (simplified - you might want to use a more robust method)
            inst_name = sf2_path.split("/")[-1].split(".")[0].title()
            instruments[sf2_path] = inst_name

        for sf2_path, inst_name in instruments.items():
            self.instrument_combo.addItem(inst_name, sf2_path)

        # Add to layout
        layout.addWidget(self.arm_radio)
        layout.addWidget(self.name_label)
        layout.addWidget(self.mute_checkbox)
        layout.addWidget(self.instrument_combo)

        # CRITICAL UX FIX: Prevent child widgets from stealing MIDI navigation focus
        self.arm_radio.setFocusPolicy(Qt.NoFocus)
        self.mute_checkbox.setFocusPolicy(Qt.NoFocus)
        self.instrument_combo.setFocusPolicy(Qt.NoFocus)

        # Wire UI clicks to our custom signals
        self.mute_checkbox.toggled.connect(lambda state: self.mute_toggled.emit(self.track_id, state))
        self.arm_radio.clicked.connect(lambda: self.armed.emit(self.track_id))
        self.instrument_combo.currentIndexChanged.connect(self._on_instrument_changed)

    def _on_instrument_changed(self, index):
        sf2_path = self.instrument_combo.itemData(index)
        self.instrument_changed.emit(self.track_id, sf2_path)

    

    def update_from_dto(self, track_dto: dict):
        """Called by the MainWindow when new data arrives from the backend."""
        # 1. TEMPORARILY DEAFEN THE WIDGET to prevent infinite loops
        self.blockSignals(True)
        self.mute_checkbox.blockSignals(True)
        self.arm_radio.blockSignals(True)
        self.instrument_combo.blockSignals(True)

        # 2. UPDATE VALUES
        self.name_label.setText(track_dto["name"])
        self.mute_checkbox.setChecked(track_dto["is_muted"])
        self.arm_radio.setChecked(track_dto["is_armed"])

        #update the instrument combo box to match the program_id of the track dto
        

        # Match the combo box to the backend program ID
        idx = self.instrument_combo.findData(track_dto["program_id"])
        if idx >= 0:
            self.instrument_combo.setCurrentIndex(idx)

        # 3. VISUAL FEEDBACK
        if track_dto["is_armed"]:
            # Highlight armed tracks so the user knows where the keyboard is routed
            self.setStyleSheet("background-color: #3a3a3a; border: 1px solid #55aaff;")
        else:
            self.setStyleSheet("")

        # 4. RESTORE HEARING
        self.instrument_combo.blockSignals(False)
        self.arm_radio.blockSignals(False)
        self.mute_checkbox.blockSignals(False)
        self.blockSignals(False)