import mido
import time

class AudioIO:
    """
    Manages the MIDI input port, routes commands to the API, 
    and routes live musical notes to the Synthesizer.
    """
    def __init__(self, project, engine, on_command_cb=None):
        self.project = project
        self.engine = engine
        self.on_command_cb = on_command_cb  # This is your main trigger to the API
        self.inport = None
        self.joystick = JoystickMapper()

    def start(self, port_name=None):
        # ... (keep your existing start function) ...
        try:
            self.inport = mido.open_input(port_name, callback=self.on_midi_callback)
            print(f"AudioIO Connected: Listening to '{self.inport.name}'")
        except Exception as e:
            print(f"CRITICAL AudioIO Error: Could not open MIDI port. {e}")
            print("Available ports are:", mido.get_input_names())

    def stop(self):
        # ... (keep your existing stop function) ...
        if self.inport:
            self.inport.close()
            print("AudioIO Disconnected.")

    def on_midi_callback(self, msg):
        """The core routing function."""
        # --- 2. CHECK DYNAMIC PROJECT MAPPINGS ---
        if msg.type == 'control_change':
            action = self.project.midi_mapping.get(msg.control)
            #print(f"Checking MIDI CC {msg.control} for mapped action: {action}")
            if action:
                self.handle_command(action, msg)

        # --- 4. LIVE PLAYBACK & RECORDING (Your existing logic) ---
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

    def handle_command(self, action: str, msg):
        """This is the main lifeline from the AudioIO to the API. Whenever a MIDI command is recognized, this function is called."""
        if self.on_command_cb:
            if action == "BPM_KNOB":
                    if getattr(self, 'last_bpm_knob_value', None) is not None:
                        if msg.value > self.last_bpm_knob_value:
                            if self.on_command_cb: self.on_command_cb("BPM_UP")
                        elif msg.value < self.last_bpm_knob_value:
                            if self.on_command_cb: self.on_command_cb("BPM_DOWN")
                    self.last_bpm_knob_value = msg.value
                    return
            elif action in ["BPM_UP", "BPM_DOWN"]:
                self.on_command_cb(action)
                return
            elif action == "VOLUME_ROLLER":
                # get the armed track and set its gain
                armed_track = self.project.get_armed_track()
                if armed_track:
                    armed_track.set_volume(msg.value)  # Normalize MIDI value to 0.0 - 1.0
                self.on_command_cb(action)  # Notify the API of the volume change
                return
            elif action in ["NAV_LEFT", "NAV_DOWN", "NAV_RIGHT", "NAV_UP"]:
                if self.on_command_cb: self.on_command_cb(self.joystick.process(msg, action))
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

    def process(self, msg, action: str) -> str | None:
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
