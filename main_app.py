# System imports
from collections.abc import Callable #, Iterable
from enum import Enum
import os
# from queue import Queue
import sys
import threading
import time
from typing import Any
import re

# Installed imports
from mido import MidiFile, MidiTrack, Message
import numpy as np
from piper import PiperVoice, SynthesisConfig #, AudioChunk
import pyaudio as pa
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget
)
import sounddevice as sd

# Our imports
import functions as f
from classes2 import Project, Track




# Code from StackOverflow 
class UpdatableBlockingQueue(object):

  def __init__(self):
    self.queue = {}
    self.cv = threading.Condition()

  def put(self, key, value):
    with self.cv:
      self.queue[key] = value
      self.cv.notify()

  def pop(self):
    with self.cv:
      while not self.queue:
        self.cv.wait()
      return self.queue.popitem()



class ApplicationState():

    def __init__(self, main_project, selected_track, midi_callback=None, bpm=120) -> None:

        # List of global variables that define the state of the program, used for communication between threads and functions

        # Objects and functions 
        # Main project object, holds the project settings and tracks
        self.main_project: Project = main_project
        # Selected track object, holds the track settings and MIDI data
        self.selected_track: Track = selected_track
        # MIDI track object from mido, used to store recorded MIDI messages
        # self.midi_track: MidiTrack = midi_track
        # Holds the MIDI callback function, allowing dynamic assignment and control over MIDI message handling
        self.midi_callback: Callable[[Message], None] | None = midi_callback

        # Counters
        # Timestamp of the last received MIDI message, used to calculate time deltas for recording
        # self.last_msg_time: float | None = None
        # Counts the number of recorded ticks, used to determine when to stop recording based on track length and tempo
        # self.recorded_ticks: int = 0
        # Current BPM
        self.bpm: int = bpm

        # Flags
        # Signals that we're closing the app
        self.terminate_flag: bool = False 
        # Whether we're currently recording
        self.record_flag: bool = False 
        # Whether the metronome is currently set to "on"
        self.metronome_on: bool = False
        # Whether we're currently playing back a track
        self.is_playing: bool = False

    # TODO: class attributes have changed
    def to_string(self) -> str:

        project = "main_project: "
        if self.main_project is not None:
            project += self.main_project.to_string()
        else:
            project += "None"

        st = "selected_track: "
        if self.selected_track is not None:
            st += self.selected_track.to_string()
        else:
            st += "None"

        mt = "midi_track: "
        if self.selected_track.midi_track is not None:
            mt += self.selected_track.midi_track.__str__()
        else:
            mt += "None"

        mc = "midi_callback: "
        if self.midi_callback is not None:
            mc += self.midi_callback.__str__()
        else:
            mc += "None"

        lmt = "last_msg_time: "
        if self.selected_track.last_msg_time is not None:
            lmt += f"{self.selected_track.last_msg_time}"
        else:
            lmt += "None"

        return f"""ApplicationState(
                {project},
                {st},
                {mt},
                {mc},
                {lmt},
                recorded_ticks: {self.selected_track.recorded_ticks}
                bpm: {self.bpm}
                terminate_flag: {self.terminate_flag},
                record_flag: {self.record_flag},
                metronome_on: {self.metronome_on},
                is_playing: {self.is_playing}
                )"""


# Quick clickable QLabel (thanks StackOverflow)
class _QLabel(QLabel):
    clicked=Signal()

    def mousePressEvent(self, ev):
        self.clicked.emit()


class SpeechType(Enum):
    BPM_INFO = 1
    BPM_MOD = 2
    REC_STOP = 3
    WELCOME = 4
    METR_TOGGLE = 5
    TRACK_SAVE = 6
    METR_INFO = 7
    STOP = 0

from main_app import SpeechType as st

