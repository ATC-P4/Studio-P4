import pyaudio as pa
import threading
from enum import Enum
from core.utils import EventBus, EventType
import time
from typing import TypeVar, Generic
from piper import PiperVoice, AudioChunk
from collections.abc import Iterable


class VoiceType(Enum):
    STOP = 0
    BPM_INFO = 1
    BPM_MOD = 2
    REC_STOP = 3
    WELCOME = 4
    METR_TOGGLE = 5
    PROJ_SAVE = 6
    METR_INFO = 7
    PROJ_INFO = 8
    GENERAL_INFO = 9
    TRACK_INFO = 10
    TRACK_NAME = 11

K = TypeVar('K')
V = TypeVar('V')
# Your requested BlockingMap from Slack
class BlockingMap(Generic[K, V], object):
    def __init__(self):
        self._queue: dict[K, V] = {}
        self._cv = threading.Condition()
        self._last_popped: None | tuple[K, V] = None

    def put(self, key: K, value: V) -> None:
        with self._cv:
            self._queue[key] = value
            self._cv.notify()

    def pop(self) -> tuple[K, V]:
        with self._cv:
            while not self._queue:
                self._cv.wait()
            # popitem() returns the most recently inserted key-value pair (LIFO)
            self._last_popped = self._queue.popitem()
            return self._last_popped
        
    def get_last_popped(self) -> None | tuple[K, V]:
        return self._last_popped
    
    def clear_last_popped(self) -> None:
        self._last_popped = None

class VoiceService:

    _vol = 0.5
    _lenscale = 1.2
    _nsscale = 0.667
    _nswscale = 0.8
    _normaudio = True

    def __init__(self, voice_engine: PiperVoice):
        """
        voice_engine: Your text-to-speech synthesizer instance.
        voice_config: Configuration for the voice synthesizer.
        """
        self._voice = voice_engine
        self._voice_queue: BlockingMap[VoiceType, Iterable[AudioChunk] | None] = BlockingMap()
        self._is_running = True
        self._interrupt = threading.Event()
        
        # Start the persistent audio worker
        threading.Thread(target=self._voice_worker, daemon=True).start()

    def _voice_worker(self):
        """Single persistent thread that owns the audio engine exclusively."""
        sample_rate = getattr(self._voice.config, 'sample_rate', 44100) 

        def clear_interrupt() -> None:
            """Clears interrupt request"""
            self._voice_queue.clear_last_popped()
            self._interrupt.clear()

        def check_interrupt() -> bool:
            """Checks if there's been an interruption request, if yes clear it and return true"""
            interrupt = self._interrupt.is_set()
            if interrupt:
                clear_interrupt()
            return interrupt
        
        CHUNK_SIZE = 256

        while self._is_running:
            # This uses your BlockingMap's pop function
            voicetype, audio = self._voice_queue.pop() 
            
            if voicetype == VoiceType.STOP:
                return # clean up after ourselves

            if audio:
                player = None
                stream = None
                try:
                    player = pa.PyAudio()
                    stream = player.open(
                        format=pa.paInt16,
                        channels=1,
                        rate=sample_rate,
                        output=True
                    )
                    
                    for chunk in audio:

                        raw = chunk.audio_int16_bytes
                        for i in range(0, len(raw), CHUNK_SIZE):
                            if check_interrupt():
                                break
                            stream.write(raw[i:i + CHUNK_SIZE])

                    # Clear interruption 
                    clear_interrupt()
                            
                except Exception as e:
                    # intercept the sudden disconnection
                    clear_interrupt()
                    print(f"[Audio] Switching computer sound cards...")
                    time.sleep(0.5) # Give a moment to route the audio!
                    
                finally:
                    
                    # Clear interrupt
                    clear_interrupt()

                    if stream:
                        try:
                            stream.stop_stream()
                        except: pass
                        try:
                            stream.close() # If it fails because the headset is no longer there, ignore it
                        except: pass
                        
                    if player:
                        try:
                            player.terminate() # If the termination fails, we ignore it
                        except: pass

    def speak(self, voice_type: VoiceType, text: str):
        """Synthesizes text in the background and queues it for voice."""
        def _add_sentence():
            snt = self._voice.synthesize(text)
            self._voice_queue.put(voice_type, snt)

        # We run the text-generation on a temp thread so the UI never freezes
        threading.Thread(target=_add_sentence, daemon=True).start()

    def interrupt(self):
        """Cuts off the currently playing audio immediately."""
        self._interrupt.set()

    def currently_speaking(self) -> None | VoiceType:
        """Returns the type of the currently playing (or most recently 
            played) spoken sentence."""
        v = self._voice_queue.get_last_popped()
        if not v:
            return None
        ret, _ = v
        return ret

    def shutdown(self):
        """Cleanly closes the audio stream."""
        self._voice_queue.put(VoiceType.STOP, None)
        self._is_running = False
    


