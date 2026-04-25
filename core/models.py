import os
from os import path
import time

import fluidsynth
import mido

import fluidsynth
import mido

from core.utils import get_resource_path

class Track:
    def __init__(self, name: str, synth: fluidsynth.Synth, channel: int, sf2_path: str = "sf2/basic_piano.sf2"):
        self.name = name
        self.is_muted = False
        self.is_armed = False
        self.program_id = 0  
        self.midi_events = []  
        self.active_notes = set()  
        
        self.synth = synth
        self.channel = channel
        self.sf2_path = get_resource_path(sf2_path)
        self.sf_id = 0
        self.volume = 100 # Default volume (0-127)

    def initialize_synth(self):
        self.sf_id = self.synth.sfload(self.sf2_path)
        self.synth.program_select(self.channel, self.sf_id, 0, self.program_id)

    def set_instrument(self, program_id: int):
        self.program_id = program_id
        if self.synth:
            self.synth.program_select(self.channel, self.sf_id, 0, self.program_id)

    def set_soundfont(self, sf2_path: str):
        self.sf2_path = get_resource_path(f"sf2/{sf2_path}")
        #print(f"[TRACK] Setting soundfont for '{self.name}' to '{sf2_path}'")
        if self.synth:
            self.sf_id = self.synth.sfload(self.sf2_path)
            self.synth.program_select(self.channel, self.sf_id, 0, self.program_id)

    def play_note_on(self, note: int, velocity: int):
        if self.synth and not self.is_muted:
            if note in self.active_notes:
                self.synth.noteoff(self.channel, note)
                self.active_notes.discard(note)
            self.synth.noteon(self.channel, note, velocity)
            self.active_notes.add(note)
                                  
    def play_note_off(self, note: int):
        if self.synth:
            self.synth.noteoff(self.channel, note)
            self.active_notes.discard(note)

    def flush_notes(self):
        if self.synth:
            self.synth.cc(self.channel, 123, 0) # CC 123 is "All Notes Off"
            self.active_notes.clear() 

    def add_midi_event(self, msg, timestamp):
        self.midi_events.append((msg, timestamp))

    def export_to_midi(self, filepath: str, bpm: int, master_loop_beats: int, ticks_per_beat: int = 480):
        print(f"Exporting track '{self.name}' to MIDI file: {filepath}")
        mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
        midi_track = mido.MidiTrack()
        mid.tracks.append(midi_track)
        
        tempo = mido.bpm2tempo(bpm)
        midi_track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
        
        # (You should still include the program_change here so DAWs know the instrument)
        midi_track.append(mido.Message('program_change', channel=self.channel, program=self.program_id, time=0))
        
        sorted_events = sorted(self.midi_events, key=lambda x: x[1])
        last_time = 0.0
        
        for msg, timestamp in sorted_events:
            timestamp = max(0.0, timestamp)
            delta_seconds = timestamp - last_time
            last_time = timestamp
            
            delta_ticks = int(round(mido.second2tick(delta_seconds, ticks_per_beat, tempo)))
            midi_msg = msg.copy(channel=self.channel, time=delta_ticks)
            midi_track.append(midi_msg)
            
        # --- NEW: PADDING TO MATCH MASTER LOOP ---
        # 1. Calculate the target length of the loop in seconds
        total_loop_seconds = master_loop_beats * (60.0 / bpm)
        
        # 2. Find the remaining empty space after the final event
        remaining_seconds = total_loop_seconds - last_time
        
        # 3. If there is empty space, pad the file with an end_of_track message
        if remaining_seconds > 0:
            padding_ticks = int(round(mido.second2tick(remaining_seconds, ticks_per_beat, tempo)))
            midi_track.append(mido.MetaMessage('end_of_track', time=padding_ticks))
            
        # 4. Safe Save
        try:
            mid.save(filepath)
            print(f"[TRACK] Successfully exported: {filepath}")
        except Exception as e:
            print(f"[TRACK] ERROR exporting MIDI: {e}")

    def set_volume(self, midi_value: int):
        self.volume = midi_value
        if self.synth:
            self.synth.cc(self.channel, 7, self.volume)  # CC 7 is the standard volume control

