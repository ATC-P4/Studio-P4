import sys
import os
import mido
from typing import Callable, Any, Dict, List,TYPE_CHECKING


if TYPE_CHECKING:
    from core.models import Track



def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_available_instruments() -> dict:
    """Scans the sf2 directory and returns a dictionary grouped by folder."""
    base_dir = os.path.abspath("./sf2")
    instruments = {}
    
    if not os.path.exists(base_dir):
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
            
    return instruments

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

class EventBus:
    """A lightweight publisher/subscriber router for decoupled backend communication."""
    
    def __init__(self):
        # Maps event string names to a list of callback functions
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Adds a listener for a specific event."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def emit(self, event_type: str, *args: Any, **kwargs: Any) -> None:
        """Triggers all callbacks listening to this event type."""
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                callback(*args, **kwargs)