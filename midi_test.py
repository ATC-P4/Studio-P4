import mido
import time

# List available input ports
midi_names = mido.get_input_names()
print(midi_names)
DEVICE = midi_names[0]

recorded_messages = []
start_time = None

with mido.open_input(DEVICE) as port:
    print("Recording... Press Ctrl+C to stop.")
    try:
        start_time = time.time()
        for msg in port:
            if msg.type == 'note_on' or msg.type == 'note_off':
                elapsed = time.time() - start_time
                msg_with_time = msg.copy(time=int(elapsed * 1000))  # ms
                recorded_messages.append(msg_with_time)
                print(f"Recorded: {msg_with_time}")
    except KeyboardInterrupt:
        print("Stopped recording.")

# Save to MIDI file
mid = mido.MidiFile()
track = mido.MidiTrack()
mid.tracks.append(track)

track.append(mido.MetaMessage('set_tempo', tempo=500000))  # 120 BPM

prev_time = 0
for msg in recorded_messages:
    delta = msg.time - prev_time
    prev_time = msg.time
    track.append(msg.copy(time=delta))  # MIDI uses delta times

mid.save('recorded.mid')
print("Saved to recorded.mid")