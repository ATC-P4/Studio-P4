import time
import mido

from core.models import Project
from core.engine import MasterClockEngine

# A dummy callback to simulate the UI getting updated
def mock_ui_callback(state):
    print(f"\n[UI MOCK] Engine state changed to: {state}")

def run_engine_test():
    print("=== Starting Master Clock Engine Test ===")

    # 1. Setup the Data
    project = Project("Engine Test", bpm=120, time_signature=(4, 4))
    
    try:
        # Ensure basic_piano.sf2 is in the same directory!
        project.add_track("Piano Track")
        armed_track = project.get_armed_track()
    except Exception as e:
        print(f"CRITICAL ERROR: FluidSynth failed. {e}")
        return
    time.sleep(4.5)
    # 2. Setup the Engine
    # We pass the mock callback so the engine can "talk" to us
    engine = MasterClockEngine(project)
    
    # 3. Turn on the Metronome
    #engine.set_metronome_state(True)
    
    # 4. Trigger Recording (This starts the thread and the Count-In)
    print("\nStarting the Engine in RECORDING mode...")
    engine.set_state("COUNT_IN")
    
    # Wait for the 4-beat count-in to finish (4 beats at 120 BPM = 2.0 seconds)
    # We sleep a little longer (2.1s) to let the engine transition its state automatically
    time.sleep(2.01) 
    
    if engine.current_state != "RECORDING":
        print(f"FAILED: Engine did not automatically transition to RECORDING. Current state: {engine.current_state}")
        engine.set_state("STOPPED")
        return

    print("\n[USER SIMULATION] Playing notes live into the track...")
    
    # Simulate the user hitting keys exactly at 0.5s, 1.0s, and 1.5s into the recording
    # At 120 BPM, these are exactly Beats 2, 3, and 4.
    
    # Note 1: E4
    time.sleep(0.5)
    armed_track.play_note_on( 64, 100)
    armed_track.add_midi_event(mido.Message('note_on', note=64, velocity=100), 0.5)
    
    # Note 2: G4
    time.sleep(0.5)
    armed_track.play_note_off(64)
    armed_track.add_midi_event(mido.Message('note_off', note=64, velocity=0), 1.0)
    
    armed_track.play_note_on(67, 100)
    armed_track.add_midi_event(mido.Message('note_on', note=67, velocity=100), 1.0)
    
    # Note 3: C5
    time.sleep(0.5)
    armed_track.play_note_off(67)
    armed_track.add_midi_event(mido.Message('note_off', note=67, velocity=0), 1.5)
    
    armed_track.play_note_on(72, 100)
    armed_track.add_midi_event(mido.Message('note_on', note=72, velocity=100), 1.5)
    
    time.sleep(0.5)
    armed_track.play_note_off(72)
    armed_track.add_midi_event(mido.Message('note_off', note=72, velocity=0), 2.0)

    print("\n[TEST] Notes recorded. Letting the engine loop twice to test playback wrap-around...")
    
    # The loop duration is 4 beats (2.0 seconds). 
    # We sleep for 4.0 seconds to let the engine play the recorded loop twice.
    # You should hear the metronome click, and the precise E-G-C notes playback exactly on time.
    time.sleep(4.0)

    print("\n[TEST] Stopping engine...")
    engine.set_state("STOPPED")
    
    # Wait a fraction of a second to let the thread die gracefully
    time.sleep(0.1)
    print("=== Test Complete ===")

if __name__ == "__main__":
    run_engine_test()