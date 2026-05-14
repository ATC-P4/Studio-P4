from enum import Enum, auto

import os
import mido
import time
from typing import Callable
import threading

# enable class type checking

from core.engine import MasterClockEngine
from core.models import Project
from core.utils import EventBus, EventType

class MidiIO:

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
        1: "VOLUME_ROLLER",
        114: "REFRESH_AUDIO",

        # Add any other defaults here!
        # knobs 70-77
    }
    
    """
    Manages the MIDI input port, routes commands to the API, 
    and routes live musical notes to the Synthesizer.
    """
    def __init__(self, project : Project, engine : MasterClockEngine, event_bus: EventBus, on_command_cb=None):
        self.project: Project = project
        self.engine: MasterClockEngine = engine
        self.on_command_cb = on_command_cb  # This is your main trigger to the API
        self.inport = None
        self.joystick = JoystickMapper()
        self._event_bus = event_bus

        self._is_monitoring = False
        self._target_hints = ["iPad", "MPK mini", "LoopBe", "IAC"] # TODO: this severely limits the input options to the app

    def start(self, port_name: str|None=None) -> None:
        """
        start the mido thread to read incoming midi messages from port_name and execute on_midi_callback on them.

        Args:
            port_name (str | None, optional): The name of the MIDI input port to open. Defaults to None.
        """
        try:
            self.inport = mido.open_input(port_name, callback=self.on_midi_callback)
            print(f"MidiIO Connected: Listening to '{self.inport.name}'")
        except Exception as e:
            print(f"CRITICAL MidiIO Error: Could not open MIDI port. {e}")
            print("Available ports are:", mido.get_input_names())

    def start_auto_connection(self):
        """Start the periodic verification thread (hot-plugging)."""
        if not self._is_monitoring:
            self._is_monitoring = True
            threading.Thread(target=self._monitor_loop, daemon=True).start()
            print("[MidiIO] Starting automatic keyboard search...")

    def _monitor_loop(self):
        """A background thread that checks the ports every 2 seconds."""
        while self._is_monitoring:
            available_ports: list[str] = mido.get_input_names()
            
            # 1. Handling a disconnection (if the cable is pulled out)
            if self.inport and self.inport.name not in available_ports:
                print(f"[MidiIO] Clavier déconnecté : {self.inport.name}")
                self._event_bus.emit(EventType.MIDI_DISC, self.inport.name)
                self.inport.close()
                self.inport = None
                
            # 2. Manage the connection (if a keyboard is connected)
            if not self.inport:
                for port in available_ports:
                    for hint in self._target_hints:
                        if hint in port and "MIDIIN" not in port:
                            self.start(port)
                            self._event_bus.emit(EventType.MIDI_UPD, port)
                            break 
                    if self.inport:
                        break 
                        
            time.sleep(2)

    def stop(self) -> None:
        """Properly close the connection when the app is closed."""
        self._is_monitoring = False
        if self.inport:
            self.inport.close()
            print("MidiIO Disconnected.")
            
    def on_midi_callback(self, msg) -> None:
        """
        Callback function for handling incoming MIDI messages. 
        Routes commands to the API and handles routing live note playback and recording to specific subfunctions.


        Args:
            msg (mido.Message): The incoming MIDI message.
        """
        # print(f"[MidiIO] Received MIDI message: {msg}")
        if msg.type == 'control_change':
            action = self.DEFAULT_MIDI_MAPPING.get(msg.control)
            #print(f"Checking MIDI CC {msg.control} for mapped action: {action}")
            if action:
                self.handle_command(action, msg)

        # ---  LIVE PLAYBACK & RECORDING  ---
        #TODO: handle midi messages that aren't note_on/off or control_change (e.g. pitch bend, aftertouch, etc.)
        if msg.type not in ['note_on', 'note_off']:
            return 

        armed_track = self.project.get_armed_track()
        if armed_track:
            if msg.type == "note_on" and msg.velocity > 0:
                # print(f"Playing note {msg.note} with velocity {msg.velocity} on track '{armed_track.name}'")
                armed_track.play_note_on(msg.note, msg.velocity)
            else:
                armed_track.play_note_off(msg.note)

            if self.engine.current_state == "RECORDING":
                timestamp = time.perf_counter() - self.engine.start_time
                armed_track.add_midi_event(msg, timestamp)

        

    def handle_command(self, action: str, msg) -> None:
        """
        This function is called when a midi control message is recognized, routs to the specific handlers.
        Contains the track Volume change logic.

        Args:
            action (str): The abstract action string mapped from the MIDI control (e.g. "RECORD_TOGGLE", "NAV_LEFT", etc.)
            msg (mido.Message): The incoming MIDI message.
        """
        if self.on_command_cb:
            if action == "VOLUME_ROLLER":
                self.on_command_cb(action, value=msg.value)
                return
            elif action in ["NAV_LEFT", "NAV_DOWN", "NAV_RIGHT", "NAV_UP"]:
                process = self.joystick.process(msg, action)
                if process:
                    if self.on_command_cb: self.on_command_cb(process)
                return
            else:
                print(f"MidiIO recognized command: {action} from MIDI message: {msg}")
                self.on_command_cb(action)


