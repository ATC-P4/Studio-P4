from core.project_io import ProjectIO

from typing import TYPE_CHECKING

from core.utils import EventType

# enable class type checking
if TYPE_CHECKING:
    from core.engine import MasterClockEngine
    from core.models import Project
    from core.utils import EventBus
    

class LooperAPI:
    def __init__(self, engine : 'MasterClockEngine', project : 'Project', available_instruments, ui_callback, event_bus : 'EventBus'):
        """
        Stores the backend instances so the API can route commands to them.
        the ui_callback is a function that will be called after every state change to update the UI.
        """
        self._engine = engine
        self.project = project
        self._ui_callback = ui_callback
        self._available_instruments = available_instruments
        self._engine.on_state_change_cb = self._ui_callback # Link the engine's state change callback to the API's ui_callback
        self.events = event_bus

    # Main toggle functions 
    def toggle_record(self) -> None:
        """ 
        Toggle between the states Recording and Stopped, starting or stopping the recording. 
        """
        now = self._engine.current_state
        if now in ["RECORDING", "COUNT_IN"]:
            self._engine.set_state("STOPPED") # Cancel recording or count-in

            # Trigger voice on record toggle
            self.events.emit(EventType.REC_STOP)  
        else:
            # If STOPPED or PLAYING, start the record sequence
            self._engine.set_state("COUNT_IN")
        self._ui_callback()

    def toggle_playback(self) -> None:
        """
        Toggle between the states Playing and Stopped, starting or stopping the playback.
        """
        if self._engine.current_state == "PLAYING":
            self._engine.set_state("STOPPED")
        else:
            self._engine.set_state("PLAYING")
        self._ui_callback()

    def toggle_metronome(self) -> None:
        """
        Toggles the metronome on or off.
        """
        current_state = self._engine.get_metronome_state()
        self._engine.set_metronome_state(not current_state)
        self._ui_callback()

        # Trigger voice on metronome change
        self.events.emit(EventType.METR_TOGGLE, is_on=not current_state)

    def mute_track(self, track_id: int, state: bool) -> None:
        """
        Mute a track using the specific track_id and specific state

        Args:
            track_id (int): Track identifier
            state (bool): state to set track.is_muted
        """
        track = self.project.tracks[track_id]
        track.is_muted = state
        if state:
            track.flush_notes()  # Stop any currently playing notes immediately, handles the drone issue when muting.
        self.events.emit(EventType.TRACK_MUTE, track_name=track.name, is_muted=track.is_muted)
        self._ui_callback()

    def _toggle_armed_track_mute(self) -> None:
        """
        Toggle the mute state of the armed track.
        """
        armed_track = self.project.get_armed_track()
        if not armed_track: return
        
        track_index = self.project.tracks.index(armed_track)
        self.mute_track(track_index, not armed_track.is_muted)
        print("Nav left - toggling mute on armed track")

    def add_track(self, name: str) -> None:
        """
        Adds a new track to the project with the given name.
        """
        self.project.add_track(name)
        self._ui_callback()

    def arm_track(self, track_id: int) -> None:
        """
        Arm a specific track based on a track identifier.

        Args:
            track_id (int): track identifier
        """
        for i, track in enumerate(self.project.tracks):
            if track.is_armed and i != track_id:
                track.flush_notes()  # Stop any currently playing notes immediately, handles the drone issue when switching armed tracks.
            track.is_armed = (i == track_id)
        #print(f"[API] Track {track_id} is now exclusively armed.")
        self.events.emit(EventType.TRACK_SELECT, name=self.project.tracks[track_id].name)
        self._ui_callback()

    def set_soundfont_instrument(self, track_id: int, program_id: int) -> None:
        """
        -----WIP-----
        Function to change the program_id used by fluidsynth to play the loded soundfont.
        Depending on the sound font this action can change instrument.

        Args:
            track_id (int): Track identifier
            program_id (int): Program identifier
        """
        track = self.project.tracks[track_id]
        track.set_instrument(program_id)
        #print(f"[API] Track {track_id} is now using instrument {program_id}.")
        self._ui_callback()

    def set_track_soundfont(self, track_id: int, sf2_path: str) -> None:
        """
        Function to set a specific sound font, defined with a path, to a specific track using an identifier.

        Args:
            track_id (int): Track identifier
            sf2_path (str): SoundFont path
        """
        track = self.project.tracks[track_id]
        track.set_soundfont(sf2_path)
        self._ui_callback()

    def get_state_dto(self) -> dict:
        """
        Constructs a "dumb" dictionary representing the entire state of the application.
        The UI calls this whenever the ui_callback alerts it that a change happened.

        Returns:
            dict: dictionary containing the application state variables
        """
        return {
            "current_state": self._engine.current_state,
            "bpm": self.project.bpm,
            "time_signature": self.project.time_signature,
            "metronome_on": self._engine.metronome_on,
            "available_instruments": self._available_instruments, # Now a dictionary!
            "is_quitting": getattr(self, "is_quitting", False),
            "tracks": [
                {
                    "id": i,
                    "name": track.name,
                    "is_muted": track.is_muted,
                    "is_armed": track.is_armed,
                    "program_id": track.program_id,
                    "sf2_path": track.sf2_path # <-- NEW: Add the path here
                }
                for i, track in enumerate(self.project.tracks)
            ]
        }
    
   
    def speak_info(self) -> None:
        """
        Announces current status, specifically the BPM and metronome state, using the voice service.
        """
        metronome_status = "activé" if self._engine.metronome_on else "désactivé"
        bpm = self.project.bpm
        self.events.emit(EventType.STAT_REQ, metronome_status=metronome_status, bpm=bpm)


    def adjust_bpm(self, delta: int) -> None:
        """
        Function to adjust the bpm by a specific delta ammount and update the variables correlated to the bpm.
        The change will be annpounced.

        Args:
            delta (int): Ammount to change the bpm, can be positive or negative.
        """
        new_bpm = self.project.bpm + delta
        if 10 <= new_bpm <= 400:
            self.project.bpm = new_bpm
            self.project.beat_duration = 60.0 / new_bpm
            
            # If you added the voice service:
            self.events.emit(EventType.BPM_MOD, bpm=new_bpm)
            self._ui_callback()
    
    def change_volume(self, value: int) -> None:
        armed_track = self.project.get_armed_track()
        if armed_track:
            # kwargs.get("value") holds the 0-127 midi value
            armed_track.set_volume(value)
    
    def saveproject_to_disk(self, folder_name: str | None = None) -> None:
        """Delegates saving to the IO service and notifies the user."""
        try:
            ProjectIO.save(self.project, folder_name)
            self.events.emit(EventType.PROJ_SAVED)
        except Exception as e:
            print(f"Save failed: {e}")
            self.events.emit(EventType.ERR, error="Erreur de sauvegarde")

    def load_project_from_disk(self, folder_path: str) -> None:
        """Safely stops the engine, loads new data, and redraws the UI."""
        # 1. Stop the engine completely to release locks on MIDI events
        self._engine.set_state("STOPPED")
        
        try:
            # 2. Rebuild the project in place
            ProjectIO.load_into_project(self.project, folder_path)
            
            # 3. Update the engine's beat calculations
            self.project.beat_duration = 60.0 / self.project.bpm
            
            # 4. Force UI Redraw
            self._ui_callback()
            self.events.emit(EventType.PROJ_LOAD, message=f"Projet {self.project.name} chargé")
            
        except Exception as e:
            print(f"Failed to load project: {e}")
            self.events.emit(EventType.ERR, error="Erreur de chargement")
