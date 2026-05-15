import sys
import os
import mido
from typing import Callable, Any, Dict, List,TYPE_CHECKING
from enum import Enum


if TYPE_CHECKING:
    from core.models import Track



def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS # type: ignore
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_sf2_filename(path):
    return os.path.basename(path)

def get_sf2_display_name(path):
    return get_sf2_filename(path).replace(".sf2", "").title().replace("_", " ")

def get_sf2_dir():
    return os.path.join(os.path.abspath("."),("sf2")) 





def get_available_instruments() -> dict:
    """Scans the sf2 directory and returns a dictionary grouped by folder."""

    base_dir = get_sf2_dir()
    print(base_dir)

    instruments = {}
    
    if not os.path.exists(base_dir):
        # print("[get_available_instruments] No instruments found")
        os.makedirs(base_dir)
        return instruments

    for item in os.listdir(base_dir):
        # FIX 3: Normalize the parent path
        item_path = os.path.normpath(os.path.join(base_dir, item))
        
        if os.path.isdir(item_path):
            # FIX 4: Normalize every file path in the subfolders
            sf2_files = [os.path.normpath(os.path.join(item_path, f)) 
                         for f in os.listdir(item_path) if f.endswith('.sf2')]
            if sf2_files:
                instruments[item] = sf2_files
                
        elif item.endswith('.sf2'):
            if "Général" not in instruments:
                instruments["Général"] = []
            instruments["Général"].append(item_path)

    # print(f"[get_available_instruments] Found: {len(instruments)} instruments in: {base_dir}")
            
    return instruments

def get_default_instrument(available_instruments = get_available_instruments()): # return the first instrument in the dict. pretty much a random selection.
    return next(iter(available_instruments.values()))[0]

class MidiExporter:
    """Handles the conversion of internal Track data into standard .mid files on disk."""

    @staticmethod
    def export_track(track: 'Track', filepath: str, bpm: int, master_loop_beats: int, ticks_per_beat: int = 480) -> None:
        """
        Calculates delta ticks and writes a Track's event history to a physical MIDI file,
        padding the end to ensure it perfectly loops in a DAW.
        """
        print(f"[EXPORTER] Writing track '{track.name}' to: {filepath}")
        
        mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
        midi_track = mido.MidiTrack()
        mid.tracks.append(midi_track)
        
        tempo = mido.bpm2tempo(bpm)
        
        # 1. Initialization Messages
        midi_track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
        midi_track.append(mido.Message('program_change', channel=track.channel, program=track.program_id, time=0))
        
        # 2. Time Conversion & Event Writing
        sorted_events = sorted(track.midi_events, key=lambda x: x[1])
        last_time = 0.0
        
        for msg, timestamp in sorted_events:
            timestamp = max(0.0, timestamp)
            delta_seconds = timestamp - last_time
            last_time = timestamp
            
            delta_ticks = int(round(mido.second2tick(delta_seconds, ticks_per_beat, tempo)))
            midi_msg = msg.copy(channel=track.channel, time=delta_ticks)
            midi_track.append(midi_msg)
            
        # 3. Master Loop Padding
        total_loop_seconds = master_loop_beats * (60.0 / bpm)
        remaining_seconds = total_loop_seconds - last_time
        
        if remaining_seconds > 0:
            padding_ticks = int(round(mido.second2tick(remaining_seconds, ticks_per_beat, tempo)))
            midi_track.append(mido.MetaMessage('end_of_track', time=padding_ticks))
            
        # 4. Safe Disk I/O
        try:
            mid.save(filepath)
            print(f"[EXPORTER] Successfully exported: {filepath}")
        except Exception as e:
            print(f"[EXPORTER] ERROR writing MIDI to disk: {e}")


class EventType(Enum):
    TRACK_SELECT = 0
    PROJ_SAVED = 1
    METR_TOGGLE = 2
    BPM_MOD = 3
    REC_STOP = 4
    TRACK_MUTE = 5
    STAT_REQ = 6
    ERR = 7
    PROJ_LOAD = 8
    MIDI_DISC = 9
    MIDI_UPD = 10
    GR_SEL = 11 # Announces group mode + selected group name
    INSTR_SEL = 12
    SAVE_HINT = 13
    TR_HINT = 14
    TR_ADD = 15
    GR_NAME = 16 # Announces just the selected group name

    

class EventBus:
    """A lightweight publisher/subscriber router for decoupled backend communication."""
    
    def __init__(self):
        # Maps event string names to a list of callback functions
        self._subscribers: Dict[EventType, List[Callable]] = {}

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Adds a listener for a specific event."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def emit(self, event_type: EventType, *args: Any, **kwargs: Any) -> bool:
        """Triggers all callbacks listening to this event type."""
        called = False
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                callback(*args, **kwargs)
                called = True
        return called