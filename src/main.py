import keyboard
import threading
import time
import classes as classes
import mido
import fluidsynth
import functions as f
import states as s
mido.set_backend("mido.backends.rtmidi")


#main logic
if __name__ == "__main__":
    # Create a project and a track for testing
    s.s_t.length = 4
    s.s_t.midi_file_name = "piano_track.mid"

    #initiating the time tracking
    record_start_time = time.time()
    s.last_msg_time = record_start_time
    s.midi_track = mido.MidiTrack()
    mid = mido.MidiFile(ticks_per_beat=s.m_p.tpb)
    mid.tracks.append(s.midi_track)

    # Port discovery
    port_thread = threading.Thread(target=f.port_discovery, daemon=True)
    port_thread.start()

    #starts the keyboard listener in a separate thread 
    listener_thread = threading.Thread(target=f.keyboard_listener, daemon=True)
    listener_thread.start()

    keyboard.wait('esc')  # Main thread waits for 'esc' to exit the program
    s.terminate_flag = True
    port_thread.join()
    listener_thread.join()
    print("Program terminated.")
