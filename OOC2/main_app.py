import os
import sys
import threading
import time
import pyttsx3
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShortcut, QKeySequence
import states as s
import functions as f

class AccessibleStudio(QMainWindow):
    # Secure communication app (Signal)
    midi_signal = Signal(object)

    def __init__(self):
        super().__init__()
        # Memory for the BPM roulette
        self.last_bpm_knob_value = None
        # Connect our “pipe” to the function that will sort the messages
        self.midi_signal.connect(self.process_midi_command)
        
        # Provide the entry point to backend
        s.midi_callback = self.midi_signal.emit

        # retrieve the exact directory where main_app.py is located
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        # BACKEND INITIALIZATION
        s.m_p = f.create_project("Projet P4")
        s.s_t = f.create_track("Piste Piano", s.m_p)
        s.s_t.length = 4 # length of 4 measures
        s.s_t.midi_file_name = os.path.join(self.base_dir, "piano_track.mid")
        # Specify the exact path to the sound bank in FluidSynth
        sf2_path = os.path.join(self.base_dir, "basic_piano.SF2")
        s.s_t.update_soundfont(sf2_path) # Dynamic update
        # Launch of MIDI port discovery in the background
        self.port_thread = threading.Thread(target=f.port_discovery, daemon=True)
        self.port_thread.start()

        # Voice initialization
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 180)

        # Graphical user interface
        self.setWindowTitle("P4 Studio - Connecté au Backend")
        self.resize(4000, 4000)

        self.label_status = QLabel("Studio prêt. Appuyez sur R pour enregistrer.")
        self.label_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QMainWindow { background-color: #F0FFFF; }
            QLabel#Title { 
                font-size: 24px; 
                font-weight: bold; 
                color: #F0FFFF; /* Vert néon musical */
                margin-bottom: 20px;
            }
            QFrame#ControlCard {
                background-color: #1E1E1E;
                border-radius: 15px;
                border: 1px solid #333;
            }
        """)
        
        self.btn_rec = QPushButton("🔴 RECORD (R)")
        self.btn_play = QPushButton("▶ PLAY (ESPACE)")

        layout = QVBoxLayout()
        layout.addWidget(self.label_status)
        layout.addWidget(self.btn_rec)
        layout.addWidget(self.btn_play)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        #  Connections (Signals to the Backend)
        QShortcut(QKeySequence("R"), self, self.action_record)
        self.btn_rec.clicked.connect(self.action_record)

        QShortcut(QKeySequence("Space"), self, self.action_play)
        self.btn_play.clicked.connect(self.action_play)

        # BPM connections
        QShortcut(QKeySequence("Up"), self, self.bpm_up)
        QShortcut(QKeySequence("Down"), self, self.bpm_down)

        self.speak("Bienvenue dans le prototype 1 de Logiciel Studio.")

    def speak(self, text):
        """
        Executes text-to-speech synthesis in a non-blocking background thread.

        This method creates a daemon thread to initialize the pyttsx3 engine 
        and speak the provided text. This prevents the main PySide6 GUI event 
        loop from freezing during the audio playback.

        Args:
            text (str): The string of text to be spoken by the engine.
        """
        def run_speech():
            engine = pyttsx3.init()
            engine.setProperty('rate', 180)
            engine.say(text)
            engine.runAndWait()
        threading.Thread(target=run_speech, daemon=True).start()

    # Button Logic
    def action_record(self):
        if s.record_flag is True:
            # Manual stop request
            s.record_flag = False
            self.label_status.setText("Prêt")
            self.speak("Enregistrement arrêté.")
        else:
            # Instead of starting the live recording, we start the countdown sequence
            threading.Thread(target=self.recording_sequence, daemon=True).start()

    def recording_sequence(self):
        """Handles the countdown before starting the actual recording"""
        bpm = s.m_p.bpm
        # Calculating the time between each beat in seconds (e.g., 60 / 120 = 0.5 s)
        beat_duration = 60.0 / bpm 
        
        print(f"[DEBUG] Lancement du décompte à {bpm} BPM")
        
        # Countdown loop (1, 2, 3, 4)
        for i in range(1, 5):
            self.label_status.setText(f"Décompte : {i}")
            # We use synchronized audio here to prevent voice tracks from overlapping
            engine = pyttsx3.init()
            engine.setProperty('rate', 220)
            engine.setProperty('volume', 0.6)
            engine.say(str(i))
            engine.runAndWait() 
            
            # We wait for the rest of the beat
            time.sleep(beat_duration)
            
        # record
        s.record_flag = True
        self.label_status.setText("🔴 ENREGISTREMENT...")
        print("[DEBUG] Go Record!")
        
        f.record() 
        
        # When f.record() has finished recording its 4 measures, the code resumes here:
        self.label_status.setText("Prêt")
        self.speak("Piste sauvegardée.")

    def action_play(self):
        self.label_status.setText("▶ LECTURE...")
        self.speak("Lecture de la piste.")
        # We start the player in a separate thread so we can stop it later if necessary
        play_thread = threading.Thread(target=f.player, daemon=True)
        play_thread.start()

    # Closing Procedures
    def closeEvent(self, event):
        """
        Handles the application's close event to ensure a clean shutdown.

        Triggered when the user attempts to close the main window. It sets the 
        global termination flag to gracefully stop all background MIDI loops 
        and waits for the port discovery thread to join before accepting the closure.

        Args:
            event (QCloseEvent): The close event object provided by PySide6.
        """
        print("Fermeture de l'application...")
        s.terminate_flag = True
        self.port_thread.join(timeout=1)
        event.accept()

    def bpm_up(self):
        s.m_p.bpm += 5
        message = f"BPM {s.m_p.bpm}"
        self.label_status.setText(message)
        self.speak(message)
        print(f"[DEBUG] {message}")

    def bpm_down(self):
        s.m_p.bpm -= 5
        # Safety measures to avoid a negative or zero BPM
        if s.m_p.bpm < 40:
            s.m_p.bpm = 40
            
        message = f"BPM {s.m_p.bpm}"
        self.label_status.setText(message)
        self.speak(message)
        print(f"[DEBUG] {message}")
    
    def process_midi_command(self, msg):
        """
        Processes incoming MIDI messages and maps them to UI actions.

        This method acts as the MIDI Learn/Mapping router. It intercepts external 
        Control Change (CC) messages from a connected MIDI keyboard and triggers 
        the corresponding functions (e.g., Record, Play, BPM adjustment) as if 
        the user interacted with the graphical interface.

        Args:
            msg (mido.Message): The MIDI message object received from the input port.
        """
        
        if msg.type == 'control_change':
            
            # record button (CC 119)
            if msg.control == 119 and msg.value > 0:
                print("[MIDI] Bouton RECORD pressé")
                self.action_record()

            # Play button (CC 118)
            elif msg.control == 118 and msg.value > 0:
                print("[MIDI] Bouton PLAY pressé")
                self.action_play()

            # BPM Wheel(CC 77)
            elif msg.control == 77:
                # If a value is already in memory, we compare it
                if self.last_bpm_knob_value is not None:
                    if msg.value > self.last_bpm_knob_value:
                        self.bpm_up()    # Turn right
                    elif msg.value < self.last_bpm_knob_value:
                        self.bpm_down()  # Turn left
                
                # Update the memory with the new value
                self.last_bpm_knob_value = msg.value


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AccessibleStudio()
    window.show()
    sys.exit(app.exec())