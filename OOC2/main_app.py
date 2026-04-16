import os
import queue
import sys
import threading
import time

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget
)
import sounddevice as sd
import soundfile as sf

import functions as f
import states as s

# Test
from piper import PiperVoice
import wave
import io


# ---------------------------------------------------------------------------
# EXCEPTION CATCHING
# ---------------------------------------------------------------------------

import signal
import faulthandler

# Dumps a Python traceback even on hard crashes (SIGSEGV etc.)
faulthandler.enable()

def signal_handler(sig, frame):
    print(f"[SIGNAL] Received signal {signal.Signals(sig).name}")
    import traceback
    traceback.print_stack(frame)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGSEGV, signal_handler)  # May not work on Windows

# import sys
# sys.stderr = open("crash.log", "w", buffering=1)  # line-buffered
# sys.stdout = open("out.log", "w", buffering=1)

def global_thread_exception_handler(args):
    print(f"[CRASH] Thread exception: {args.exc_type.__name__}: {args.exc_value}")
    import traceback
    traceback.print_tb(args.exc_traceback)

threading.excepthook = global_thread_exception_handler

# ---------------------------------------------------------------------------


class AccessibleStudio(QMainWindow):
    # Secure communication app (Signal)
    midi_signal = Signal(object)

    def __init__(self) -> None:
        
        super().__init__()

        self._speech_queue = queue.Queue()
        voice_path = "fr_FR-siwis-medium.onnx" # os.path.join(self.base_dir, "fr_FR-siwis-medium.onnx")
        self._voice = PiperVoice.load(voice_path)

        # Current "state" members (TODO: cleanup)
        self.rec_thread = False
    
        # Memory for the BPM roulette
        self.last_bpm_knob_value = None
        # Connect our "pipe" to the function that will sort the messages
        self.midi_signal.connect(self.process_midi_command)

        # Provide the entry point to backend
        s.midi_callback = self.midi_signal.emit

        # retrieve the exact directory where main_app.py is located
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self._init_backend()
        self._init_ui()
        self._init_shortcuts()

        self.speak("Bienvenue dans le prototype 1 de Logiciel Studio.")


    # ---------------------------------------------------------------------------
    # SPEECH THREAD
    # ---------------------------------------------------------------------------

    # TODO: initialise speech thread
    def _speech_worker(self) -> None:
        """Single persistent thread that owns the audio engine exclusively."""
        while True:
            text = self._speech_queue.get()
            if text is None:  # Poison pill to shut down cleanly
                return
            try:
                buf = io.BytesIO()
                with wave.open(buf, 'wb') as wav:
                    self._voice.synthesize(text, wav)
                buf.seek(0)
                data, samplerate = sf.read(buf)
                sd.play(data, samplerate)
                sd.wait()
            except Exception as e:
                print(f"[speech] Error: {e}")

    # ---------------------------------------------------------------------------
    # BACKEND INITIALIZATION
    # ---------------------------------------------------------------------------

    def _init_backend(self) -> None:
        s.m_p = f.create_project("Projet P4")
        s.s_t = f.create_track("Piste Piano", s.m_p)
        s.s_t.length = 4  # length of 4 measures
        s.s_t.midi_file_name = os.path.join(self.base_dir, "piano_track.mid")
        # Specify the exact path to the sound bank in FluidSynth
        sf2_path = os.path.join(self.base_dir, "basic_piano.SF2")
        s.s_t.update_soundfont(sf2_path)  # Dynamic update
        # Launch of MIDI port discovery in the background
        self.port_thread = threading.Thread(target=f.port_discovery, daemon=True)
        self.port_thread.start()

    # ---------------------------------------------------------------------------
    # GRAPHICAL USER INTERFACE
    # ---------------------------------------------------------------------------

    def _init_ui(self):
        self.setWindowTitle("P4 Studio")
        self.resize(800, 800)
        self.setStyleSheet("""
            QMainWindow { background-color: #000000; }
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

        self.label_status = QLabel("Studio prêt. Appuyez sur R pour enregistrer.")
        self.label_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        self.btn_rec.clicked.connect(self.action_record)
        self.btn_play.clicked.connect(self.action_play)


    def _init_shortcuts(self):
        QShortcut(QKeySequence("R"), self, self.action_record)
        QShortcut(QKeySequence("Space"), self, self.action_play)
        QShortcut(QKeySequence("Up"), self, self.bpm_up)
        QShortcut(QKeySequence("Down"), self, self.bpm_down)
        QShortcut(QKeySequence("B"), self, self.speak_info)
        QShortcut(QKeySequence("M"), self, self.metronome_toggle)
        QShortcut(QKeySequence("I"), self, self.info)

    # ---------------------------------------------------------------------------
    # SPEECH
    # ---------------------------------------------------------------------------

    def speak(self, text):
        """
        Queues text for speech.
        """
        # TODO
        return

        

    # ---------------------------------------------------------------------------
    # GLOBAL INFO FUNCTION
    # ---------------------------------------------------------------------------

    def info(self):
        # Can't speak when recording or playing
        print(f"[info] rec: {self.rec_thread}")
        if self.rec_thread:
            return
        self.metronome_info()
        self.speak_info()


    # ---------------------------------------------------------------------------
    # METRONOME LOGIC
    # ---------------------------------------------------------------------------
    
    def metronome_toggle(self):
        if s.metronome_on:
            self.speak("Métronome désactivé")
        else: 
            self.speak("Métronome activé")
        s.metronome_on = not s.metronome_on

    def metronome_info(self):
        if s.metronome_on:
            self.speak("Métronome activé")
        else: 
            self.speak("Métronome désactivé")

    def play_metronome(self):

        bpm = s.m_p.bpm
        # Calculating the time between each beat in seconds (e.g., 60 / 120 = 0.5 s)
        beat_duration = 60.0 / bpm

        print(f"[play_metronome] {s.metronome_on} {self.rec_thread}")

        while(self.rec_thread):

            for i in range(1, 5):

                if s.metronome_on:
                    self.play_tick(accent=(i == 1))

                # We wait for the rest of the beat
                time.sleep(beat_duration)

    # ---------------------------------------------------------------------------
    # BUTTON LOGIC
    # ---------------------------------------------------------------------------

    def action_record(self) -> None:
        if s.record_flag:
            # Manual stop request
            s.record_flag = False
            self.rec_thread = False
            self.label_status.setText("Prêt")
            self.speak("Enregistrement arrêté.")
        else:
            # Instead of starting the live recording, we start the countdown sequence
            if self.rec_thread:
                return
            else:
                self.rec_thread = True 
                threading.Thread(target=self.recording_sequence, daemon=True).start()
                if s.metronome_on:
                    threading.Thread(target=self.play_metronome, daemon=True).start()



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
            # self.speak(f"{i}")
            self.play_tick(accent=(i == 1))

            # We wait for the rest of the beat
            time.sleep(beat_duration)

        # record
        s.record_flag = True
        self.label_status.setText("🔴 ENREGISTREMENT...")
        print("[DEBUG] Go Record!")

        f.record()

        # When f.record() has finished recording its 4 beats, the code resumes here:
        self.label_status.setText("Prêt")
        time.sleep(0.2)
        self.speak("Piste sauvegardée.")



    # Method to play a metronome-like tick
    def play_tick(self, accent=False):
        """Generates and plays a single metronome tick as a sine wave burst."""
        sample_rate = 44100
        duration = 0.08  # seconds — short click
        freq = 1800 if accent else 1200  # Hz — higher pitch on beat 1

        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = np.sin(2 * np.pi * freq * t)

        # Fade out to avoid clicks at the end
        fade = np.linspace(1.0, 0.0, len(wave))
        wave = (wave * fade * 0.5).astype(np.float32)

        sd.play(wave, sample_rate)
        sd.wait()



    def action_play(self):
        
        if s.is_playing:
            return
        else:

            def stop_playing():
                self.label_status.setText("PLAY (ESPACE)")
                s.is_playing = False

            s.is_playing = True
            self.label_status.setText("▶ LECTURE...")
            # self.speak("Lecture de la piste.")
            # We start the player in a separate thread so we can stop it later if necessary
            threading.Thread(target=lambda: f.player(stop_playing), daemon=True).start()

    # ---------------------------------------------------------------------------
    # BPM CONTROLS
    # ---------------------------------------------------------------------------

    def bpm_up(self):

        if s.m_p.bpm >= 400:
            return

        s.m_p.bpm += 4
        message = f"BPM {s.m_p.bpm}"
        self.label_status.setText(message)
        self.speak(message)
        print(f"[DEBUG] {message}")

    def bpm_down(self):

        if s.m_p.bpm <= 10:
            return
        
        s.m_p.bpm -= 4
        # Safety measures to avoid a negative or zero BPM
        
        message = f"BPM {s.m_p.bpm}"
        self.label_status.setText(message)
        self.speak(message)
        print(f"[DEBUG] {message}")

    def speak_info(self):
        self.speak(f"BPM actuel: {s.m_p.bpm}")

    # ---------------------------------------------------------------------------
    # MIDI
    # ---------------------------------------------------------------------------

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
        if msg.type != 'control_change':
            return

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

    # ---------------------------------------------------------------------------
    # CLOSING PROCEDURES
    # ---------------------------------------------------------------------------

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
        # TODO: terminate speech thread
        # -----------------------------
        s.terminate_flag = True
        self.port_thread.join(timeout=1)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AccessibleStudio()
    window.show()
    sys.exit(app.exec())
