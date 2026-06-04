"""Text-to-speech layer: VoiceService owns the audio 
thread and voice synthesizer; VoicePresenter translates EventBus 
events into spoken announcements."""

import pyaudio as pa
import threading
from enum import Enum
from core.utils import EventBus, EventType
import time
from typing import TypeVar, Generic
from piper import PiperVoice, AudioChunk, SynthesisConfig
from collections.abc import Iterable
from ui.voice_settings import SETTING_NAMES, RATE_STEPS


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
    NAME = 9
    TRACK_INFO = 10
    TRACK_NAME = 11
    ERROR = 12
    MIDI_IN = 13
    VSETT = 14
    VSETT_W = 15
    GR_SEL = 16
    INSTR_SEL = 17
    HINT = 18

K = TypeVar('K')
V = TypeVar('V')
# Your requested BlockingMap from Slack
class BlockingMap(Generic[K, V], object):
    """Thread-safe LIFO map: inserting with the same key overwrites the previous value, allowing newer events to supersede stale ones.

    Consumers block on pop() until an item is available.
    """

    def __init__(self):
        self._queue: dict[K, V] = {}
        self._cv = threading.Condition()
        self._last_popped: None | tuple[K, V] = None

    def put(self, key: K, value: V) -> None:
        """Inserts or replaces the entry for key and wakes any waiting consumer.

        Args:
            key (K): Key to insert or overwrite.
            value (V): Value to store.
        """
        with self._cv:
            self._queue[key] = value
            self._cv.notify()

    def pop(self) -> tuple[K, V]:
        """Blocks until an item is available, then removes and returns the most-recently inserted pair.

        Returns:
            tuple[K, V]: The (key, value) pair that was removed.
        """
        with self._cv:
            while not self._queue:
                self._cv.wait()
            # popitem() returns the most recently inserted key-value pair (LIFO)
            self._last_popped = self._queue.popitem()
            return self._last_popped

    def get_last_popped(self) -> None | tuple[K, V]:
        """Returns the last pair removed by pop(), or None if nothing has been popped yet.

        Returns:
            tuple[K, V] | None: The last popped (key, value) pair.
        """
        return self._last_popped

    def clear_last_popped(self) -> None:
        """Clears the cached last-popped value."""
        self._last_popped = None

    def is_empty(self) -> bool:
        """Returns True if the queue contains no pending items.

        Returns:
            bool: True if empty, False otherwise.
        """
        if self._queue:
            return False
        return True

    def clear(self) -> None:
        """Removes all pending items from the queue without notifying consumers."""
        self._queue.clear()



