import time
import mido
import classes2 as classes
from main_app import ApplicationState


def port_discovery(state: ApplicationState):
    """
    Discover available MIDI input ports and select one for recording.
    If no ports are found, print a message and return.
    """
    input_ports = mido.get_input_names()
    if not input_ports:
        print("No MIDI input devices found.")
        return

    print("Available MIDI input ports:")
    for i, name in enumerate(input_ports):
        print(f"[{i}] {name}")

    # Keep default behaviour: first port
    selected_port = input_ports[0]
    found = port_selection(selected_port, state)
    if found:
        print(f"Using input port: {selected_port}")
    else:
        raise Exception(f"Couldn't open port {selected_port}")

def port_selection(selected_port, state: ApplicationState):
    """
    Attempt to open the selected MIDI input port and set up a callback for incoming messages.
    If the port cannot be opened, print an error message and return False.
    """
    inport = None
    try:
        inport = mido.open_input(selected_port, autoreset=True, callback=on_midi)

        while not state.terminate_flag:
            time.sleep(0.1)  # Keep the thread alive
    except Exception as e:
        print(f"Could not open/read MIDI input '{selected_port}': {e}")
        return False

    finally:
        if inport is not None:
            print("Closing MIDI input port...")
            inport.close()


def on_midi(msg, state : ApplicationState):
    """
    Function to handle incoming MIDI messages during recording. It calculates the time delta since the last message,
    converts it to ticks, and appends the message to the MIDI track with the appropriate timing. It also provides live monitoring
    """

    # Can't do anything if we have no project or selected track
    if state.main_project is None or state.selected_track is None:
        return
    if state.midi_track is None:
        return

    #notifies the interface that a message has just arrived
    if state.midi_callback is not None:
        state.midi_callback(msg)
    
    if state.record_flag:

        now = time.time()
        delta_seconds = 0
        if state.last_msg_time is not None:
            delta_seconds = now - state.last_msg_time
        state.last_msg_time = now

        ticks = mido.second2tick(delta_seconds, state.main_project.tpb, mido.bpm2tempo(state.main_project.bpm))
        round_ticks = round(ticks)
        state.recorded_ticks += round_ticks
        state.midi_track.append(msg.copy(time=round_ticks))
        # print(f"Recorded: {msg.type} | Ticks: {round(ticks)}")

    # print(f"{msg.channel}, {msg.note}, {msg.velocity}")
    state.selected_track.play_note(msg)

def record(state: ApplicationState):
    """
    Main recording loop that runs in a separate thread. It calculates the target number of ticks based on the track length,
     BPM, and time signature. It continuously checks if the recording duration has been reached and handles MIDI message
    """

    if state.selected_track is None or state.main_project is None:
        return

    bpm = state.main_project.bpm
    ts_num, ts_den = state.main_project.time_signature
    total_time = state.selected_track.length * ts_num * (60.0 / bpm) * (4.0 / ts_den)
    target_ticks = round(mido.second2tick(total_time, state.main_project.tpb, mido.bpm2tempo(state.main_project.bpm)))
    

    # MIDI container
    state.midi_track = mido.MidiTrack()
    mid = mido.MidiFile(ticks_per_beat=state.main_project.tpb)
    mid.tracks.append(state.midi_track)
    state.recorded_ticks = 0

    temp = time.time()
    record_start_time = temp
    state.last_msg_time = temp
    completed = False
    while state.record_flag:
        # elapsed = time.time() - record_start_time
        # if elapsed >= total_time:
        #     print("Reached track duration.")
        #     completed = True
        #     state.record_flag = False
        time.sleep(0.1)  # Sleep briefly to reduce CPU usage

    if not state.record_flag:
        completed = True
    
    # Check for completion and pad the MIDI track if necessary, also check for unclosed notes and close them if needed before saving the file
    if completed:
        if state.recorded_ticks < target_ticks:
            print("Padding MIDI track to reach target length...")
            pad_ticks = max(0, target_ticks - state.recorded_ticks)
            state.midi_track.append(mido.MetaMessage("end_of_track", time=pad_ticks))

        # elif s.recorded_ticks > target_ticks:
        #     print("Warning: Recorded MIDI exceeds target length. Consider adjusting track length or tempo.")
        # print("checking for unclosed notes...")

        # Ensure all notes are properly closed
        # Assume that every note is from the same channel

        active_notes = {}
        for msg in state.midi_track:
            if msg.type == "note_on" and msg.velocity > 0:
                active_notes[msg.note] = msg
            elif (msg.type == "note_off") or (msg.type == "note_on" and msg.velocity == 0):
                active_notes.pop(msg.note, None)

        if active_notes:
            print("Warning: Found unclosed notes.")
            for (channel, note), msg in active_notes.items():
                print(f" - Channel {channel}, Note {note} started at tick {msg.time} was not closed.")
                state.midi_track.append(mido.Message("note_off", channel=channel, note=note, velocity=0, time=0))

        # Save midi file
        if state.selected_track.midi_file_name:
            mid.save(state.selected_track.midi_file_name)
            print(f"Successfully saved to {state.selected_track.midi_file_name}")
        
    else:
        print("Recording stopped before completion, file not saved.")

def player(callback,state: ApplicationState):
    """
    playback the MIDI file associated with the current track using fluidsynth for live monitoring. 
    It reads the MIDI file and sends messages to the synthesizer in real-time.
    """

    # Check the selected track and filename are not None
    if state.selected_track is None:
        return
    filename = state.selected_track.midi_file_name
    if filename is None:
        return
    
    mid = mido.MidiFile(filename)
    for msg in mid.play():
        on_midi(msg, state)  # This will trigger the on_midi callback for live monitoring

    # Indicates that we're done playing to the caller
    callback()

