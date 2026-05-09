import time

import pyaudio as pa
from piper import PiperVoice, SynthesisConfig

start = time.time()

# PyAudio player
player = pa.PyAudio()

# Configure synthesis options
syn_config = SynthesisConfig(
    volume=0.5,           # half as loud
    length_scale=1.2,     # 50% slower
    noise_scale=0.667,    # amount of audio variation
    noise_w_scale=0.8,    # amount of speaking variation
    normalize_audio=True  # automatically normalize volume
)

print("Loading voice...")
voice = PiperVoice.load("fr_FR-siwis-medium.onnx")
print("Voice loaded.")

print("Creating stream...")
# Create PyAudio stream
stream = player.open(
    format=pa.paInt16,
    channels=1,
    rate=voice.config.sample_rate,
    output=True
)

print("Creating TTS audio chunks...")
audio = voice.synthesize(text="Bonjour, je suis le studio P4.", syn_config=syn_config)

print("Streaming audio chunks...")
for chunk in audio:
    stream.write(chunk.audio_int16_bytes)

# Reloading more TTS
print("Creating next TTS audio chunks...")
audio = voice.synthesize(text="Bonjour, je suis à l'innovation park et il fait beau.", syn_config=syn_config)

# Reading them
print("Streaming next chunks...")
for chunk in audio:
    stream.write(chunk.audio_int16_bytes)

print("Stopping and closing sream...")
stream.stop_stream()
stream.close()

print("Terminating PyAudio player...")
player.terminate()

end = time.time()

print(f"Done, runtime: {end - start}s")

# Temps Daniel: ~7.2s