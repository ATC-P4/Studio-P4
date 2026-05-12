import os
import threading
import time
import fluidsynth
import mido
from core.utils import get_resource_path
from core.utils import MidiExporter
import platform

class Track:
    def __init__(self, name: str, synth: fluidsynth.Synth, channel: int, sf2_path: str = "sf2/basic_piano.sf2"):
        self.name = name
        self.is_muted = False
        self.is_armed = False
        self.program_id = 0  
        self.midi_events = []  
        self.active_notes = set()  
        self.event_lock = threading.Lock()
        
        self.synth = synth
        synth.setting('synth.gain', 1)
        self.channel = channel
        self.sf2_path = os.path.normpath(get_resource_path(sf2_path))
        self.sf_id = 0
        self.volume = 100 

    def _update_synth_program(self) -> None:
        """Consolidated helper to apply soundfont and program changes to the synth."""
        if self.synth:
            self.sf_id = self.synth.sfload(self.sf2_path)
            self.synth.program_select(self.channel, self.sf_id, 0, self.program_id)

    def initialize_synth(self) -> None:
        self._update_synth_program()

    def set_instrument(self, program_id: int) -> None:
        """
        ----- NOT IMPLEMENTED YET -----
        Sets the MIDI program (instrument) for this track.
        Only applies if the soundfont has multiple instruments on different program numbers. 
        not the same as setting a different soundfont, which always changes the entire soundfont and is the default method.
        Args:
            program_id (int): MIDI program number to select (0-127)
        """
        self.program_id = program_id
        self._update_synth_program()

    def set_soundfont(self, sf2_filename_or_path: str) -> None:
        """Loads a new soundfont, safely handling both relative filenames and absolute paths."""
        # FIX 2: Check if the string is already an absolute path from the router
        if os.path.isabs(sf2_filename_or_path):
            self.sf2_path = os.path.normpath(sf2_filename_or_path)
        else:
            self.sf2_path = os.path.normpath(get_resource_path(f"sf2/{sf2_filename_or_path}"))
            
        self._update_synth_program()

    def play_note_on(self, note: int, velocity: int) -> None:
        """Plays a MIDI note on this track, respecting mute status and managing active notes to prevent "stuck" notes.
        Args:
            note (int): MIDI note number to play.
            velocity (int): MIDI velocity for the note on event.
        """        
        if self.synth and not self.is_muted:
            if note in self.active_notes:
                self.synth.noteoff(self.channel, note)
                self.active_notes.discard(note)
            self.synth.noteon(self.channel, note, velocity)
            self.active_notes.add(note)
                                  
    def play_note_off(self, note: int) -> None:
        """Stops a MIDI note on this track, ensuring it is removed from the active notes set.
        Args:
            note (int): MIDI note number to stop.
        """
        if self.synth:
            self.synth.noteoff(self.channel, note)
            self.active_notes.discard(note)

    def flush_notes(self) -> None:
        """Immediately stops all currently active notes on this track. Useful for handling edge cases when switching armed tracks."""
        if self.synth:
            self.synth.cc(self.channel, 123, 0) 
            self.active_notes.clear() 

    def add_midi_event(self, msg: mido.Message, timestamp: float) -> None:
        """Thread-safe method to add a MIDI event to the track's event history.
        Args:
            msg (mido.Message): The MIDI message to add (should be note_on or note_off).
            timestamp (float): The timestamp in seconds when this event should occur relative to the start of the loop.
        """
        with self.event_lock:
            self.midi_events.append((msg, timestamp))
            
    def clear_events(self) -> None:
        """Thread-safe method to clear all MIDI events from the track. Useful for resetting a track or when deleting it."""
        with self.event_lock:
            self.midi_events.clear()

    def set_volume(self, midi_value: int) -> None:
        """Sets the volume for this track using MIDI CC 7. The synth's channel volume is updated immediately if the synth is initialized.
        Args:
            midi_value (int): MIDI velocity value (0-127) representing the desired volume level.
        """
        self.volume = midi_value
        if self.synth:
            self.synth.cc(self.channel, 7, self.volume)


