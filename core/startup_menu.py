import os
import sys
import mido
import time
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.models import Project
from core.midi_io import JoystickMapper, MidiIO
from core.utils import get_resource_path
from core.voice import VoiceType

class StartupMenu(QDialog):
    """A visual, MIDI-controlled startup menu."""
    
    # Custom Qt Signals to safely update the UI from the MIDI background thread
    selection_changed = Signal(int)
    project_confirmed = Signal()

    def __init__(self, voice_service):
        super().__init__()
        self.voice = voice_service
        self.mapping = MidiIO.DEFAULT_MIDI_MAPPING
        self.joystick = JoystickMapper()
        
        self.projects = [None] + self._get_saved_projects()
        self.current_idx = 0
        self.selected_folder_path = None
        
        # Tracks if the user clicked the 'X' or 'Escape' to close the window
        self._aborted = True 

        self._setup_ui()

        # Wire up MIDI signals with EXPLICIT QueuedConnections
        self.selection_changed.connect(self._update_ui_selection, Qt.QueuedConnection)
        self.project_confirmed.connect(self.accept, Qt.QueuedConnection)
        
    def _get_saved_projects(self) -> list:
        base_dir = os.path.abspath("./Saves")
        os.makedirs(base_dir, exist_ok=True)
        
        dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) 
                if os.path.isdir(os.path.join(base_dir, d))]
        dirs.sort(key=os.path.getmtime, reverse=True)
        return dirs

    def _setup_ui(self):
        self.setWindowTitle("Studio P4 - Démarrage")
        self.setFixedSize(400, 350)
        layout = QVBoxLayout(self)

        title = QLabel("Sélectionnez un projet")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Arial", 11))
        
        self.list_widget.addItem("✨ Nouveau Projet ✨")
        for p in self.projects[1:]:
            clean_name = os.path.basename(p).replace("_", " ")
            self.list_widget.addItem(f"📁 {clean_name}")
            
        self.list_widget.setCurrentRow(0) 
        layout.addWidget(self.list_widget)

        # Sync mouse clicks to the voice announcement
        self.list_widget.currentRowChanged.connect(self._on_mouse_selection)
        # Double click confirms instantly
        self.list_widget.itemDoubleClicked.connect(self.accept)

        # Fallback UI Button (prevents soft-locks if MIDI is unplugged)
        self.btn_confirm = QPushButton("Confirmer (Joystick Droite)")
        self.btn_confirm.setMinimumHeight(40)
        self.btn_confirm.clicked.connect(self.accept)
        layout.addWidget(self.btn_confirm)

    def _midi_callback(self, msg) -> None:
        """
        Runs on a background thread triggered by Mido. 
        DO NOT interact with Qt UI elements directly here!
        """
        if msg.type == 'control_change':
            raw_action = self.mapping.get(msg.control)
            
            if raw_action in ["NAV_DOWN", "NAV_UP", "NAV_RIGHT"]:
                action = self.joystick.process(msg, raw_action)
                
                # CRITICAL FIX: Read the thread-safe Python integer, 
                # NEVER call self.list_widget.currentRow() from this thread!
                safe_current_idx = self.current_idx
                
                if action == "NAV_DOWN":
                    if safe_current_idx < len(self.projects) - 1:
                        self.selection_changed.emit(safe_current_idx + 1)
                        
                elif action == "NAV_UP":
                    if safe_current_idx > 0:
                        self.selection_changed.emit(safe_current_idx - 1)
                        
                elif action == "NAV_RIGHT":
                    self.project_confirmed.emit()

    def _update_ui_selection(self, idx: int) -> None:
        """Triggered by MIDI. Moves the visual highlight."""
        self.list_widget.setCurrentRow(idx)

    def _on_mouse_selection(self, idx: int) -> None:
        """Triggered by Mouse/Keyboard or MIDI updating the list."""
        self.current_idx = idx
        self._announce()

    def accept(self):
        """
        OVERRIDE: This triggers whether the user hits Enter, clicks Confirmer, 
        double-clicks, or uses NAV_RIGHT. It is the single source of truth.
        """
        self.current_idx = self.list_widget.currentRow()
        self.selected_folder_path = self.projects[self.current_idx]
        self._aborted = False

        # Kill the MIDI callback IMMEDIATELY to prevent deadlocks during teardown
        if hasattr(self, 'inport') and self.inport:
            self.inport.callback = None 
        
        self.voice.speak(VoiceType.METR_INFO, "Chargement du projet.")
        super().accept() # Call the parent QDialog close routine

    def _announce(self) -> None:
        if self.current_idx == 0:
            self.voice.speak(VoiceType.METR_INFO, "Nouveau Projet")
        else:
            folder_name = os.path.basename(self.projects[self.current_idx])
            clean_name = folder_name.replace("_", " ")
            self.voice.speak(VoiceType.METR_INFO, f" {clean_name}")

    def run(self, port_name: str | None = None) -> str | None:
        time.sleep(0.5) # Small delay to ensure the UI is fully rendered before MIDI input starts
        self.voice.speak(VoiceType.METR_INFO, "Menu de démarrage. Nouveau projet.")
        
        inport = None
        try:
            inport = mido.open_input(port_name, callback=self._midi_callback)
        except Exception as e:
            print(f"[STARTUP WARNING] Could not open MIDI port. Use mouse/keyboard. Error: {e}")
            print("Available MIDI ports:", mido.get_input_names())

        # Block Python execution here and show the Window
        self.exec()

        if inport:
            inport.close()

        if self._aborted:
            print("Application aborted by user.")
            sys.exit(0)

        return self.selected_folder_path