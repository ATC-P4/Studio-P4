from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox, QApplication
from PySide6.QtCore import Signal, Qt
from ui.track_widget import TrackWidget

class MainWindow(QMainWindow):
    # These signals perfectly match the connections we set up in main.py
    record_requested = Signal()
    play_requested = Signal()
    metronome_toggled = Signal(bool)
    track_muted = Signal(int, bool)
    track_armed = Signal(int)
    instrument_changed = Signal(int, str)
    add_track_requested = Signal()
    backend_state_changed = Signal(dict)

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

        control_layout.addWidget(self.record_btn)
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.metro_checkbox)
        control_layout.addWidget(self.status_label)
        control_layout.addWidget(self.add_track)
        
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