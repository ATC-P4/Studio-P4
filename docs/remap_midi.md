# How to Remap MIDI Controls

Studio P4 is hardcoded by default to work with the **AKAI MPK Mini Plus**, with the joystick configured in accordance. However, because different MIDI controllers assign different Control Change (CC) numbers to their knobs and joysticks, you may need to remap these values if you are using a different keyboard.

This guide explains how to find your keyboard's CC values and update the application to recognize them.

## Step 1: Find Your Keyboard's CC Values

If you don't know the CC numbers your keyboard outputs, you can find out by running the application and watching the terminal:

1. Open your terminal and run `python main.py`.
2. Press the buttons or move the joystick on your MIDI keyboard.
3. Look at the terminal output. You will see raw MIDI messages printed out, looking something like this:
   `[MidiIO] Received MIDI message: control_change channel=0 control=114 value=127 time=0`
4. Note down the `control` number for each physical button you want to map.

## Step 2: Update the Mapping Dictionary

The MIDI mappings are stored in a single dictionary located in the **`core/midi_io.py`** file.

1. Open `core/midi_io.py` in your code editor.
2. Locate the `MidiIO` class and find the `DEFAULT_MIDI_MAPPING` dictionary at the top.
3. Replace the integer keys (the CC numbers) with the numbers you noted from your keyboard.

### Example Mapping

```python
class MidiIO:
    DEFAULT_MIDI_MAPPING = {
        # Transport Controls
        119: "TOGGLE_RECORD",   # Change 119 to your Record button's CC
        118: "TOGGLE_PLAY",     # Change 118 to your Play button's CC
        117: "TOGGLE_METRONOME",
        
        # Tempo Controls
        77: "BPM_KNOB",         # Map to an endless rotary encoder
        116: "BPM_UP",
        115: "BPM_DOWN",
        
        # Joystick / D-Pad Navigation
        2: "NAV_DOWN",          # Change 2 to your joystick's DOWN CC
        3: "NAV_UP",
        12: "NAV_LEFT",
        13: "NAV_RIGHT",
        
        # Mix Controls
        1: "VOLUME_ROLLER",     # Map to a fader or knob
        114: "REFRESH_AUDIO",
    }
```

### Step 3: Adjust the Joystick Threshold (Optional)

Analog joysticks send a continuous stream of numbers from `0` to `127`. To prevent menus from scrolling uncontrollably, Studio P4 uses a threshold to convert this analog sweep into a single digital "click".

If your joystick requires you to push too hard, or triggers too easily, you can adjust the threshold:

1. Still in `core/midi_io.py`, scroll down to the `JoystickMapper` class.
2. Locate the `self.threshold` variable inside the `__init__` method.
3. Change the value (Default is `100`). 
   * *Lowering* it (e.g., `50`) makes the joystick more sensitive.
   * *Raising* it (e.g., `120`) requires a harder push to trigger navigation.