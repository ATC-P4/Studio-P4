import rtmidi

# 1. Initialize the MIDI input
midi_in = rtmidi.MidiIn()

# 2. Open the port (0 is usually the first available controller)
ports = midi_in.get_ports()
if ports:
    midi_in.open_port(0)
    print(f"Connected to: {ports[0]}")
else:
    print("No MIDI ports found.")

# 3. Read messages in a loop
print("Listening for raw bytes... Press Ctrl+C to stop.")
try:
    while True:
        msg = midi_in.get_message()
        if msg:
            message_bytes, delta_time = msg
            print(f"Raw Bytes: {message_bytes} | Hex: {[hex(b) for b in message_bytes]}")
except KeyboardInterrupt:
    print("Stopped.")
finally:
    midi_in.close_port()