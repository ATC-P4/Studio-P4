from core import models
import time
import threading
import math
import heapq
import mido

class MasterClockEngine:
    def __init__(self, project):
        self.project : models.Project = project
        self.current_state = "STOPPED" 
        self.start_time = 0.0
        self.metronome_on = False
        self.last_processed_time = 0.0
        self.on_state_change_cb = None 
        
        self.audio_queue = []
        self.queue_lock = threading.Lock()
        self.event_counter = 0 
        
        # --- NEW: Thread-Safe Reset Flag ---
        self._pending_clock_reset = False

        # START THREADS ONCE AND LEAVE THEM RUNNING
        self._engine_alive = True 
        threading.Thread(target=self._clock_loop, daemon=True).start()
        threading.Thread(target=self._dispatcher_loop, daemon=True).start() 

    def set_state(self, new_state: str) -> None:
        armed_track = self.project.get_armed_track()
        is_master = (self.project.master_track is None or self.project.master_track == armed_track)

        # 1. Handle transitions FROM Recording
        if self.current_state == "RECORDING" and new_state in ["PLAYING", "STOPPED"]:
            if is_master:
                self._calculate_master_loop(armed_track)
            self._sanitize_open_notes(armed_track)

        # 2. Handle specific state preparations
        if new_state == "STOPPED":
            for track in self.project.tracks:
                track.flush_notes()
            with self.queue_lock:
                self.audio_queue.clear()
                
        elif new_state in ["COUNT_IN", "RECORDING"]:
            if armed_track:
                armed_track.clear_events() # Use the new thread-safe method (see Step 4)
                print(f"[ENGINE] Track '{armed_track.name}' wiped upon entering {new_state}.")
            
            if self.current_state in ["STOPPED", "COUNT_IN"] or (new_state == "RECORDING" and is_master):
                self._pending_clock_reset = True

        # 3. Apply State
        self.current_state = new_state
        if self.on_state_change_cb:
            self.on_state_change_cb()

    def _calculate_master_loop(self, armed_track) -> None:
        """Calculates and locks the master loop length based on recorded beats."""
        elapsed_seconds = time.perf_counter() - self.start_time
        beats_recorded = elapsed_seconds / self.project.beat_duration
        time_sig = self.project.time_signature_numerator
        
        lower_bound_beats = math.floor(beats_recorded / time_sig) * time_sig
        excess_beats = beats_recorded - lower_bound_beats
        
        calculated_beats = lower_bound_beats + time_sig if excess_beats > 1.0 else lower_bound_beats
        
        self.project.master_loop_beats = max(time_sig, calculated_beats)
        self.project.master_track = armed_track
        print(f"[ENGINE] Master Loop locked at {self.project.master_loop_beats} beats.")

    def _sanitize_open_notes(self, armed_track) -> None:
        """Closes any MIDI notes that were held down when recording stopped."""
        if not armed_track: return
        
        open_notes = set()
        elapsed_seconds = time.perf_counter() - self.start_time
        
        # Access safely via a lock!
        with armed_track.event_lock:
            for msg, ts in armed_track.midi_events:
                if msg.type == 'note_on' and msg.velocity > 0:
                    open_notes.add(msg.note)
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    open_notes.discard(msg.note)
            
            for note in open_notes:
                fake_off = mido.Message('note_off', note=note, velocity=0, time=0)
                armed_track.midi_events.append((fake_off, elapsed_seconds))

    
    def set_metronome_state(self, state: bool):
        self.metronome_on = state

    def get_metronome_state(self) -> bool:
        return self.metronome_on

    # --- THREAD 1: The Timeline Calculator ---
    def _clock_loop(self):
        LOOKAHEAD_SEC = 0.05 
        while self._engine_alive:
            if self.current_state == "STOPPED":
                time.sleep(0.1) # Idle safely
                continue
            
            if self._pending_clock_reset:
                self.start_time = time.perf_counter()
                self.last_processed_time = 0.0
                with self.queue_lock:
                    self.audio_queue.clear()
                self._pending_clock_reset = False

            now = time.perf_counter()
            elapsed = now - self.start_time
            
            # Anchor target_time strictly to the REAL hardware clock
            target_time = elapsed + LOOKAHEAD_SEC
            
            if self.current_state == "COUNT_IN":
                count_in_duration = self.project.time_signature_numerator * self.project.beat_duration
                
                if target_time >= count_in_duration:
                    # A. Process the exact remaining sliver of the Count-In
                    self._process_playback(self.last_processed_time, count_in_duration, elapsed)
                    
                    # B. Shift the timeline back mathematically
                    self.start_time += count_in_duration
                    
                    # Re-evaluate the hardware clock variables for the new timeline
                    elapsed = now - self.start_time  
                    target_time = elapsed + LOOKAHEAD_SEC 
                    
                    # C. Change State seamlessly
                    self.current_state = "RECORDING"
                    if self.on_state_change_cb:
                        self.on_state_change_cb()
                        
                    # --- THE MISSING FIX: Wipe the track to prevent count-in bleed ---
                    armed_track = self.project.get_armed_track()
                    if armed_track:
                        armed_track.clear_events()
                        print(f"[ENGINE] Track '{armed_track.name}' wiped perfectly at the downbeat.")
                    
                    # D. Process the beginning of the actual recording
                    self._process_playback(0.0, target_time, elapsed)
                    self.last_processed_time = target_time
                else:
                    self._process_playback(self.last_processed_time, target_time, elapsed)
                    self.last_processed_time = target_time
            
            elif self.current_state in ["PLAYING", "RECORDING"]:
                self._process_playback(self.last_processed_time, target_time, elapsed)
                self.last_processed_time = target_time
                
            time.sleep(LOOKAHEAD_SEC / 2.0)


    # --- THREAD 2: The Instant Audio Trigger ---
    def _dispatcher_loop(self):
        while self._engine_alive:
            now = time.perf_counter()
            with self.queue_lock:
                while self.audio_queue and self.audio_queue[0][0] <= now:
                    exec_time, priority, count, action, obj, note, vel = heapq.heappop(self.audio_queue)
                    
                    if action == "NOTE_ON":
                        obj.play_note_on(note, vel)
                    elif action == "NOTE_OFF":
                        obj.play_note_off(note)
                    elif action == "METRO":
                        obj.play_click(note) 
            time.sleep(0.001)

    def _schedule_event(self, delay_sec, action, obj, note, vel=0):
        """Puts a note into the Priority Queue with strict tie-breaking."""
        exec_time = time.perf_counter() + delay_sec
        priority = 1
        if action == "NOTE_OFF": priority = 0
        elif action == "NOTE_ON": priority = 2
        
        with self.queue_lock:
            heapq.heappush(self.audio_queue, (exec_time, priority, self.event_counter, action, obj, note, vel))
            self.event_counter += 1

    def _process_playback(self, start_window: float, end_window: float, actual_elapsed: float):
        armed_track = self.project.get_armed_track()
        is_master = (self.project.master_track is None or self.project.master_track == armed_track)

        if self.current_state == "RECORDING" and is_master:
            loop_duration = float('inf')
        elif self.project.master_loop_beats > 0:
            loop_duration = self.project.master_loop_beats * self.project.beat_duration
        else:
            loop_duration = self.project.time_signature_numerator * self.project.beat_duration

        should_click = self.current_state in ["COUNT_IN", "RECORDING"] or (self.current_state == "PLAYING" and self.metronome_on)
        if should_click:
            first_beat = math.ceil(start_window / self.project.beat_duration)
            beat_time = first_beat * self.project.beat_duration
            
            while beat_time < end_window:
                delay_sec = beat_time - actual_elapsed
                is_downbeat = (first_beat % self.project.time_signature_numerator == 0)
                self._schedule_event(delay_sec, "METRO", self.project.metronome, is_downbeat)
                
                first_beat += 1
                beat_time = first_beat * self.project.beat_duration

        if self.current_state == "COUNT_IN":
            return
        
        for track in self.project.tracks:
            if track.is_muted: continue

            with track.event_lock:
                for msg, timestamp in track.midi_events:
                    if loop_duration == float('inf'):
                        absolute_play_time = timestamp
                    else:
                        ts_mod = timestamp % loop_duration
                        current_loop_start = (start_window // loop_duration) * loop_duration
                        absolute_play_time = current_loop_start + ts_mod
                        
                        if absolute_play_time < start_window:
                            absolute_play_time += loop_duration

                    if start_window <= absolute_play_time < end_window:
                        delay_sec = absolute_play_time - actual_elapsed

                        if msg.type == 'note_on' and msg.velocity > 0:
                            self._schedule_event(delay_sec, "NOTE_ON", track, msg.note, msg.velocity)
                        else:
                            self._schedule_event(delay_sec, "NOTE_OFF", track, msg.note)