class JoystickMapper:
    """
    Translates a 2-direction MIDI joystick (0-127 per axis) into UI navigation.
    Hardware constraint: Only registers LEFT (CC 2) and DOWN (CC 12).
    """
    def __init__(self):

        # Threshold to trigger the action (prevents accidental nudges)
        self.threshold = 100 
        
        # State tracking to prevent spamming the command while held down
        self.active_states = {} # e.g. {"NAV_LEFT": False, "NAV_DOWN": False} - True means the joystick is currently in that position

    def process(self, msg , action: str) -> str | None:
        """
        Transform the continous stream of input from the joystick in a toggle command

        Args:
            msg (mido.Message): Message from the MIDI port (should be a control_change)
            action (str): The abstract action this joystick movement corresponds to (e.g. "NAV_LEFT", "NAV_DOWN")

        Returns:
            str | None: The action to trigger if the joystick crossed the threshold, or None if no action should be taken.
        """
        if msg.type != 'control_change':
            return None
        
        is_active = msg.value > self.threshold
        
        # Look up the previous state for this action (defaults to False)
        was_active = self.active_states.get(action, False)
        
        # If the state crossed the threshold in either direction
        if is_active != was_active:
            self.active_states[action] = is_active # Save the new state
            
            if is_active:
                return action
                
        return None
    
class NavMode(Enum):
    """
    Enumeration for joystick navigation modes. Determines whether the joystick is currently controlling track selection or instrument selection.
    """
    TRACK = auto()
    GROUP = auto() 
    INSTRUMENT = auto()

class BoundaryState(Enum):
    """States for track list boundaries."""
    TOP = auto()
    BOTTOM = auto()
    NORMAL = auto()