class AccessibleStudio(QMainWindow):

    
    # Secure communication app (Signal)
    midi_signal: Signal = Signal(object)

    def __init__(self) -> None:
        
        super().__init__()

        # Speech model 
        self._speech_queue = UpdatableBlockingQueue()
        voice_path = "fr_FR-siwis-medium.onnx"
        self._voice = PiperVoice.load(voice_path)
        self._voice_config = SynthesisConfig(
            volume=0.5,
            length_scale=1.2,
            noise_scale=0.667,
            noise_w_scale=0.8,
            normalize_audio=True
        )

        # Init speech thread
        threading.Thread(target=self._speech_worker, daemon=True).start()

        # TODO: are these useful?
        # -----------------------------
        # Current "state" members
        self.rec_thread = False
        # Memory for the BPM roulette
        self.last_bpm_knob_value = None
        # -----------------------------

        # Connect our "pipe" to the function that will sort the messages
        self.midi_signal.connect(self.process_midi_command)

        # ---------------------------------------------------------------------------
        # BACKEND INITIALIZATION
        # ---------------------------------------------------------------------------
        # TODO
        proj: Project = Project(pname="Projet P4")
        track: Track = proj.add_track("Piste piano")
        track.update_soundfont("basic_piano.SF2")

        # Init current state
        self._state = ApplicationState(main_project=proj,
                                        selected_track=track, midi_callback=self.midi_signal.emit)
    
        # initiating the time tracking (?)
        # mid = MidiFile(ticks_per_beat=self._state.main_project.tpb)
        # mid.tracks.append(self._state.midi_track)

        # Start port discovery thread
        threading.Thread(target=lambda: f.port_discovery(self._state), daemon=True).start()

        self._init_ui()

        QShortcut(QKeySequence("R"), self, self.action_record)
        QShortcut(QKeySequence("Space"), self, self.action_play)
        QShortcut(QKeySequence("Up"), self, self.bpm_up)
        QShortcut(QKeySequence("Down"), self, self.bpm_down)
        QShortcut(QKeySequence("B"), self, self.bpm_info)
        QShortcut(QKeySequence("M"), self, self.metronome_toggle)
        QShortcut(QKeySequence("I"), self, self.speak_info)

        self.speak(st.WELCOME, "Bienvenue dans le prototype 1 de Logiciel Studio.")




    # ---------------------------------------------------------------------------
    # SPEECH THREAD
    # ---------------------------------------------------------------------------

    def _speech_worker(self) -> None:
        """Single persistent thread that owns the audio engine exclusively."""

        player = pa.PyAudio()
        stream = player.open(
            format=pa.paInt16,
            channels=1,
            rate=self._voice.config.sample_rate,
            output=True
        )

        while True:
            speechtype, audio = self._speech_queue.pop()
            
            if speechtype == SpeechType.STOP:
                stream.stop_stream()
                stream.close()
                return

            for chunk in audio:
                stream.write(chunk.audio_int16_bytes)


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
                color: #F0FFFF;
                margin-bottom: 20px;
            }
            QFrame#ControlCard {
                background-color: #1E1E1E;
                border-radius: 15px;
                border: 1px solid #333;
            }
            QLabel#MetronomeStatus {
                font-size: 16px;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 8px;
            }
            QLabel#MetronomeStatus[metronome_on="true"] {
                color: #00FF88;
                background-color: #003322;
                border: 1px solid #00FF88;
            }
            QLabel#MetronomeStatus[metronome_on="false"] {
                color: #888888;
                background-color: #1A1A1A;
                border: 1px solid #444444;
            }
        """)

        self.label_status = QLabel("Studio prêt. Appuyez sur R pour enregistrer.")
        self.label_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Metronome status label ---
        self.label_metronome = _QLabel()
        self.label_metronome.setObjectName("MetronomeStatus")
        self.label_metronome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_metronome_label()  # set initial text and style
        # ------------------------------

        self.btn_rec = QPushButton("🔴 RECORD (R)")
        self.btn_rec.setAccessibleIdentifier("Enregistrement")
        self.btn_rec.setAccessibleDescription("Bouton pour démarrer ou arrêter un enregistrement.")
        self.btn_rec.setAccessibleName

        self.btn_play = QPushButton("▶ PLAY (ESPACE)")
        self.btn_play.setAccessibleIdentifier("Play")
        self.btn_play.setAccessibleDescription("Bouton pour démarrer le playback du track enregistré.")

        layout = QVBoxLayout()
        layout.addWidget(self.label_status)
        layout.addWidget(self.label_metronome)
        layout.addWidget(self.btn_rec)
        layout.addWidget(self.btn_play)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.btn_rec.clicked.connect(self.action_record)
        self.btn_play.clicked.connect(self.action_play)

        self.label_metronome.clicked.connect(self.metronome_toggle)


    # ---------------------------------------------------------------------------
    # SPEECH
    # ---------------------------------------------------------------------------

    def speak(self, type: SpeechType, text: str):
        """Queues text for speech."""

        def _add_sentence():
            snt = self._voice.synthesize(text)
            self._speech_queue.put(type, snt)

        threading.Thread(target=_add_sentence, daemon=True).start()



    # ---------------------------------------------------------------------------
    # GLOBAL INFO FUNCTION
    # ---------------------------------------------------------------------------

    def info(self):
        self.speak_info()

    # ---------------------------------------------------------------------------
    # METRONOME LOGIC
    # ---------------------------------------------------------------------------

    def _update_metronome_label(self):
        """Refreshes the metronome status label to reflect the current state."""
        if self._state.metronome_on:
            self.label_metronome.setText("MÉTRONOME  ●  ON")
            self.label_metronome.setProperty("metronome_on", "true")
        else:
            self.label_metronome.setText("MÉTRONOME  ○  OFF")
            self.label_metronome.setProperty("metronome_on", "false")

        # Force Qt to re-evaluate the stylesheet after the property change
        self.label_metronome.style().unpolish(self.label_metronome)
        self.label_metronome.style().polish(self.label_metronome)

    def metronome_toggle(self):
        self._state.metronome_on = not self._state.metronome_on
        self._update_metronome_label()
        if self._state.metronome_on:
            self.speak(st.METR_TOGGLE, "Métronome activé")
        else:
            self.speak(st.METR_TOGGLE, "Métronome désactivé")

    def play_metronome(self):

        bpm = self._state.bpm
        beat_duration = 60.0 / bpm

        while(self.rec_thread):
            for i in range(1, 5):
                if self._state.metronome_on:
                    self.play_tick(accent=(i == 1))
                time.sleep(beat_duration)

    # ---------------------------------------------------------------------------
    # BUTTON LOGIC
    # ---------------------------------------------------------------------------

    def action_record(self) -> None:
        if self._state.record_flag:
            self._state.record_flag = False
            self.rec_thread = False
            self.label_status.setText("Prêt")
            self.speak(st.REC_STOP, "Enregistrement arrêté.")
        else:
            if self.rec_thread:
                return
            else:
                if self._state.selected_track.midi_file_name is None:
                    name = self.save_track_dialog()
                    self._state.selected_track.midi_file_name = name

                self.rec_thread = True 
                threading.Thread(target=self.recording_sequence, daemon=True).start()
                if self._state.metronome_on:
                    threading.Thread(target=self.play_metronome, daemon=True).start()


    def recording_sequence(self):
        """Handles the countdown then recording, then prompts for a save location."""

        bpm = self._state.bpm
        beat_duration = 60.0 / bpm

        for i in range(1, 5):
            self.label_status.setText(f"Décompte : {i}")
            self.play_tick(accent=(i == 1))
            time.sleep(beat_duration)

        self._state.record_flag = True
        self.label_status.setText("🔴 ENREGISTREMENT...")

        f.record(self._state)

        self.label_status.setText("Prêt")
        time.sleep(0.2)

        if self._state.selected_track.midi_file_name is not None:
            path = self._state.selected_track.midi_file_name.split("/")
            name = path[len(path)-1]
            self.speak(st.TRACK_SAVE, f"Piste sauvegardée dans le fichier {name}.")



    # ---------------------------------------------------------------------------
    # SAVE DIALOG
    # ---------------------------------------------------------------------------

    def save_track_dialog(self) -> str:
        """
        Opens a simple Save As dialog for the user to choose the MIDI file
        name and location.

        Returns the chosen file path as a string, or None if the user cancelled.
        The .mid extension is appended automatically if omitted.
        """

        self.speak(st.TRACK_SAVE, "Veuillez choisir un nom pour le fichier dans lequel sera sauvegardé le track MIDI.")

        DEFAULT = "track.mid"
        fn = DEFAULT

        if self._state.selected_track.midi_file_name is not None:
            fn = self._state.selected_track.midi_file_name

        default_path = os.path.join(os.path.abspath(__file__), fn)

        file_path, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Enregistrer la piste MIDI",
            dir=default_path,
            filter="Fichiers MIDI (*.mid);;Tous les fichiers (*)"
        )

        if not file_path:
            self.speak(st.TRACK_SAVE, f"Nom choisi: {DEFAULT}")
            return DEFAULT

        # Ensure the .mid extension is present
        if not file_path.lower().endswith(".mid"):
            file_path += ".mid"

        fp = file_path.split("/")
        name = fp[len(fp)-1]
        self.speak(st.TRACK_SAVE, f"Nom choisi: {name}")

        return file_path



    # Method to play a metronome-like tick
    def play_tick(self, accent=False):
        """Generates and plays a single metronome tick as a sine wave burst."""
        sample_rate = 44100
        duration = 0.08
        freq = 1800 if accent else 1200

        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = np.sin(2 * np.pi * freq * t)

        fade = np.linspace(1.0, 0.0, len(wave))
        wave = (wave * fade * 0.5).astype(np.float32)

        sd.play(wave, sample_rate)
        sd.wait()


    def action_play(self):
        
        if self._state.is_playing:
            return
        else:
            def stop_playing():
                self.label_status.setText("Prêt.")
                self._state.is_playing = False

            self._state.is_playing = True
            self.label_status.setText("▶ LECTURE...")
            threading.Thread(target=lambda: f.player(stop_playing, self._state), daemon=True).start()

    # ---------------------------------------------------------------------------
    # BPM CONTROLS
    # ---------------------------------------------------------------------------

    def bpm_up(self):
        if self._state.bpm >= 320:
            return
        self._state.bpm += 4
        message = f"B P M {self._state.bpm}"
        self.label_status.setText(message)
        self.speak(st.BPM_MOD, message)

    def bpm_down(self):
        if self._state.bpm <= 8:
            return
        self._state.bpm -= 4
        message = f"B P M {self._state.bpm}"
        self.label_status.setText(message)
        self.speak(st.BPM_MOD, message)

    def bpm_info(self):
        self.speak(st.BPM_INFO, f"B P M actuel: {self._state.bpm}")

    def speak_info(self):
        info = ""
        if self._state.metronome_on:
            info += "Métronome actuellement activé."
        else: 
            info += "Métronome actuellement désactivé."

        self.speak(st.METR_INFO, info)
        self.bpm_info()

    # ---------------------------------------------------------------------------
    # MIDI
    # ---------------------------------------------------------------------------

    def process_midi_command(self, msg):
        """
        Processes incoming MIDI messages and maps them to UI actions.

        Args:
            msg (mido.Message): The MIDI message object received from the input port.
        """
        if msg.type != 'control_change':
            return

        if msg.control == 119 and msg.value > 0:
            self.action_record()

        elif msg.control == 118 and msg.value > 0:
            self.action_play()

        elif msg.control == 77:
            if self.last_bpm_knob_value is not None:
                if msg.value > self.last_bpm_knob_value:
                    self.bpm_up()
                elif msg.value < self.last_bpm_knob_value:
                    self.bpm_down()
            self.last_bpm_knob_value = msg.value

    # ---------------------------------------------------------------------------
    # CLOSING PROCEDURES
    # ---------------------------------------------------------------------------

    def closeEvent(self, event):
        """
        Handles the application's close event to ensure a clean shutdown.

        Args:
            event (QCloseEvent): The close event object provided by PySide6.
        """
        print("Fermeture de l'application...")
        self._speech_queue.put(SpeechType.STOP, "STOP")
        self._state.terminate_flag = True
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AccessibleStudio()
    window.show()
    sys.exit(app.exec())