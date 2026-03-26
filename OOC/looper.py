import keyboard
import threading
import time
import classes
import mido
import fluidsynth
mido.set_backend("mido.backends.rtmidi")

global flag_recording
flag_recording = False  # global variable to track recording state

global rec_thread
rec_thread = None  # global variable to hold the recording thread

global last_time
last_time = 0

"""
def handle_midi(msg, midi_track, TICKS_PER_BEAT, TEMPO):
    global last_time
    
    # 2. Get exact current time and calculate delta seconds
    current_time = time.time()
    delta_seconds = current_time - last_time
    last_time = current_time  # Reset for the next message
    
    # 3. Convert manual delta seconds to ticks
    ticks = mido.second2tick(delta_seconds, TICKS_PER_BEAT, TEMPO)
    
    track_msg = msg.copy(time=round(ticks))
    midi_track.append(track_msg)
    
    print(f"Recorded: {msg.type} | Ticks: {round(ticks)}")

    #play it
    if msg.type == "note_on":
        print(f"Playing note: {msg.note} with velocity {msg.velocity} on channel {msg.channel}")
        fs.noteon(msg.channel, msg.note, msg.velocity)
    elif msg.type == "note_off":
        print(f"Playing note: {msg.note} with velocity {msg.velocity} on channel {msg.channel}")
        fs.noteoff(msg.channel, msg.note)
    elif msg.type == "program_change":
        fs.program_change(msg.channel, msg.program)
"""

def record_to_midi(port_name, midi_track, ticks_per_beat, tempo, total_time):
    """
    Record MIDI messages from `port_name` into `midi_track` for up to `total_time` seconds.
    Returns True if recording reached natural end, False if stopped early or failed.
    """
    global flag_recording

    print(f"Recording from '{port_name}'...")
    print("Play your MIDI instrument. Press 'r' again to stop and save.")

    record_start_time = time.time()
    last_msg_time = record_start_time

    def on_midi(msg):
        nonlocal last_msg_time
        now = time.time()
        delta_seconds = now - last_msg_time
        last_msg_time = now

        ticks = mido.second2tick(delta_seconds, ticks_per_beat, tempo)
        midi_track.append(msg.copy(time=round(ticks)))

        # Optional live monitoring through fluidsynth
        if msg.type == "note_on":
            fs.noteon(msg.channel, msg.note, msg.velocity)
        elif msg.type == "note_off":
            fs.noteoff(msg.channel, msg.note)
        elif msg.type == "program_change":
            fs.program_change(msg.channel, msg.program)

        print(f"Recorded: {msg.type} | Ticks: {round(ticks)}")

    inport = None
    try:
        inport = mido.open_input(port_name, autoreset=True)
        inport.callback = on_midi

        while flag_recording:
            elapsed = time.time() - record_start_time
            if elapsed >= total_time:
                print("Reached track duration.")
                return True
            time.sleep(0.01)

        print("Recording stopped by user.")
        return False

    except Exception as e:
        print(f"Could not open/read MIDI input '{port_name}': {e}")
        return False

    finally:
        if inport is not None:
            print("Closing MIDI input port...")
            inport.close()


def create_project(pname):
    project = classes.Project(pname=pname)
    return project

def create_track(name, project):
    track = project.add_track(name)
    return track



def player():
    print("Player function called.")
    pass

def record(project, track):
    global flag_recording

    print("Record function called.")

    if not track.midi_file_name:
        print("No MIDI output filename set on track; recording aborted.")
        flag_recording = False
        return

    # Timing setup
    bpm = project.bpm
    ts_num, ts_den = project.time_signature
    tempo = mido.bpm2tempo(bpm)
    ticks_per_beat = project.tpb
    total_time = track.length * ts_num * (60.0 / bpm) * (4.0 / ts_den)

    # MIDI container
    midi_track = mido.MidiTrack()
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    mid.tracks.append(midi_track)

    # Port discovery
    input_ports = mido.get_input_names()
    if not input_ports:
        print("No MIDI input devices found.")
        flag_recording = False
        return

    print("Available MIDI input ports:")
    for i, name in enumerate(input_ports):
        print(f"[{i}] {name}")

    # Keep default behavior: first port
    selected_port = input_ports[0]
    print(f"Using input port: {selected_port}")

    completed = record_to_midi(
        selected_port,
        midi_track,
        ticks_per_beat,
        tempo,
        total_time,
    )

    if completed or len(midi_track) > 0:
        mid.save(track.midi_file_name)
        print(f"Successfully saved to {track.midi_file_name}")
    else:
        print("No data recorded, file not saved.")

    flag_recording = False

def keyboard_shortcuts(project, track):
    def click_e(event):
        player()

    def click_r(event):
        global flag_recording, rec_thread
        if flag_recording is True and rec_thread is not None:
            print("Stopping recording...")
            flag_recording = not flag_recording
            # Python threads cannot be force-stopped; clear the handle here.
            rec_thread = None
        else:
            print("Starting recording...")
            flag_recording = not flag_recording
            rec_thread = threading.Thread(target=record, args=[project,track], daemon=True)
            rec_thread.start()

    keyboard.on_press_key('e', click_e)
    keyboard.on_press_key('r', click_r)

    print("Keyboard listener running in background. Press 'esc' to stop listener.")
    keyboard.wait('esc')  # blocks only this thread

    pass



if __name__ == "__main__":
    # Create a project and a track for testing
    project_1 = create_project("My First Project")
    track_1 = create_track("Piano Track", project_1)
    track_1.length = 4
    track_1.midi_file_name = "piano_track.mid"

    fs = fluidsynth.Synth()
    fs.start()  # On Windows, auto audio driver is usually fine
    sfid = fs.sfload(track_1.sf2_file_name)
    fs.program_select(0, sfid, 0, 0)

    #starts the keyboard listener in a separate thread 
    listener_thread = threading.Thread(target=keyboard_shortcuts, args=[project_1,track_1], daemon=True)
    listener_thread.start()
    keyboard.wait('esc')  # Main thread waits for 'esc' to exit the program
