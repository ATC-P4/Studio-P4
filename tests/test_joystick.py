import mido
import time
import sys

# =====================================================================
# 1. THE MAPPER (Copied from core/audio_io.py)
# =====================================================================
class JoystickMapper:
    """
    Translates physical joystick MIDI CC values into UI navigation commands.
    """
    def __init__(self, xr_cc=2,xl_cc=3, yr_cc=12, yl_cc=13, deadzone=(48, 80)):
        self.XR_CC = xr_cc
        self.XL_CC = xl_cc
        self.YR_CC = yr_cc
        self.YL_CC = yl_cc
        self.deadzone = deadzone
        
        self.last_x_state = "CENTER"
        self.last_y_state = "CENTER"

    def process(self, msg) -> str | None:
        """Returns a navigation command if the joystick enters a new zone."""
        
        # --- Handle standard Control Change (CC) Joysticks ---
        if msg.type == 'control_change':
            # Y-Axis Logic (Up / Down)
            if msg.control == self.YR_CC:
                state = "UP" if msg.value > self.deadzone[1] else "DOWN" if msg.value < self.deadzone[0] else "CENTER"
                if state != self.last_y_state:
                    self.last_y_state = state
                    if state != "CENTER":
                        return f"NAV_{state}"

            # X-Axis Logic (Left / Right)
            elif msg.control == self.XR_CC:
                state = "RIGHT" if msg.value > self.deadzone[1] else "LEFT" if msg.value < self.deadzone[0] else "CENTER"
                if state != self.last_x_state:
                    self.last_x_state = state
                    if state != "CENTER":
                        return f"NAV_{state}"
                    
                

        # --- Handle Pitchwheel Joysticks (Very common for Y-Axis) ---
        # Pitchwheel ranges from 0 to 16383. Center is 8192.
        elif msg.type == 'pitchwheel':
            pw_deadzone = (6000, 10000) # Wiggle room around 8192 center
            state = "UP" if msg.pitch > pw_deadzone[1] else "DOWN" if msg.pitch < pw_deadzone[0] else "CENTER"
            if state != self.last_y_state:
                self.last_y_state = state
                if state != "CENTER":
                    return f"NAV_{state} (via Pitchwheel)"

        return None


# =====================================================================
# 2. DIAGNOSTIC TOOL
# =====================================================================
def main():
    print("\n--- MIDI Joystick Diagnostic Tool ---")
    
    # 1. List available ports
    ports = mido.get_input_names()
    if not ports:
        print("ERROR: No MIDI devices found! Please plug in your controller.")
        sys.exit(1)

    print("\nAvailable MIDI Ports:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port}")

    # 2. Ask user to select a port
    try:
        selection = int(input("\nEnter the number of your MIDI port to monitor: "))
        selected_port_name = ports[selection]
    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")
        sys.exit(1)

    # Instantiate our mapper with the CCs you suspect
    # (Adjust these based on what the Raw Output tells you)
    mapper = JoystickMapper(x_cc=2, y_cc=12)

    print(f"\n[ SYSTEM ] Connecting to '{selected_port_name}'...")
    print("[ SYSTEM ] Move your joystick. Press Ctrl+C to exit.\n")
    print("-" * 60)

    try:
        # Open the port and listen
        with mido.open_input(selected_port_name) as inport:
            for msg in inport:
                # Ignore clock sync messages (they spam the console)
                if msg.type in ['clock', 'sysex', 'active_sensing']:
                    continue

                # A. Print the RAW hardware data
                if msg.type == 'control_change':
                    print(f"[ RAW  ] CC Message - Control: {msg.control:3} | Value: {msg.value:3}")
                elif msg.type == 'pitchwheel':
                    print(f"[ RAW  ] Pitchwheel - Value: {msg.pitch:5}")
                elif msg.type in ['note_on', 'note_off']:
                    print(f"[ RAW  ] Note       - Note: {msg.note:3} | Velocity: {msg.velocity:3} ({msg.type})")
                else:
                    print(f"[ RAW  ] Other      - {msg}")

                # B. Pass to the Mapper and print the result
                nav_command = mapper.process(msg)
                if nav_command:
                    print(f">>> [ MAPPER ] SUCCESS: Triggered '{nav_command}'")
                    print("-" * 60)

    except KeyboardInterrupt:
        print("\n[ SYSTEM ] Diagnostic tool closed.")
    except Exception as e:
        print(f"\n[ ERROR ] {e}")

if __name__ == "__main__":
    main()