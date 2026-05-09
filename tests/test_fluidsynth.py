#this script is to test how fluidsynth handles different sf2 files and test if it actually changes the sound.
import time
import mido
from core.models import Project
import fluidsynth
import keyboard

def run_test():
    print("=== Starting FluidSynth Test ===")

    # 1. Initialize the Project
    print("1. Creating Project...")
    project = Project("FluidSynth Test", bpm=120)
    
    # 2. Add a Track with a different SoundFont
    print("2. Adding Track with a different SoundFont...")
    try:
        # Make sure you have "another_sf2.sf2" in your directory for this test!
        project.add_track("Piano Track") 

        active_track = project.get_armed_track()
        print(f"   -> Track '{active_track.name}' armed successfully with new SoundFont.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load FluidSynth or SoundFont. {e}")
        return

    # 3. Play a note to test the new SoundFont
    print("3. Playing a note to test the new SoundFont...")
    active_track.play_note_on(60, velocity=100)  # Middle C
    time.sleep(1)  # Hold the note for 1 second
    active_track.play_note_off(60)
    print("   -> Note played and released.")

# 4. Test the Metronome Clicks
    print("4. Testing Metronome Clicks...")
    project.metronome.play_click(is_downbeat=True)  # Should play a downbeat click
    time.sleep(0.5)
    project.metronome.play_click(is_downbeat=False) # Should play an upbeat click
    print("   -> Metronome clicks played.")

def basic_test(path: str = "sf2/basic_piano.sf2", program: int = 0, bank: int = 0, note: int = 60, velocity: int = 100):
    print("=== Starting Basic FluidSynth Test with {}".format(path))
    fl = fluidsynth.Synth()
    fl.start(driver="dsound")
    sfid = fl.sfload(path)
    fl.program_select(0, sfid, bank, program)

    time.sleep(1)  # Wait a moment for the synth to initialize
    print("Playing a C4 note...")
    fl.noteon(0, note, velocity)  # Channel 0, note, velocity
    time.sleep(2)  # Hold the note for 1 second
    fl.noteoff(0, note)
    print("Note released.")
    fl.delete()

from sf2utils.sf2parse import Sf2File

def list_presets_and_instruments(sf2_path: str):
    with open(sf2_path, 'rb') as sf2_file:
        sf2 = Sf2File(sf2_file)
        for preset in sf2.presets:
            print(f"Preset: {preset.name}, Bank: {preset.bank}, Program: {preset.preset}")
            for instrument in preset.instruments:
                print(f"  Instrument: {instrument.name}")
                for sample in instrument.samples:
                    print(f"    Sample: {sample.name}, Rate: {sample.sample_rate}")
def test_midi_input():
    print("=== Starting MIDI Input Test ===")
    fl = fluidsynth.Synth()
    fl.start(driver="dsound")
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

def play_msg(msg, fl):
    print(f"Playing MIDI message: {msg}")
    if msg.type == 'note_on':
        fl.noteon(0, msg.note, msg.velocity)
    elif msg.type == 'note_off':
        fl.noteoff(0, msg.note)

def behaviour_test():
    # This function is meant to be run while the main application is running, to test how the UI and API react to MIDI commands.
    # You can trigger it by sending MIDI messages from your controller that correspond to the mapped commands (e.g., "MUTE_TRACK_0", "ARM_TRACK_1", "NAV_VIEW", etc.)
    # Make sure to have the main application running and the MIDI controller connected before running this test.
    print("=== Starting MIDI Command Behavior Test ===")
    print("Please send MIDI commands from your controller to see how the application responds.")
    fs = fluidsynth.Synth()
    fs.start(driver="dsound")
    fs.setting("midi.driver", "none")
    fs.setting("midi.autoconnect", 0)
    sfid = fs.sfload("sf2/1115_Alaska.sf2")
    fs.program_select(0, sfid, 0, 0)
    keyboard.wait("esc")  # Wait until the user presses the ESC key to stop the test

def test_reverb_attack(path: str = "sf2/basic_piano.sf2", program: int = 0):
    print(f"=== Starting Reverb & Attack Test with {path} ===")
    fl = fluidsynth.Synth()
    fl.setting("synth.reverb.active", 1)
    fl.start(driver="dsound")
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

def bulletproof_effects_test(path: str = "sf2/basic_piano.sf2", program: int = 0):
    print(f"=== Starting Bulletproof Effects Test with {path} ===")
    fl = fluidsynth.Synth()
    
    # --- REVERB FIX: Force effect memory allocation BEFORE starting the driver ---
    fl.setting("synth.reverb.active", 1)
    
    fl.start(driver="dsound")
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

# Run it
#bulletproof_effects_test()
test_reverb_attack()


#list_presets_and_instruments("sf2/Metronom.sf2")
#basic_test("sf2/Metronom.sf2", program=48, bank=128, note=76, velocity=100)  # Test the metronome SoundFont
#test_midi_input()
#behaviour_test()

"""
basic_test()
time.sleep(0.5)  # Wait a bit before running the full test
basic_test("sf2/1115_Alaska.sf2")  # Test the metronome SoundFont
time.sleep(0.5)  # Wait a bit before running the full test
basic_test("sf2/SFX_StarWars_ships.sf2")  # Test the metronome SoundFont
time.sleep(0.5)  # Wait a bit before running the full test
basic_test("sf2/Arachno_SoundFont.sf2")  # Test the metronome SoundFont
time.sleep(0.5)  # Wait a bit before running the full test

basic_test("sf2/Arachno_SoundFont.sf2",127)  # Test the metronome SoundFont
time.sleep(0.5)  # Wait a bit before running the full test
"""