class Metronome:
    def __init__(self, synth: fluidsynth.Synth, sf2_path: str = "sf2/Metronom.sf2", bank: int = 128, program: int = 48):
        self.synth = synth
        self.channel = 9 
        self.active_notes = set() 
        
        absolute_sf2_path = get_resource_path(sf2_path)
        self.sfid = self.synth.sfload(absolute_sf2_path)
        self.synth.program_select(self.channel, self.sfid, bank, program)

    def play_click(self, is_downbeat: bool) -> None:
        """Plays a metronome click. Uses different MIDI notes for downbeats vs. regular beats, and ensures no notes get stuck.
        Args:
            is_downbeat (bool): True if this click is a downbeat (first beat of the measure), False for regular beats.
        """
        for note in [76, 77]:
            if note in self.active_notes:
                self.synth.noteoff(self.channel, note)
                self.active_notes.discard(note)
            
        if is_downbeat:
            self.synth.noteon(self.channel, 76, 100) 
            self.active_notes.add(76)
        else:
            self.synth.noteon(self.channel, 77, 75)
            self.active_notes.add(77)


class Project:
    def __init__(self, pname: str, bpm: int = 120, time_signature: tuple = (4, 4)):
        self.name = pname
        self.bpm = bpm
        self.time_signature = time_signature
        self.time_signature_numerator, self.time_signature_denominator = self.time_signature
        self.tracks: list[Track] = []
        self.beat_duration = 60.0 / self.bpm 
        self.master_loop_beats = 0
        self.master_track = None

        # Audio setup
        self.master_synth = fluidsynth.Synth()
        self.gain = 0.4
        self.master_synth.setting("synth.gain", self.gain)
        self.master_synth.setting("audio.periods", 8)
        self.master_synth.setting("audio.period-size", 512)
        self.master_synth.setting("synth.sample-rate", 44100.0)
        
        # Driver depending on the machine type
        current_os = platform.system()
        
        if current_os == "Darwin": # MacOS
            self.master_synth.start(driver="coreaudio")
            #print("[AUDIO] MacOS Mode (coreaudio) activated.")
            
        elif current_os == "Windows":
            self.master_synth.start(driver="dsound") 
            #print("[AUDIO] Windows mode (wasapi) activated.")
            
        else:  # Linux
            self.master_synth.start(driver="pulseaudio") # or "alsa"
            print(f"[AUDIO] System {current_os} detected. Generic mode activated.")
        self.master_synth.setting("midi.driver", "none")
        self.master_synth.setting("midi.autoconnect", 0)

        self.master_synth.setting("midi.driver", "none")
        self.master_synth.setting("midi.autoconnect", 0)

        # Ch 0 removed to prevent dupe listening. Ch 9 reserved for Metronome.
        self.available_channels = [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15]

        self.master_synth.cc(0, 7, 0)
        self.master_synth.cc(0, 11, 0)
        self.metronome = Metronome(synth=self.master_synth)

    def add_track(self, name: str) -> None:
        """Adds a new track to the project with the given name. Automatically assigns an available MIDI channel and initializes the synth for that track.
        Args:
            name (str): The name of the new track to add.
        """
        if not self.available_channels: 
            return
        assigned_channel = self.available_channels.pop(0)
        track = Track(name, synth=self.master_synth, channel=assigned_channel)
        track.initialize_synth()  
        track.is_armed = (len(self.tracks) == 0)  
        self.tracks.append(track)
        
    def get_armed_track(self) -> Track | None:
        """
        Returns the currently armed track, or None if no track is armed.
        """
        return next((track for track in self.tracks if track.is_armed), None)

    def save_project(self, folder_name: str | None = None) -> None:
        """Saves the project MIDI tracks to the specific requested folder."""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        folder_name = folder_name or f"project_{timestamp}"
        
        project_folder = os.path.join(os.path.abspath("."), "Saves", folder_name)
        os.makedirs(project_folder, exist_ok=True)

        for track in self.tracks:
            full_path = os.path.join(project_folder, f"{track.name}.mid")
            # Delegate the heavy lifting to the new service!
            MidiExporter.export_track(track, full_path, self.bpm, self.master_loop_beats)

    def set_gain(self, gain: float) -> None:
        """Sets the master gain for the project's synth. Value should be between 0.0 and 1.0. 
        Act as a master volume control for all tracks since they share the same synth engine.
        Args:
            gain (float): The desired gain value.
        """
        self.gain = gain
        self.master_synth.setting("synth.gain", self.gain)