class VoiceService:

    _vol:float = 0.5
    _speech_rate: float = 1.2       # length_scale in SynthesisConfig = speech rate (higher is slower)
    _nsscale: float = 0.667
    _nswscale: float = 0.8
    _normaudio: bool = True
    # In theory, smaller chunk sizes will result in faster 
    # voice interruptions
    CHUNK_SIZE: int = 256

    def __init__(self, voice_engine: PiperVoice, enable: bool = True, cfg: SynthesisConfig | None = None):
        """
        voice_engine: Your text-to-speech synthesizer instance.
        voice_config: Configuration for the voice synthesizer.
        """
        self._voice = voice_engine
        self._enable = enable

        if cfg:
            self._vol = cfg.volume if cfg.volume else self._vol
            self._speech_rate = cfg.length_scale if cfg.length_scale else self._speech_rate
            self._nsscale = cfg.noise_scale if cfg.noise_scale else self. _nsscale
            self._nswscale = cfg.noise_w_scale if cfg.noise_w_scale else self._nswscale
            self._normaudio = cfg.normalize_audio

        self._cfg: SynthesisConfig = SynthesisConfig(length_scale=self._speech_rate, 
                               noise_scale=self._nsscale, 
                               noise_w_scale=self._nswscale, 
                               normalize_audio=self._normaudio, 
                               volume=self._vol)

        self._voice_queue: BlockingMap[VoiceType, Iterable[AudioChunk] | None] = BlockingMap()
        self._is_running = True
        self._interrupt = threading.Event()
        
        # Start the persistent audio worker
        threading.Thread(target=self._voice_worker, daemon=True).start()

    def current_cfg(self) -> SynthesisConfig:
        """Returns the active SynthesisConfig used for speech synthesis.

        Returns:
            SynthesisConfig: Current synthesis configuration.
        """
        return self._cfg

    def update_cfg(self, new_cfg: SynthesisConfig | None = None, enable: bool | None = None) -> None:
        """Replaces the synthesis config and/or the enabled flag without restarting the worker thread.

        Args:
            new_cfg (SynthesisConfig | None): New configuration to apply. Unchanged if None.
            enable (bool | None): New enabled state. Unchanged if None.
        """
        self._enable = enable if enable is not None else self._enable
        self._cfg = new_cfg if new_cfg is not None else self._cfg

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
                # self._voice_queue.clear() # TODO: clear queue or no?
            return interrupt
        
        while self._is_running:
            # This uses your BlockingMap's pop function
            voicetype, audio = self._voice_queue.pop() 

            if not self._enable:
                continue
            
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
                        for i in range(0, len(raw), self.CHUNK_SIZE):
                            if check_interrupt():
                                break
                            stream.write(raw[i:i + self.CHUNK_SIZE])

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
            snt = self._voice.synthesize(text, syn_config=self._cfg)
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

    def __init__(self, voice_path: str, event_bus: EventBus, enable: bool = True):
        """Loads the Piper voice model and wires all EventBus subscriptions to announcement methods.

        Args:
            voice_path (str): Path to the Piper voice model file.
            event_bus (EventBus): Application-wide event bus to subscribe to.
            enable (bool): Whether voice announcements are active on startup. Defaults to True.
        """
        voice_service = VoiceService(PiperVoice.load(voice_path))
        self._vpath: str = voice_path
        self._voice: VoiceService = voice_service
        self._enable: bool = enable
        
        # Wire up the event subscriptions

        # Announces that a track has been selected
        event_bus.subscribe(EventType.TRACK_SELECT, lambda name: self.announce_name(name))
        # Announces that project has been saved
        event_bus.subscribe(EventType.PROJ_SAVED, self.announce_saved)
        # Announces new metronome status
        event_bus.subscribe(EventType.METR_TOGGLE, lambda is_on: self.announce_metronome(is_on))
        # Announces new BPM value
        event_bus.subscribe(EventType.BPM_MOD, lambda bpm: self.announce_bpm(bpm))
        # Announces that recording has stopped
        event_bus.subscribe(EventType.REC_STOP, self.announce_recording_stopped)
        # Announces mute state of track
        event_bus.subscribe(EventType.TRACK_MUTE, lambda track_name, is_muted: self.announce_track_muted(track_name, is_muted))
        # Announce current state (TODO: improve this)
        event_bus.subscribe(EventType.STAT_REQ, lambda metronome_status, bpm: self.announce_current_state(metronome_status, bpm))
        # Loading project with specific name
        event_bus.subscribe(EventType.PROJ_LOAD, lambda name: self.announce_loading_proj(name))
        # MIDI input updated
        event_bus.subscribe(EventType.MIDI_UPD, lambda name: self.announce_sel_midiin(name))
        # MIDI input disconnected
        event_bus.subscribe(EventType.MIDI_DISC, lambda name: self.announce_disc_midiin(name))
        # Instrument groups cycling mode
        event_bus.subscribe(EventType.GR_SEL, lambda name: self.announce_group_sel(name))
        # Instrument list cycling mode
        event_bus.subscribe(EventType.INSTR_SEL, self.announce_instr_sel)
        # Hint for adding new track
        event_bus.subscribe(EventType.TR_HINT, self.hint_new_track)
        # Hint for saving project
        event_bus.subscribe(EventType.SAVE_HINT, self.hint_save_proj)
        # New track announcement
        event_bus.subscribe(EventType.TR_ADD, lambda name: self.announce_new_track(name))
        # New group selected
        event_bus.subscribe(EventType.GR_NAME, lambda name: self.announce_name(name))

        # Only for general errors
        event_bus.subscribe(EventType.ERR, lambda error: self._voice.speak(VoiceType.ERROR, error))


    # Update voice settings
    def update_settings(self, cfg: dict) -> None:
        """
        Updates voice settings.
        
        To see which values can be updated by the UI, 
        check main_window.py: VoiceConfigDialog.get_values
        """

        self._enable = cfg.get("enabled", self._enable)
        
        # Get current voice config
        voice_config = self._voice.current_cfg()

        # Update speech rate
        if (rate := cfg.get("rate")) is not None:
            voice_config.length_scale = 1/rate
            
        # Update volume
        if (volume := cfg.get("volume")) is not None:
            voice_config.volume = volume

        # Init new voice with updated settings
        self._voice.update_cfg(voice_config, self._enable)



    def shutdown(self) -> None:
        """Disables voice output and cleanly stops the audio worker thread."""
        if self._enable:
            self._enable = False
            self._voice.shutdown()



    # ----------------------------------------
    # Voice announcements of individual events
    # ----------------------------------------

    # INTERRUPTS
    def announce_new_track(self, name: str) -> None:
        if self._voice.currently_speaking():
            self._voice.interrupt()
        self._voice.speak(VoiceType.TRACK_NAME, f"Nouveau track: {name}")

    def announce_saved(self) -> None:
        self._voice.speak(VoiceType.PROJ_SAVE, "Projet sauvegardé")
        
    # INTERRUPTS
    def announce_metronome(self, is_on: bool) -> None:
        if self._voice.currently_speaking():
            self._voice.interrupt()
        msg = "Métronome activé" if is_on else "Métronome désactivé"
        self._voice.speak(VoiceType.METR_TOGGLE, msg)

    # INTERRUPTS
    def announce_group_sel(self, name: str) -> None:
        if self._voice.currently_speaking():
            self._voice.interrupt()
        self._voice.speak(VoiceType.GR_SEL, f"Séléction de groupe: {name}.")

    # INTERRUPTS
    def announce_instr_sel(self) -> None:
        if self._voice.currently_speaking():
            self._voice.interrupt()
        self._voice.speak(VoiceType.INSTR_SEL, "Séléction d'instruments.")

    def hint_new_track(self) -> None:
        self._voice.speak(VoiceType.HINT, "Appuyez à nouveau vers le bas pour rajouter une piste.")

    def hint_save_proj(self) -> None:
        self._voice.speak(VoiceType.HINT, "Appuyez à nouveau vers le haut pour sauvegarder le projet.")

    # INTERRUPTS
    def announce_bpm(self, bpm: int) -> None:
        if self._voice.currently_speaking():
            self._voice.interrupt()
        self._voice.speak(VoiceType.BPM_MOD, f"B P M {bpm}")
        
    # INTERRUPTS
    def announce_recording_stopped(self) -> None:
        if self._voice.currently_speaking():
            self._voice.interrupt()
        self._voice.speak(VoiceType.REC_STOP, "Enregistrement arrêté.")

    # INTERRUPTS
    def announce_track_muted(self, track_name: str, is_muted: bool) -> None:
        if self._voice.currently_speaking():
            self._voice.interrupt()
        status = "muté" if is_muted else "démuté"
        self._voice.speak(VoiceType.TRACK_INFO, f"{track_name} {status}")
    
    def announce_current_state(self, metronome_status: bool, bpm: int) -> None:
        """announce current BPM and metronome status on demand"""
        status = "activé" if metronome_status else "désactivé"
        self._voice.speak(VoiceType.METR_INFO, f"Métronome actuellement {status}.")
        self._voice.speak(VoiceType.BPM_INFO, f"B P M actuel: {bpm}.")

    # INTERRUPTS
    def announce_loading_proj(self, name: str) -> None:
        if self._voice.currently_speaking():
            self._voice.interrupt()
        self._voice.speak(VoiceType.PROJ_INFO, f"Chargement du projet {name}.")

    # INTERRUPTS
    def announceb_new_proj(self) -> None:
        if self._voice.currently_speaking():
            self._voice.interrupt()
        self._voice.speak(VoiceType.PROJ_INFO, "Nouveau Projet")

    # INTERRUPTS
    def announce_name(self, name: str, interrupt: bool=True) -> None:
        if self._voice.currently_speaking() and interrupt:
            self._voice.interrupt()
        self._voice.speak(VoiceType.NAME, name)

    def announce_started(self) -> None:
        self._voice.speak(VoiceType.WELCOME, "Menu de démarrage. Nouveau projet.")

    def welcome(self) -> None:
        self._voice.speak(VoiceType.WELCOME, "Bienvenue dans le studio.")

    def announce_sel_midiin(self, midi_name: str) -> None:
        self._voice.speak(VoiceType.MIDI_IN, f"ine poute MIDI sélectionné: {midi_name}")

    def announce_no_menu_ctr(self, name: str | None) -> None:
        if name:
            self._voice.speak(VoiceType.MIDI_IN, f"L'ine poute {name} est incompatible avec le menu de démarrage, veuillez utiliser le clavier.")
        else:
            self._voice.speak(VoiceType.MIDI_IN, "Aucun ine poute MIDI trouvé, veuillez utiliser le clavier pour naviguer le menu de démarrage.")

    def announce_disc_midiin(self, midi_name: str) -> None:
        self._voice.speak(VoiceType.MIDI_IN, f"ine poute MIDI {midi_name} déconnecté.")

    def announce_no_sf2(self) -> None:
        self._voice.speak(VoiceType.ERROR, "Pas d'instrument détecté. Veuiller placer des fichier soundfont dans le dossier S F 2. Appuyez sur entrée pour scanner à nouveau")

    # INTERRUPTS
    def announce_vsett_opened(self) -> None:
        # Temporarily re-enable voice upon voice settings open
        self._voice.update_cfg(enable=True)
        if self._voice.currently_speaking():
            self._voice.interrupt()

        self._voice.speak(VoiceType.VSETT_W, "Ouverture de la fenêtre de réglages pour la voix.")

    # INTERRUPTS
    def announce_vsett(self, sett: str, value: float) -> None:

        if self._voice.currently_speaking():
            self._voice.interrupt()

        if sett == SETTING_NAMES[0]: # enabled button
            enabled = value >= 0.0
            msg = "Voix activée." if enabled else "Voix désactivée."
            self._voice.speak(VoiceType.VSETT, msg)
        elif sett == SETTING_NAMES[1]: # rate slider
            limit = ""
            if value == RATE_STEPS[0]:
                limit += "Valeur minimale."
            elif value == RATE_STEPS[len(RATE_STEPS)-1]:
                limit += "Valeur maximale."
            self._voice.speak(VoiceType.VSETT, f"Vitesse de parole à {value}. {limit}")
        elif sett == SETTING_NAMES[2]: # volume slider
            self._voice.speak(VoiceType.VSETT, f"Volume de parole à {value} sur 1.")
        else:
            pass # TODO error handling ?

    # INTERRUPTS
    def announce_vsett_closed(self, changed: bool) -> None:

        if self._voice.currently_speaking():
            self._voice.interrupt()

        if changed:
            self._voice.speak(VoiceType.VSETT_W, "Sauvegarde des nouveaux réglages de la voix.")
        else:
            self._voice.speak(VoiceType.VSETT_W, "Annulation des modifications aux réglages de la voix.")