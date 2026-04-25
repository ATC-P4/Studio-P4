import os

from core.voice import VoiceType
from core.utils import get_resource_path

class LooperAPI:
    def __init__(self, engine, project, audio_io, voice_service, ui_callback):
        """
        Stores the backend instances so the API can route commands to them.
        the ui_callback is a function that will be called after every state change to update the UI.
        """
        self._engine = engine
        self._project = project
        self._audio_io = audio_io
        self._voice = voice_service  
        self._ui_callback = ui_callback
        self._available_instruments = self.get_available_instruments()
        self._engine.on_state_change_cb = self._ui_callback # Link the engine's state change callback to the API's ui_callback
        # Track what the joystick is currently controlling
        self.nav_mode = "TRACK" # Can be "TRACK" or "INSTRUMENT" 
         # Keeps track if the position of the armed track is at an edge(first or last track) to trigger extra function
        self.at_edge = {"TOP_EDGE": False, "BOTTOM_EDGE": False} # can contain TOP_EDGE: true/false and BOTTOM_EDGE: true/false to indicate if the currently armed track is at an edge of the track list. 
        # to trigger specific actions when the user goes twice over the edge (eg. if the user tries to go "down" while the last track is armed, first we put BOTTOM_EDGE = True, and if the user does it again, we can interpret that as a desire to add a new track and arm it, instead of just doing nothing)
   
    # Main toggle functions 
    def toggle_record(self):
        """
        Initiates the recording sequence (which includes the count-in).
        """
        now = self._engine.current_state
        if now in ["RECORDING", "COUNT_IN"]:
            self._engine.set_state("STOPPED") # Cancel recording or count-in

            # Trigger voice on record toggle
            self._voice.speak(VoiceType.REC_STOP, "Enregistrement arrêté.")
        else:
            # If STOPPED or PLAYING, start the record sequence
            self._engine.set_state("COUNT_IN")

        self._ui_callback()

    def toggle_playback(self):
        """
        Starts or stops the main clock engine.
        """
        if self._engine.current_state == "PLAYING":
            self._engine.set_state("STOPPED")
        else:
            self._engine.set_state("PLAYING")
        self._ui_callback()

    def toggle_metronome(self, state: bool):
        """
       Turns the metronome track on or off.
        """
        self._engine.set_metronome_state(state)
        self._ui_callback()

        # Trigger voice on metronome change
        msg = "Metronome On" if state else "Metronome Off"
        self._voice.speak(VoiceType.METR_TOGGLE, msg)

    # Track manipulation functions
    def mute_track(self, track_id: int, state: bool):
        """
        Mutes or unmutes a specific track and prevents the "infinite drone" bug.
        """
        track = self._project.tracks[track_id]
        track.is_muted = state
        if state:
            track.flush_notes()  # Stop any currently playing notes immediately, handles the drone issue when muting.
        self._ui_callback()

    def add_track(self, name: str):
        """
        Adds a new track to the project with the given name.
        """
        self._project.add_track(name)
        self._ui_callback()

    def arm_track(self, track_id: int):
        """
        Selects which track receives live MIDI input from the keyboard. Only one track can be armed at a time.
        """ 
        for i, track in enumerate(self._project.tracks):
            if track.is_armed and i != track_id:
                track.flush_notes()  # Stop any currently playing notes immediately, handles the drone issue when switching armed tracks.
            track.is_armed = (i == track_id)
        print(f"[API] Track {track_id} is now exclusively armed.")
        self._ui_callback()

    def set_track_instrument(self, track_id: int, program_id: int):
        """
        Changes the MIDI instrument patch for a specific track.
        """
        track = self._project.tracks[track_id]
        track.set_instrument(program_id)
        print(f"[API] Track {track_id} is now using instrument {program_id}.")
        self._ui_callback()

    def set_track_soundfont(self, track_id: int, sf2_path: str):
        """
        Changes the MIDI soundfont for a specific track.
        """
        track = self._project.tracks[track_id]
        track.set_soundfont(sf2_path)
        self._ui_callback()

    def get_available_instruments(self):
        """Scans the sf2 directory and returns a list of filenames."""
        # sf2_dir = "sf2"
        sf2_dir = get_resource_path("sf2")
        if not os.path.exists(sf2_dir):
            return ["basic_piano.sf2"] # Fallback if folder is missing
            
        # Get all .sf2 files, excluding the metronome so it doesn't show in the UI list
        files = [f for f in os.listdir(sf2_dir) if f.endswith('.sf2') and "Metronom" not in f]
        return files

    def get_state_dto(self):
        """
        Constructs a "dumb" dictionary representing the entire state of the application.
        The UI calls this whenever the ui_callback alerts it that a change happened.
        """
        return {
            "current_state": self._engine.current_state,
            "bpm": self._project.bpm,
            "time_signature": self._project.time_signature,
            "metronome_on": self._engine.metronome_on,
            "available_instruments": self.get_available_instruments(),
            "tracks": [
                {
                    "id": i,
                    "name": track.name,
                    "is_muted": track.is_muted,
                    "is_armed": track.is_armed,
                    "program_id": track.program_id
                }
                for i, track in enumerate(self._project.tracks)
            ]
        }
    
    def save_project_to_disk(self, path: str|None = None):
        """
        Saves the current project state to disk. The directory_path is where the MIDI files will be saved.
        """
        self._project.save_project(path)
        # Optionally, you could trigger a UI update here to show a "Saved Successfully" message or similar.
        # self._ui_callback()

    def speak_info(self):
        """Announces current status."""
        metronome_status = "activé" if self._engine.metronome_on else "désactivé"
        self._voice.speak(VoiceType.METR_INFO, f"Métronome actuellement {metronome_status}.")
        self._voice.speak(VoiceType.BPM_INFO, f"B P M actuel: {self._project.bpm}")

    # Add inside LooperAPI class in core/api.py:

    def handle_midi_action(self, action: str):
        """Central dispatcher for all mapped MIDI commands."""
        if action is not None and action != "VOLUME_ROLLER":  # Avoid spamming the logs with volume roller changes
            print(f"Received MIDI action: {action} at state {self.nav_mode}")

        if action == "TOGGLE_RECORD":
            self.toggle_record()

        elif action == "TOGGLE_PLAY" :
            self.toggle_playback()

        elif action == "TOGGLE_METRONOME":
            self.toggle_metronome(not self._engine.metronome_on)

        elif action == "BPM_UP":
            self.adjust_bpm(4)

        elif action == "BPM_DOWN":
            self.adjust_bpm(-4)

        elif action == "VOLUME_ROLLER":
            # announce the change
            # self._voice.speak(VoiceType.METR_INFO, f"Volume changé")
            # we could also trigger a UI update here if we had a visual indicator for gain, but for now we'll just rely on the voice feedback
            # self._ui_callback()
            pass

            # --- JOYSTICK STATE MACHINE ---
        elif action == "NAV_RIGHT" and self.nav_mode == "TRACK":
            self.nav_mode = "INSTRUMENT"
            print("[API] Joystick Mode: INSTRUMENT CYCLE")
            # announce the change
            self._voice.speak(VoiceType.METR_INFO, "Mode instrument")
            
        elif action == "NAV_LEFT" and self.nav_mode == "INSTRUMENT":
            self.nav_mode = "TRACK"
            print("[API] Joystick Mode: TRACK CYCLE")
            # announce the change
            self._voice.speak(VoiceType.METR_INFO, "Mode piste")

        
        elif action == "NAV_LEFT" and self.nav_mode == "TRACK":
            # toggle mute on the armed track
            #print(f"[API] NAV_LEFT received in TRACK mode - toggling mute on armed track")
            armed_track = self._project.get_armed_track()
            if armed_track:
                track_index = self._project.tracks.index(armed_track)
                self.mute_track(track_index, not armed_track.is_muted)
                # announce the change
                status = "muté" if armed_track.is_muted else "démuté"
                self._voice.speak(VoiceType.METR_INFO, f"{armed_track.name} {status}")
                # ui update will be triggered by mute_track method
            print("Nav left - toggling mute on armed track")

        elif action == "NAV_UP":
            if self.nav_mode == "TRACK":    
                self.cycle_armed_track(direction=1)
            elif self.nav_mode == "INSTRUMENT":
                self.cycle_instrument(direction=1)
            print("Nav up") 
        elif action == "NAV_DOWN":
            if self.nav_mode == "TRACK":    
                self.cycle_armed_track(direction=-1)
            elif self.nav_mode == "INSTRUMENT":
                self.cycle_instrument(direction=-1)
            print("Nav down")
        # Add any other dynamic or hardcoded actions here

    def adjust_bpm(self, delta: int):
        new_bpm = self._project.bpm + delta
        if 10 <= new_bpm <= 400:
            self._project.bpm = new_bpm
            self._engine.beat_duration = 60.0 / new_bpm
            
            # If you added the voice service:
            self._voice.speak(VoiceType.BPM_MOD, f"B P M {new_bpm}")
            self._ui_callback()

    def reset_midi_mapping(self):
        """Restores the MIDI mapping to the hardcoded factory defaults."""
        
        # Overwrite current mapping with a fresh copy of the defaults
        self._project.midi_mapping = self._project.DEFAULT_MIDI_MAPPING.copy()
        
        # Optional: Announce the reset via the voice service
        self._voice.speak(VoiceType.WELCOME, "Mapping reset to defaults.")
        self._ui_callback()
        print("[API] MIDI mapping has been reset to factory defaults.")

    def cycle_armed_track(self, direction: int = 1):
        """Cycles the armed status to the next track in the project."""
        tracks = self._project.tracks
        if not tracks:
            return

        current_armed_idx = 0
        for i, track in enumerate(tracks):
            if track.is_armed:
                current_armed_idx = i
                break

        # Calculate the next index 
        next_idx = (current_armed_idx - direction) 

        # --- Logic at the edges of the track list to trigger extra functions ---
        if next_idx < 0:
            next_idx = 0
            if self.at_edge.get("TOP_EDGE"):
                # User tried to go up while the first track is armed, interpret as a desire to save the project
                self.save_project_to_disk()
                self._voice.speak(VoiceType.METR_INFO, "Projet sauvegardé")
                self.at_edge["TOP_EDGE"] = False  # reset the edge state after saving
            else:
                #ask for confirmation to save the project if the user tries to go up while the first track is armed, by saying "you are at the first track, press again to save the project"
                self._voice.speak(VoiceType.METR_INFO, "Appuyez à nouveau ver l'haut pour sauvegarder le projet")
                self.at_edge["TOP_EDGE"] = True
                self.at_edge["BOTTOM_EDGE"] = False  # reset the opposite edge state just in case
            
        elif next_idx >= len(tracks):
            next_idx = len(tracks) - 1
            if self.at_edge.get("BOTTOM_EDGE"):
                # User tried to go down while the last track is armed, interpret as a desire to add a new track at the bottom and arm it
                self.add_track(f"Track {len(tracks)+1}")
                next_idx = len(tracks) - 1  # Arm the newly added track
                self._voice.speak(VoiceType.METR_INFO, f"Nouvelle piste ajoutée et armée: Track {len(tracks)}")
                self.at_edge["BOTTOM_EDGE"] = False  # reset the edge state after adding a track
            else:
                #ask for confirmation to add a new track if the user tries to go down while the last track is armed, by saying "you are at the last track, press again to add a new track"
                self._voice.speak(VoiceType.METR_INFO, f"Appuyez ver le bas à nouveau pour en ajouter une nouvelle")
                self.at_edge["BOTTOM_EDGE"] = True
                self.at_edge["TOP_EDGE"] = False  # reset the opposite edge state just in case
        else:
            # reset edge states if we're safely in the middle of the track list
            self.at_edge["TOP_EDGE"] = False
            self.at_edge["BOTTOM_EDGE"] = False
            self._voice.speak(VoiceType.METR_INFO, f"{tracks[next_idx].name} armé")
        
        self.arm_track(next_idx)
        self._ui_callback()

    def cycle_instrument(self, direction: int):
        """Cycles the instrument of the currently armed track."""
        armed_track = self._project.get_armed_track()
        if not armed_track: return
        
        instruments = self._available_instruments
        if not instruments: return

        # Extract just the filename to find its index in the available list
        current_filename = os.path.basename(armed_track.sf2_path)
        
        try:
            current_idx = instruments.index(current_filename)
        except ValueError:
            current_idx = 0
            
        next_idx = (current_idx + direction) % len(instruments)
        next_instrument = instruments[next_idx]
        
        # Set the new soundfont
        armed_track.set_soundfont(next_instrument)
        
        # Force the View to update the dropdown visually
        if self._ui_callback:
            self._ui_callback()