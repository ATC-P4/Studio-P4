# This script is designed to demo fluidsynth
import time, mido, fluidsynth

AUDIO_DRIVER = "coreaudio" # coreaudio for MacOS, dsound/wasapi for Windows

def basic_test(path: str = "sf2/Default/basic_piano.sf2", program: int = 0, bank: int = 0, note: int = 60, velocity: int = 100):
    print("=== Starting Basic FluidSynth Test with {}".format(path))
    fl = fluidsynth.Synth()
    fl.start(driver=AUDIO_DRIVER)
    sfid = fl.sfload(path)
    fl.program_select(0, sfid, bank, program)

    time.sleep(1)  # Wait a moment for the synth to initialize
    print("Playing a C4 note...")
    fl.noteon(0, note, velocity)  # Channel 0, note, velocity
    time.sleep(2)  # Hold the note for 1 second
    fl.noteoff(0, note)
    print("Note released.")
    fl.delete()

# Run this method with MIDI input to test live notes
def test_midi_input():
    print("=== Starting MIDI Input Test ===")
    fl = fluidsynth.Synth()
    fl.start(driver=AUDIO_DRIVER)
    sfid = fl.sfload("sf2/basic_piano.sf2")
    fl.program_select(0, sfid, 0, 0)

    with mido.open_input() as inport:
        print("Listening for MIDI input... (Press Ctrl+C to stop)")
        try:
            for msg in inport:
                if msg.type in ['note_on', 'note_off']:
                    play_msg(msg, fl)
        except KeyboardInterrupt:
            print("MIDI input test stopped.")
    fl.delete()


def play_msg(msg, fl: fluidsynth.Synth()):
    print(f"Playing MIDI message: {msg}")
    if msg.type == 'note_on':
        fl.noteon(0, msg.note, msg.velocity)
    elif msg.type == 'note_off':
        fl.noteoff(0, msg.note)



def test_reverb_attack(path: str = "sf2/Default/basic_piano.sf2", program: int = 0):
    print(f"=== Starting Reverb & Attack Test with {path} ===")
    fl = fluidsynth.Synth()
    fl.setting("synth.reverb.active", 1)
    fl.start(driver=AUDIO_DRIVER)
    sfid = fl.sfload(path)
    fl.program_select(0, sfid, 0, program)
    
    # --- 1. BASELINE (Dry) ---
    print("1. Playing baseline dry note...")
    fl.cc(0, 91, 0)   # CC 91: Reverb Send Level (0 = dry)
    fl.cc(0, 73, 64)  # CC 73: Attack Time (64 = default/center)
    fl.noteon(0, 60, 100)
    time.sleep(1.5)
    fl.noteoff(0, 60)
    time.sleep(1)

    # --- 2. REVERB TEST ---
    print("2. Turning on Massive Reverb...")
    # Global Synth Reverb Engine settings:
    # set_reverb(roomsize [0.0-1.2], damping [0.0-1.0], width [0.0-100.0], level [0.0-1.0])
    fl.set_reverb(1.2, 0.2, 100.0, 1.0)
    #fl.set_reverb(True)
    
    # Tell Channel 0 to route 100% of its audio to the Reverb effect
    fl.cc(0, 91, 127) 
    
    fl.noteon(0, 60, 100)
    time.sleep(1.5)
    fl.noteoff(0, 60)
    time.sleep(2) # Give it time so you can hear the reverb tail fade out

    # --- 3. ATTACK TEST ---
    print("3.1 Slowing down the Attack (Swell/Pad effect)...")
    # Tell Channel 0 to maximize the volume envelope attack time
    fl.cc(0, 73, 127) 
    
    fl.noteon(0, 60, 100)
    time.sleep(3) # Wait longer because the sound takes time to fade in
    fl.noteoff(0, 60)
    time.sleep(1)

    # --- 3.2 ATTACK TEST (Custom Modulator) ---
    print("3.2 Slowing down the Attack (Swell/Pad effect)...")
    
    # Send our custom CC 16 instead of the standard CC 73
    fl.cc(0, 16, 127) 
    
    fl.noteon(0, 60, 100)
    time.sleep(3) # Wait 3 full seconds. You will hear the piano slowly swell in!
    fl.noteoff(0, 60)
    time.sleep(1)
    
    # --- 4. CLEANUP ---
    fl.delete()
    print("=== Reverb & Attack Test Complete ===")



def bulletproof_effects_test(path: str = "sf2/Default/basic_piano.sf2", program: int = 0):
    print(f"=== Starting Bulletproof Effects Test with {path} ===")
    fl = fluidsynth.Synth()
    
    # --- REVERB FIX: Force effect memory allocation BEFORE starting the driver ---
    fl.setting("synth.reverb.active", 1)
    
    fl.start(driver=AUDIO_DRIVER)
    sfid = fl.sfload(path)
    fl.program_select(0, sfid, 0, program)
    
    # --- 1. BASELINE (Dry & Center) ---
    print("1. Playing baseline (Dry & Centered)...")
    fl.cc(0, 91, 0)   # Reverb Send: 0%
    fl.cc(0, 10, 64)  # Pan: Center
    fl.noteon(0, 60, 100)
    time.sleep(1)
    fl.noteoff(0, 60)
    time.sleep(0.5)

    # --- 2. REVERB TEST ---
    print("2. Turning on Massive Reverb...")
    fl.set_reverb(1.2, 0.1, 100.0, 1.0)
    #fl.set_reverb_on(True)
    
    # Push 100% of Channel 0's audio into the reverb room
    fl.cc(0, 91, 127) 
    
    fl.noteon(0, 60, 100)
    time.sleep(1)
    fl.noteoff(0, 60)
    print("   -> Note off. Listen to the reverb tail fade out...")
    time.sleep(3) 

    # --- 3. PAN TEST (To prove CCs are working) ---
    print("3. Testing Hard Left Pan...")
    fl.cc(0, 91, 0)   # Turn reverb back down so we can hear panning clearly
    fl.cc(0, 10, 0)   # CC 10: Pan (0 = Hard Left)
    
    fl.noteon(0, 60, 100)
    time.sleep(1)
    fl.noteoff(0, 60)
    time.sleep(0.5)
    
    print("4. Testing Hard Right Pan...")
    fl.cc(0, 10, 127) # CC 10: Pan (127 = Hard Right)
    
    fl.noteon(0, 60, 100)
    time.sleep(1)
    fl.noteoff(0, 60)
    time.sleep(1)

    # --- 4. CLEANUP ---
    fl.delete()
    print("=== Test Complete ===")

print("Basic test")
basic_test()
print("Reverb attack test 1")
test_reverb_attack()
print("Reverb attack test 2")
bulletproof_effects_test()

# Use the below test to try playing a MIDI keyboard (doesn't do anything without MIDI input)
# test_midi_input()