class Metronome:
    def __init__(self, synth: fluidsynth.Synth, sf2_path: str = "sf2/Metronom.sf2", bank: int = 128, program: int = 48):
        self.synth = synth
        self.channel = 9 
        absolute_sf2_path = get_resource_path(sf2_path)
        self.sfid = self.synth.sfload(absolute_sf2_path)
        #self.sfid = self.synth.sfload(sf2_path)
        self.synth.program_select(self.channel, self.sfid, bank, program)
        self.active_notes = set() 

    def play_click(self, is_downbeat: bool):
        if 77 in self.active_notes:
            self.synth.noteoff(self.channel, 77)
            self.active_notes.discard(77)
        if 76 in self.active_notes:
            self.synth.noteoff(self.channel, 76)
            self.active_notes.discard(76)
            
        if is_downbeat:
            self.synth.noteon(self.channel, 76, 100) 
            self.active_notes.add(76)
        else:
            self.synth.noteon(self.channel, 77, 75)
            self.active_notes.add(77)

class Project:

    DEFAULT_MIDI_MAPPING = {
        119: "TOGGLE_RECORD",
        118: "TOGGLE_PLAY",
        117: "TOGGLE_METRONOME",
        77: "BPM_KNOB",
        116: "BPM_UP",
        115: "BPM_DOWN",
        2: "NAV_DOWN",
        3: "NAV_UP",
        12: "NAV_LEFT",
        13: "NAV_RIGHT",
        1: "VOLUME_ROLLER"

        # Add any other defaults here!
        # knobs 70-77

    }
    def __init__(self, pname: str, bpm: int = 120, time_signature: tuple = (4, 4)):
        self.name = pname
        self.bpm = bpm
        self.time_signature : tuple = time_signature
        self.time_signature_numerator, self.time_signature_denominator = self.time_signature
        self.tracks : list[Track] = []
        self.beat_duration = 60.0 / self.bpm 
        self.master_loop_beats = 0
        self.master_track = None

        self.master_synth = fluidsynth.Synth()
        self.gain = 0.4
        self.master_synth.setting("synth.gain", self.gain)
        self.master_synth.setting("audio.periods", 8)
        self.master_synth.setting("audio.period-size", 512)
        #double check the actual sample rate of the sf2 files, and set it here to avoid any resampling artifacts. If the sf2 files are 44100, set this to 44100. If they are 48000, set this to 48000.
        #self.master_synth.setting("synth.sample-rate", 48000.0)
        self.master_synth.setting("synth.sample-rate", 44100.0)
        self.master_synth.start(driver="wasapi") 
        self.master_synth.setting("midi.driver", "none")
        self.master_synth.setting("midi.autoconnect", 0)

        #channel 0 is removed to avoid dluidsynth listening to the input channel and causing duplicated channels
        self.available_channels = [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15]

        self.master_synth.cc(0, 7, 0)  # Master Volume = 0
        self.master_synth.cc(0, 11, 0) # Expression = 0
        
        self.metronome = Metronome(synth=self.master_synth)

        self.midi_mapping = self.DEFAULT_MIDI_MAPPING.copy()

    def add_track(self, name: str):
        if not self.available_channels: return
        assigned_channel = self.available_channels.pop(0)
        track = Track(name, synth=self.master_synth, channel=assigned_channel)
        track.initialize_synth()  
        track.is_armed = (len(self.tracks) == 0)  
        self.tracks.append(track)
        
    def get_armed_track(self):
        for track in self.tracks:
            if track.is_armed: return track 
        return None
    
    def save_project(self, path: str):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        if path is None:
                path = f"project_{timestamp}"
        base_dir = os.path.abspath(".") 
        # 2. Create a specific 'Saves' folder
        save_dir = os.path.join(base_dir, "Saves")
        os.makedirs(save_dir, exist_ok=True) # Creates the folder if it doesn't exist
        
        # 3. Create the full absolute path
        full_save_path = os.path.join(save_dir, path)

        project_folder = os.path.join(base_dir, "Saves", f"project_{timestamp}")
                
        # 2. Create the folder (this prevents the Errno 2 crash)
        os.makedirs(project_folder, exist_ok=True)

        for track in self.tracks:
            full_path = os.path.join(project_folder, f"{track.name}.mid")
            track.export_to_midi(full_path, self.bpm, self.master_loop_beats)

    def set_gain(self, gain: float):
        self.gain = gain
        self.master_synth.setting("synth.gain", self.gain)