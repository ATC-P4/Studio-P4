import time
import mido
from core.models import Project, Track

def run_test():
    print("=== Starting Core Models Test ===")

    # 1. Initialize the Project
    print("1. Creating Project...")
    project = Project("Test Project", bpm=120)
    
    # 2. Add a Track
    print("2. Adding Track and initializing FluidSynth...")
    try:
        # NOTE: Make sure "basic_piano.sf2" exists in your directory!
        project.add_track("Piano Track") 
        active_track = project.get_armed_track()
        print(f"   -> Track '{active_track.name}' armed successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load FluidSynth or SoundFont. {e}")
        return

    # 3. Simulate playing and recording a C-Major arpeggio
    print("3. Simulating live play and recording...")
    notes_to_play = [60, 64, 67, 72] # C4, E4, G4, C5
    
    # We need to track absolute time for the Master Clock simulation
    start_time = time.perf_counter()
    #active_track.set_instrument(0)  # Ensure the instrument is set (Acoustic Grand Piano)
    time.sleep(2)  # Simulate a delay before starting to play (e.g., count-in)
    for note in notes_to_play:
        current_time = time.perf_counter() - start_time
        
        # Play the note out loud
        active_track.play_note_on(note, velocity=100)
        
        # Record the note-on event
        msg_on = mido.Message('note_on', note=note, velocity=100)
        active_track.add_midi_event(msg_on, current_time)
        print(f"   -> Played Note ON: {note}")
        
        # Hold the note for 0.5 seconds
        time.sleep(0.5) 
        
        current_time = time.perf_counter() - start_time
        
        # Stop the note
        active_track.play_note_off(note)
        
        # Record the note-off event
        msg_off = mido.Message('note_off', note=note, velocity=0)
        active_track.add_midi_event(msg_off, current_time)
        print(f"   -> Played Note OFF: {note}")

    # 4. Test the Flush Notes function
    print("4. Testing flush_notes()...")
    active_track.play_note_on(48, 100) # Play a low C
    print("   -> Low C playing... flushing in 1 second.")
    time.sleep(0.5)
    active_track.flush_notes()
    print("   -> Notes flushed (should be silent now).")

    # 5. Export to MIDI File
    print("5. Exporting to .mid file...")
    try:
        # This will test your Delta-Time conversion logic
        project.save_project("test_output")
        print("   -> Success! Check your folder for 'test_output_Piano Track_basic_piano.sf2.mid'")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to save MIDI file. {e}")

    print("=== Test Complete ===")

if __name__ == "__main__":
    run_test()