class VoicePresenter:
    """Translates backend events into voice synthesizer commands."""
    
    def __init__(self, voice_path: str, event_bus: EventBus):

        voice_service = VoiceService(PiperVoice.load(voice_path))
        self.voice = voice_service
        
        # 1. Wire up the event subscriptions
        event_bus.subscribe(EventType.TRACK_SELECT, self.announce_armed_track)
        event_bus.subscribe(EventType.PROJ_SAVED, self.announce_saved)
        event_bus.subscribe(EventType.METR_TOGGLE, self.announce_metronome)
        event_bus.subscribe(EventType.BPM_MOD, self.announce_bpm)
        event_bus.subscribe(EventType.REC_STOP, self.announce_recording_stopped)
        event_bus.subscribe(EventType.TRACK_MUTE, self.announce_track_muted)
        event_bus.subscribe(EventType.STAT_REQ, self.announce_current_state)
        event_bus.subscribe(EventType.GENERAL, lambda message: self.voice.speak(VoiceType.GENERAL_INFO, message))

    def shutdown(self) -> None:
        self.voice.shutdown()

    # 2. Define the exact text and voice types for each event
    def announce_armed_track(self, track_name: str) -> None:
        self.voice.speak(VoiceType.TRACK_NAME, f"{track_name} armé")

    def announce_saved(self) -> None:
        self.voice.speak(VoiceType.PROJ_SAVE, "Projet sauvegardé")
        
    def announce_metronome(self, is_on: bool) -> None:
        msg = "Métronome On" if is_on else "Métronome Off"
        self.voice.speak(VoiceType.METR_TOGGLE, msg)

    def announce_bpm(self, bpm: int) -> None:
        self.voice.speak(VoiceType.BPM_MOD, f"B P M {bpm}")
        
    def announce_recording_stopped(self) -> None:
        self.voice.speak(VoiceType.REC_STOP, "Enregistrement arrêté.")

    def announce_track_muted(self, track_name: str, is_muted: bool) -> None:
        status = "muté" if is_muted else "démuté"
        self.voice.speak(VoiceType.TRACK_INFO, f"{track_name} {status}")
    
    def announce_current_state(self, metronome_status: str, bpm: int) -> None:
        """announce current BPM and metronome status on demand"""
        self.voice.speak(VoiceType.METR_INFO, f"Métronome actuellement {metronome_status}.")
        self.voice.speak(VoiceType.BPM_INFO, f"B P M actuel: {bpm}")

    def announce_loading_proj(self, name: str) -> None:
        if self.voice.currently_speaking():
            self.voice.interrupt()
        self.voice.speak(VoiceType.PROJ_INFO, f"Chargement du projet {name}.")

    def announceb_new_proj(self) -> None:
        if self.voice.currently_speaking():
            self.voice.interrupt()
        self.voice.speak(VoiceType.PROJ_INFO, "Nouveau Projet")

    def announce_selected_proj(self, name: str) -> None:
        if self.voice.currently_speaking():
            self.voice.interrupt()
        self.voice.speak(VoiceType.PROJ_INFO, name)

    def announce_started(self) -> None:
        self.voice.speak(VoiceType.WELCOME, "Menu de démarrage. Nouveau projet.")

    def welcome(self) -> None:
        self.voice.speak(VoiceType.WELCOME, "Bienvenue dans le studio.")