class MidiInputRouter:
    """
    This class is responsible for routing incoming MIDI commands from the AudioIO to the appropriate API methods.
    It acts as a central dispatcher, translating raw MIDI input into high-level actions that the LooperAPI can execute.
    """
    def __init__(self, api):
        self.api = api
        self.project = api.project
        self.event_bus: EventBus = api.events
        # Track what the joystick is currently controlling
        self.nav_mode = NavMode.TRACK 

        self._action_map = {
            "TOGGLE_RECORD": self.api.toggle_record,
            "TOGGLE_PLAY": self.api.toggle_playback,
            "TOGGLE_METRONOME": lambda: self.api.toggle_metronome(),
            "BPM_UP": lambda: self.api.adjust_bpm(4),
            "BPM_DOWN": lambda: self.api.adjust_bpm(-4),
            "VOLUME_ROLLER": lambda value: self.api.change_volume(value),  # Volume changes are handled directly in the handle_midi_action method to avoid log spam, but you could add voice feedback or a UI update here if desired.
        }

        # The Navigation Matrix
        self._nav_matrix = {
            NavMode.TRACK: {
                "NAV_UP": lambda: self.cycle_armed_track(1),
                "NAV_DOWN": lambda: self.cycle_armed_track(-1),
                "NAV_LEFT": self.api._toggle_armed_track_mute,
                "NAV_RIGHT": self._set_nav_mode(NavMode.GROUP, "Mode groupe"),
            },
            NavMode.GROUP: {
                "NAV_UP": lambda: self.cycle_group(1),
                "NAV_DOWN": lambda: self.cycle_group(-1),
                "NAV_LEFT": self._set_nav_mode(NavMode.TRACK, "Mode piste"),
                "NAV_RIGHT": self._set_nav_mode(NavMode.INSTRUMENT, "Mode instrument"),
            },
            NavMode.INSTRUMENT: {
                "NAV_UP": lambda: self.cycle_instrument(1),
                "NAV_DOWN": lambda: self.cycle_instrument(-1),
                "NAV_LEFT": self._set_nav_mode(NavMode.GROUP, "Mode groupe"),
                "NAV_RIGHT": lambda: None, 
            }
        }
        # Track the last edge state for the double-tap actions on the joystick (save project and add track)
        self._pending_edge = None 
        
        # 3. Track Boundary Matrix
        self._edge_handlers = {
            BoundaryState.TOP: self._handle_top_edge,
            BoundaryState.BOTTOM: self._handle_bottom_edge,
            BoundaryState.NORMAL: self._handle_normal_nav
        }

    def route_command(self, command: str) -> None:
        """
        Routes a given MIDI command string to the corresponding API method.

        Args:
            command (str): The MIDI command identifier to route.
        """
        print(f"[MIDI Router] Received command: {command}")
        self.handle_midi_action(command)

    
    def _set_nav_mode(self, mode: NavMode, voice_announcement: str) -> Callable[[], None]:
        """
        Function that return a function that change the NavMode and announce it,
        used in the handle_midi_action

        Args:
            mode (NavMode): State as an object of the class NavMode
            voice_announcement (str): Message for the voice annoucement

        Returns:
            Callable[[], None]: A callable function that transitions to the specified navigation mode.
        """
        def transition():
            self._pending_edge = None # Clear any pending edge state when switching modes to prevent accidental triggers
            self.nav_mode = mode
            print(f"[API] Joystick Mode: {mode.name} CYCLE")
            self.event_bus.emit(EventType.GENERAL, message=voice_announcement) # TODO: voice
            if mode.name == "TRACK":
                armed_track = self.project.get_armed_track()
                if armed_track:
                    self.event_bus.emit(EventType.GENERAL, message=f"{armed_track.name}") # TODO: voice
            if mode.name == "INSTRUMENT":
                armed_track = self.project.get_armed_track()
                if armed_track:
                    current_instrument_name = os.path.basename(armed_track.sf2_path).replace(".sf2", "").replace("_", " ")
                    self.event_bus.emit(EventType.GENERAL, message=f"{current_instrument_name}") # TODO: voice
            if mode.name == "GROUP":
                armed_track = self.project.get_armed_track()
                if armed_track:
                    current_sf2 = armed_track.sf2_path
                    instruments_dict = self.api._available_instruments
                    for group_name, sf2_list in instruments_dict.items():
                        if current_sf2 in sf2_list:
                            self.event_bus.emit(EventType.GENERAL, message=f"{group_name}") # TODO: voice
                            break
        return transition
    

    
    def cycle_armed_track(self, direction: int = 1) -> None:
        """
        Cycles the armed status, delegating edge-cases to the boundary map.
        Args:
            direction (int, optional): 1 for down, -1 for up. Defaults to 1.
        """
        tracks = self.project.tracks
        if not tracks: 
            return

        current_idx = next((i for i, t in enumerate(tracks) if t.is_armed), 0)
        target_idx = current_idx - direction

        # 1. Resolve the math into a simple state string
        if target_idx < 0:
            boundary_state = BoundaryState.TOP
        elif target_idx >= len(tracks):
            boundary_state = BoundaryState.BOTTOM
        else:
            boundary_state = BoundaryState.NORMAL

        # 2. Route to the handler (O(1) lookup) to get the final index to arm
        final_idx = self._edge_handlers[boundary_state](tracks, target_idx)
        
        # 3. Apply the change
        if current_idx != final_idx:
            self.api.arm_track(final_idx)

    
    def _handle_top_edge(self, tracks: list, target_idx: int) -> int:
        """
        Handles double-tap to save project.
        The first time the user tries to navigate up while the first track is armed,
        it will set a pending edge state and prompt the user to tap again to confirm. 
        If the user does tap up again, it will trigger the save action and clear the pending state. 
        If the user navigates in any other way, it will clear the pending state to prevent accidental triggers later on.
        
        Args:
            tracks (list): List of tracks in the project, used to get the name for voice feedback.
            target_idx (int): The index that the user is trying to navigate to, used to determine if we are at the edge or not.
        Returns:
            int: The index of the track to be armed.
        """
        if self._pending_edge == BoundaryState.TOP:
            self.api.saveproject_to_disk()
            self.event_bus.emit(EventType.PROJ_SAVED)
            self._pending_edge = None
        else:
            self.event_bus.emit(EventType.GENERAL, message="Appuyez à nouveau vers le haut pour sauvegarder") # TODOß
            self._pending_edge = BoundaryState.TOP
        
        return 0  # Always keep index at 0 (the top)

    def _handle_bottom_edge(self, tracks: list, target_idx: int) -> int:
        """Handles double-tap to add a new track."""
        if self._pending_edge == BoundaryState.BOTTOM:
            new_track_num = len(tracks) + 1
            self.api.add_track(f"Track {new_track_num}")
            self.event_bus.emit(EventType.GENERAL, message=f"Nouvelle piste ajoutée: Track {new_track_num}") # TODO: voice
            self._pending_edge = None
            # Return the new length - 1 so the newly created track is armed
            return len(self.project.tracks) - 1 
        else:
            self.event_bus.emit(EventType.GENERAL, message="Appuyez vers le bas à nouveau pour ajouter une piste") # TODO: voice
            self._pending_edge = BoundaryState.BOTTOM
            
        return len(tracks) - 1 # Keep index at the bottom

    def _handle_normal_nav(self, tracks: list, target_idx: int) -> int:
        """
        Handles standard navigation in the middle of the track list.
        
        Args:
            tracks (list): List of tracks in the project, used to get the name for voice feedback.
            target_idx (int): The index that the user is trying to navigate to, used to determine which track to arm.
        Returns:
            int: The index of the track to be armed.
        """
        self._pending_edge = None # Instantly clear any pending double-taps
        
        return target_idx

    def _get_current_group_and_list(self, armed_track):
        """Helper to figure out which group the current track is using."""
        instruments_dict = self.api._available_instruments
        current_sf2 = armed_track.sf2_path
        
        for group_name, sf2_list in instruments_dict.items():
            if current_sf2 in sf2_list:
                return group_name, sf2_list
        # Fallback if somehow not found
        first_group = list(instruments_dict.keys())[0]
        return first_group, instruments_dict[first_group]

    def cycle_group(self, direction: int) -> None:
        """Cycles the folder category and auto-loads the first instrument in that folder."""
        armed_track = self.project.get_armed_track()
        if not armed_track: return

        instruments_dict = self.api._available_instruments
        groups = list(instruments_dict.keys())
        if not groups: return

        current_group, _ = self._get_current_group_and_list(armed_track)
        
        current_idx = groups.index(current_group)
        next_idx = (current_idx - direction) % len(groups)
        next_group = groups[next_idx]
        
        # Auto-load the first instrument of the new group
        next_instrument = instruments_dict[next_group][0]
        armed_track.set_soundfont(next_instrument)
        
        self.event_bus.emit(EventType.GENERAL, message=f"{next_group}") # TODO: voice
        if self.api._ui_callback: self.api._ui_callback()

    def cycle_instrument(self, direction: int) -> None:
        """
        Cycles the instrument of the currently armed track.
        Args:
            direction (int): 1 for next instrument, -1 for previous instrument.
        Returns:
            None
        """
        armed_track = self.project.get_armed_track()
        if not armed_track: return

        _, current_group_list = self._get_current_group_and_list(armed_track)
        current_sf2 = armed_track.sf2_path

        try:
            current_idx = current_group_list.index(current_sf2)
        except ValueError:
            current_idx = 0

        next_idx = (current_idx - direction) % len(current_group_list)
        next_instrument = current_group_list[next_idx]

        armed_track.set_soundfont(next_instrument)
        
        # Clean up the name for the voice (e.g., "basic_piano.sf2" -> "basic piano")
        clean_name = os.path.basename(next_instrument).replace(".sf2", "").replace("_", " ")
        self.event_bus.emit(EventType.GENERAL, message=f"Instrument: {clean_name}") # TODO: voice
        
        if self.api._ui_callback: self.api._ui_callback()

    def handle_midi_action(self, action: str, value: int|None=None) -> None:
        """
        Central dispatcher for all mapped MIDI commands. 
        The function called depending on the action are mapped in the init variable of the class LooperAPI.

        Args:
            action (str): String describing a specific action.
            value (int | None): The MIDI value associated with the action. (ex. volume)
        """
        # use the action map for simple commands
        if handler := self._action_map.get(action):
            if action == "VOLUME_ROLLER" and value is not None:
                handler(value)  # Pass the MIDI value for volume changes
            else:
                handler()
            return
    
        # 2. Fallback to executing as a Navigation Action
        if handler := self._nav_matrix[self.nav_mode].get(action):
            handler()