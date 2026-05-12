import sys
import os

# Force Mido to use rtmidi
os.environ["MIDO_BACKEND"] = "mido.backends.rtmidi"
import mido

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QGridLayout, QPushButton, QLabel, QComboBox, QSlider)
from PySide6.QtCore import Qt

class VirtualMidiController(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Virtual MIDI Tester (Looper API)")
        self.resize(550, 350) 
        
        self.outport = None
        self.init_ui()
        self.populate_midi_ports()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 1. Port Selection ---
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Output Port:"))
        self.port_dropdown = QComboBox()
        self.port_dropdown.currentIndexChanged.connect(self.change_port)
        port_layout.addWidget(self.port_dropdown)
        main_layout.addLayout(port_layout)

        # --- 2. Action Buttons (Transport & Joystick) ---
        grid = QGridLayout()
        
        # Transport
        btn_play = QPushButton("Play (CC 118)")
        btn_play.clicked.connect(lambda: self.send_cc(118, 127))
        grid.addWidget(btn_play, 0, 0)

        btn_rec = QPushButton("Record (CC 119)")
        btn_rec.clicked.connect(lambda: self.send_cc(119, 127))
        grid.addWidget(btn_rec, 0, 1)

        btn_metro = QPushButton("Metro (CC 117)")
        btn_metro.clicked.connect(lambda: self.send_cc(117, 127))
        grid.addWidget(btn_metro, 0, 2)

        # NOUVEAU : Bouton Fix Audio
        btn_audio = QPushButton("Fix Audio (CC 114)")
        btn_audio.clicked.connect(lambda: self.send_cc(114, 127))
        grid.addWidget(btn_audio, 0, 3)

        # Joystick (Threshold crossing simulation)
        btn_up = QPushButton("Nav UP (CC 2)")
        btn_up.pressed.connect(lambda: self.send_cc(2, 127))
        btn_up.released.connect(lambda: self.send_cc(2, 0)) # Reset below threshold
        grid.addWidget(btn_up, 1, 0, 1, 4)

        btn_left = QPushButton("Nav LEFT (CC 12)")
        btn_left.pressed.connect(lambda: self.send_cc(12, 127))
        btn_left.released.connect(lambda: self.send_cc(12, 0))
        grid.addWidget(btn_left, 2, 0, 1, 2)

        btn_right = QPushButton("Nav RIGHT (CC 13)")
        btn_right.pressed.connect(lambda: self.send_cc(13, 127))
        btn_right.released.connect(lambda: self.send_cc(13, 0))
        grid.addWidget(btn_right, 2, 2, 1, 2)

        btn_down = QPushButton("Nav DOWN (CC 3)")
        btn_down.pressed.connect(lambda: self.send_cc(3, 127))
        btn_down.released.connect(lambda: self.send_cc(3, 0))
        grid.addWidget(btn_down, 3, 0, 1, 4)

        main_layout.addLayout(grid)

        # --- 3. Continuous Controller (Volume) ---
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Volume Knob (CC 1):"))
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 127)
        self.vol_slider.setValue(100)
        self.vol_slider.valueChanged.connect(lambda val: self.send_cc(1, val))
        vol_layout.addWidget(self.vol_slider)
        main_layout.addLayout(vol_layout)

        # --- 4. Virtual Piano (C4 to G4) ---
        main_layout.addWidget(QLabel("Piano (Channel 0):"))
        piano_layout = QHBoxLayout()
        
        notes = {"C4": 60, "D4": 62, "E4": 64, "F4": 65, "G4": 67}
        for name, midi_note in notes.items():
            btn = QPushButton(name)
            btn.pressed.connect(lambda n=midi_note: self.send_note_on(n))
            btn.released.connect(lambda n=midi_note: self.send_note_off(n))
            piano_layout.addWidget(btn)
            
        main_layout.addLayout(piano_layout)

    def populate_midi_ports(self):
        """Finds available output ports and populates the dropdown."""
        self.port_dropdown.blockSignals(True)
        self.port_dropdown.clear()
        self.port_dropdown.addItem("Select a port...")
        
        ports = mido.get_output_names()
        for port in ports:
            self.port_dropdown.addItem(port)
            
        self.port_dropdown.blockSignals(False)

    def change_port(self):
        """Handles switching the active MIDI output port."""
        port_name = self.port_dropdown.currentText()
        if port_name == "Select a port...":
            return

        if self.outport:
            self.outport.close()

        try:
            self.outport = mido.open_output(port_name)
            print(f"[TESTER] Connected to {port_name}")
        except Exception as e:
            print(f"[TESTER] Error opening port: {e}")

    # --- MIDI SEND FUNCTIONS ---
    def send_cc(self, control: int, value: int, channel: int = 0):
        if not self.outport: return
        msg = mido.Message('control_change', channel=channel, control=control, value=value)
        self.outport.send(msg)
        print(f"Sent: {msg}")

    def send_note_on(self, note: int, velocity: int = 100, channel: int = 0):
        if not self.outport: return
        msg = mido.Message('note_on', channel=channel, note=note, velocity=velocity)
        self.outport.send(msg)
        print(f"Sent: {msg}")

    def send_note_off(self, note: int, channel: int = 0):
        if not self.outport: return
        msg = mido.Message('note_off', channel=channel, note=note, velocity=0)
        self.outport.send(msg)
        print(f"Sent: {msg}")

    def closeEvent(self, event):
        """Ensure the MIDI port is freed when the window closes."""
        if self.outport:
            self.outport.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VirtualMidiController()
    window.show()
    sys.exit(app.exec())