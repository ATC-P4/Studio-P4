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

    # Keep default behavior: first port
    selected_port = input_ports[0]
    print(f"Using input port: {selected_port}")
    found = port_selection(state, selected_port)



def port_selection(state: ApplicationState, selected_port: int):
    """
    Attempt to open the selected MIDI input port and set up a callback for incoming messages.
    If the port cannot be opened, print an error message and return False.
    """
    inport = None
    try:
        inport = mido.open_input(selected_port, autoreset=True)
        inport.callback = state.selected_track.play_note

        while not state.terminate_flag:
            time.sleep(0.1)  # Keep the thread alive
    except Exception as e:
        print(f"Could not open/read MIDI input '{selected_port}': {e}")
        return False



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
    

    # Handle selected_track attributes
    state.selected_track.bpm = state.bpm
    state.selected_track.tpb = state.main_project.tpb
    state.selected_track.record_flag = state.record_flag


    # MIDI container
    mid = mido.MidiFile(ticks_per_beat=state.main_project.tpb)
    mid.tracks.append(state.selected_track.midi_track)
    state.selected_track.recorded_ticks = 0

    temp = time.time()
    state.selected_track.last_msg_time = temp
    completed = False
    while state.record_flag:
        time.sleep(0.1)  # Sleep briefly to reduce CPU usage

    if not state.record_flag:
        completed = True

    # Reset record_flag for Track instace
    state.selected_track.record_flag = False
    
    # Check for completion and pad the MIDI track if necessary, also check for unclosed notes and close them if needed before saving the file
    if completed:

        if state.selected_track.recorded_ticks < target_ticks:
            pad_ticks = max(0, target_ticks - state.selected_track.recorded_ticks)
            state.selected_track.midi_track.append(mido.MetaMessage("end_of_track", time=pad_ticks))

        # Ensure all notes are properly closed
        # Assume that every note is from the same channel

        active_notes = {}
        for msg in state.selected_track.midi_track:
            if msg.type == "note_on" and msg.velocity > 0:
                active_notes[msg.note] = msg
            elif (msg.type == "note_off") or (msg.type == "note_on" and msg.velocity == 0):
                active_notes.pop(msg.note, None)

        if active_notes:
            print("Warning: Found unclosed notes.")
            for (channel, note), msg in active_notes.items():
                print(f" - Channel {channel}, Note {note} started at tick {msg.time} was not closed.")
                state.selected_track.midi_track.append(mido.Message("note_off", channel=channel, note=note, velocity=0, time=0))

        # Save midi file
        if state.selected_track.midi_file_name:
            mid.save(state.selected_track.midi_file_name)
            print(f"Successfully saved to {state.selected_track.midi_file_name}")
        
    else:
        print("Recording stopped before completion, file not saved.")

def player(callback, state: ApplicationState):
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

    print(f"[player] playing")

    for msg in mid.play():
        print(f"[player] sent {msg}")
        state.selected_track.play_note(msg)  # This will trigger the on_midi callback for live monitoring

    # Indicates that we're done playing to the caller
    callback()

