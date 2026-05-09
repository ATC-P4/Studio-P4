import time
import fluidsynth
import os

def test_channel_volume(sf2_path="sf2/basic_piano.sf2"):
    print("--- FluidSynth CC 7 Volume Test ---")
    
    # 1. Check if soundfont exists
    if not os.path.exists(sf2_path):
        print(f"ERROR: Cannot find {sf2_path}. Run this from your main project folder.")
        return

    # 2. Initialize Synth
    print("Initializing Synth...")
    synth = fluidsynth.Synth()
    synth.start(driver="wasapi") # Use your preferred driver here
    
    sf_id = synth.sfload(sf2_path)
    channel = 1
    synth.program_select(channel, sf_id, 0, 0)

    # Helper function to play a chord
    def play_chord():
        notes = [60, 64, 67] # C Major chord
        for note in notes:
            synth.noteon(channel, note, 100)
        time.sleep(1.5)
        for note in notes:
            synth.noteoff(channel, note)
        time.sleep(0.5)

    try:
        # --- TEST 1: MAX VOLUME (127) ---
        print("\nTest 1: Volume 127 (100%)")
        synth.cc(channel, 7, 127)
        play_chord()

        # --- TEST 2: HALF VOLUME (64) ---
        print("Test 2: Volume 64 (50%)")
        synth.cc(channel, 7, 64)
        play_chord()

        # --- TEST 3: LOW VOLUME (15) ---
        print("Test 3: Volume 15 (12%)")
        synth.cc(channel, 7, 15)
        play_chord()
        
        print("\nTest Complete! Did you hear the volume decrease?")

    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    finally:
        synth.delete()

if __name__ == "__main__":
    test_channel_volume()