import time
import mido
import classes2 as classes
import states as s 

def create_project(pname):
    project = classes.Project(pname=pname)
    s.m_p = project
    return project

def create_track(name, project):
    track = project.add_track(name)
    s.s_t = track
    return track


def port_discovery():
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
    found = port_selection(selected_port)

def port_selection(selected_port):
    """
    Attempt to open the selected MIDI input port and set up a callback for incoming messages.
    If the port cannot be opened, print an error message and return False.
    """
    inport = None
    try:
        inport = mido.open_input(selected_port, autoreset=True, callback=on_midi)

        while not s.terminate_flag:
            time.sleep(0.1)  # Keep the thread alive
    except Exception as e:
        print(f"Could not open/read MIDI input '{selected_port}': {e}")
        return False

    finally:
        if inport is not None:
            print("Closing MIDI input port...")
            inport.close()


def on_midi(msg):
    """
    Function to handle incoming MIDI messages during recording. It calculates the time delta since the last message,
    converts it to ticks, and appends the message to the MIDI track with the appropriate timing. It also provides live monitoring
    """
    
    if s.record_flag:
        now = time.time()
        delta_seconds = now - s.last_msg_time
        s.last_msg_time = now
        ticks = mido.second2tick(delta_seconds, s.m_p.tpb, mido.bpm2tempo(s.m_p.bpm))
        round_ticks = round(ticks)
        s.recorded_ticks += round_ticks
        s.midi_track.append(msg.copy(time=round_ticks))
        print(f"Recorded: {msg.type} | Ticks: {round(ticks)}")

    # Force track_channel = message_channel
    ch = msg.channel
    s.s_t.update_soundfont(ch)

    # Optional live monitoring through fluidsynth
    if msg.type == "note_on":
        s.s_t.fs.noteon(msg.channel, msg.note, msg.velocity)
    elif msg.type == "note_off":
        s.s_t.fs.noteoff(msg.channel, msg.note)
    elif msg.type == "program_change":
        s.s_t.fs.program_change(msg.channel, msg.program)

def record():
    """
    Main recording loop that runs in a separate thread. It calculates the target number of ticks based on the track length,
     BPM, and time signature. It continuously checks if the recording duration has been reached and handles MIDI message
    """
    bpm = s.m_p.bpm
    ts_num, ts_den = s.m_p.time_signature
    total_time = s.s_t.length * ts_num * (60.0 / bpm) * (4.0 / ts_den)
    target_ticks = round(mido.second2tick(total_time, s.m_p.tpb, mido.bpm2tempo(s.m_p.bpm)))
    

    # MIDI container
    s.midi_track = mido.MidiTrack()
    mid = mido.MidiFile(ticks_per_beat=s.m_p.tpb)
    mid.tracks.append(s.midi_track)
    s.recorded_ticks = 0

    temp = time.time()
    record_start_time = temp
    s.last_msg_time = temp
    completed= False
    while s.record_flag:
        elapsed = time.time() - record_start_time
        if elapsed >= total_time:
            print("Reached track duration.")
            completed= True
            s.record_flag = False
        time.sleep(0.1)  # Sleep briefly to reduce CPU usage
    
    
    #check for completion and pad the MIDI track if necessary, also check for unclosed notes and close them if needed before saving the file
    if completed:
        if s.recorded_ticks < target_ticks:
            print("Padding MIDI track to reach target length...")
            pad_ticks = max(0, target_ticks - s.recorded_ticks)
            s.midi_track.append(mido.MetaMessage("end_of_track", time=pad_ticks))
        elif s.recorded_ticks > target_ticks:
            print("Warning: Recorded MIDI exceeds target length. Consider adjusting track length or tempo.")
        print("checking for unclosed notes...")

        # Ensure all notes are properly closed
        active_notes = {}
        for msg in s.midi_track:
            if msg.type == "note_on" and msg.velocity > 0:
                active_notes[(msg.channel, msg.note)] = msg
            elif (msg.type == "note_off") or (msg.type == "note_on" and msg.velocity == 0):
                active_notes.pop((msg.channel, msg.note), None)
        if active_notes:
            print("Warning: Found unclosed notes.")
            for (channel, note), msg in active_notes.items():
                print(f" - Channel {channel}, Note {note} started at tick {msg.time} was not closed.")
                s.midi_track.append(mido.Message("note_off", channel=channel, note=note, velocity=0, time=0))

        mid.save(s.s_t.midi_file_name)
        print(f"Successfully saved to {s.s_t.midi_file_name}")
    else:
        print("Recording stopped before completion, file not saved.")

def player():
    """
    playback the MIDI file associated with the current track using fluidsynth for live monitoring. 
    It reads the MIDI file and sends messages to the synthesizer in real-time.
    """
    mid = mido.MidiFile(s.s_t.midi_file_name)
    for msg in mid.play():
        on_midi(msg)  # This will trigger the on_midi callback for live monitoring
