import sys
import os
from typing import Callable, Any, Dict, List


def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_available_instruments() -> list[str]:
        """
        Scans the sf2 directory and returns a list of filenames.

        Returns:
            list[str]: List of file names with a .sf2 format
        """
        sf2_dir = get_resource_path("sf2")
        if not os.path.exists(sf2_dir):
            #TODO: implement an Import sf2 error
            return ["basic_piano.sf2"] # Fallback if folder is missing
            
        # Get all .sf2 files, excluding the metronome so it doesn't show in the UI list
        files = [f for f in os.listdir(sf2_dir) if f.endswith('.sf2') and "Metronom" not in f]
        return files

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