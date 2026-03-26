import keyboard
import threading
import time
import classes
import mido
import fluidsynth
mido.set_backend("mido.backends.rtmidi")

global flag_recording

def on_midi(msg):
    nonlocal last_msg_time
    now = time.time()
    delta_seconds = now - last_msg_time
    last_msg_time = now

    ticks = mido.second2tick(delta_seconds, ticks_per_beat, tempo)
    midi_track.append(msg.copy(time=round(ticks)))

    # Optional live monitoring through fluidsynth
    if msg.type == "note_on":
        fs.noteon(msg.channel, msg.note, msg.velocity)
    elif msg.type == "note_off":
        fs.noteoff(msg.channel, msg.note)
    elif msg.type == "program_change":
        fs.program_change(msg.channel, msg.program)

    #print(f"Recorded: {msg.type} | Ticks: {round(ticks)}")