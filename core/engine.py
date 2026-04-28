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
        """Sets the state of the engine."""
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
                
        elif new_state in ["COUNT_IN", "RECORDING", "PLAYING"]:
            # Wipe armed track if starting a new recording
            if new_state in ["COUNT_IN", "RECORDING"]:
                if armed_track and self.current_state != "RECORDING":
                    armed_track.clear_events() 
                    print(f"[ENGINE] Track '{armed_track.name}' wiped upon entering {new_state}.")
            
            # CRITICAL FIX: If we are starting from STOPPED, we must reset the timeline
            if self.current_state == "STOPPED":
                self._pending_clock_reset = True

        # 3. Apply State
        self.current_state = new_state
        if self.on_state_change_cb:
            self.on_state_change_cb()

    def _calculate_master_loop(self, armed_track) -> None:
        """
        Calculates and locks the master loop length based on recorded beats.
        This is called when stopping a recording session if the armed track is the master.
        It uses the elapsed recording time to determine how many beats were recorded, then snaps to the nearest bar.
         Args:
             armed_track: The currently armed track which is being recorded. Used to determine if it's the master and to flush notes if needed.
        """
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
        """
        Closes any MIDI notes that were held down when recording stopped.
        This prevents "hanging" notes that continue to play indefinitely after recording stops.
         Args:
             armed_track: The currently armed track which is being recorded.
        """
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
        """Set a specific state for the metronome

        Args:
            state (bool): State, True=on, False=off
        """
        self.metronome_on = state

    def get_metronome_state(self) -> bool:
        """
        Returns the current state of the metronome
        """
        return self.metronome_on

   
    def _clock_loop(self):
        """This is the heart of the engine, running in a dedicated thread."""
        LOOKAHEAD_SEC = 0.05 
        while self._engine_alive:
            if self.current_state == "STOPPED":
                time.sleep(0.1) 
                continue
            
            if self._pending_clock_reset:
                self._reset_clock()

            now = time.perf_counter()
            elapsed = now - self.start_time
            target_time = elapsed + LOOKAHEAD_SEC
            
            # CRITICAL FIX: Only process if target_time has advanced past last_processed_time.
            # This allows our 100ms pre-roll buffer to tick down smoothly without breaking the math.
            if target_time > self.last_processed_time:
                
                if self.current_state == "COUNT_IN":
                    count_in_duration = self.project.time_signature_numerator * self.project.beat_duration
                    
                    if target_time >= count_in_duration:
                        self._transition_to_recording(count_in_duration, elapsed, LOOKAHEAD_SEC, now)
                    else:
                        self._process_playback(self.last_processed_time, target_time, elapsed)
                        self.last_processed_time = target_time
                
                elif self.current_state in ["PLAYING", "RECORDING"]:
                    self._process_playback(self.last_processed_time, target_time, elapsed)
                    self.last_processed_time = target_time
                
            time.sleep(LOOKAHEAD_SEC / 2.0)
    
    def _reset_clock(self):
        """Safely resets the engine time variables to zero with a pre-roll buffer."""
        # CRITICAL FIX: Add a 100ms (0.1s) buffer. 
        # By setting the start_time slightly in the future, we give the clock loop 
        # time to calculate the 0.0 notes and push them to the dispatcher BEFORE they are due.
        self.start_time = time.perf_counter() + 0.1
        self.last_processed_time = 0.0
        with self.queue_lock:
            self.audio_queue.clear()
        self._pending_clock_reset = False

    def _transition_to_recording(self, count_in_duration: float, elapsed: float, lookahead: float, now: float):
        """Handles the complex timeline shift when switching from Count-In to live Recording."""
        # A. Process the exact remaining sliver of the Count-In
        self._process_playback(self.last_processed_time, count_in_duration, elapsed)
        
        # B. Shift the timeline back mathematically
        self.start_time += count_in_duration
        elapsed = now - self.start_time  
        target_time = elapsed + lookahead 
        
        # C. Change State seamlessly
        self.current_state = "RECORDING"
        if self.on_state_change_cb:
            self.on_state_change_cb()
            
        # D. Wipe the track to prevent count-in bleed
        armed_track = self.project.get_armed_track()
        if armed_track:
            armed_track.clear_events()
            print(f"[ENGINE] Track '{armed_track.name}' wiped perfectly at the downbeat.")
        
        # E. Process the beginning of the actual recording
        self._process_playback(0.0, target_time, elapsed)
        self.last_processed_time = target_time


    def _dispatcher_loop(self):
        """Continuously checks the audio queue and executes any events that are due to play."""
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
        """Puts a note into the Priority Queue with strict tie-breaking.
         Args:             
            delay_sec: How many seconds in the future this event should play.
            action: "NOTE_ON", "NOTE_OFF", or "METRO"
            obj: The Track or Metronome object that should execute the action.
            note: MIDI note number for the event (or downbeat flag for metronome)
            vel: MIDI velocity for note_on events (default 0 for note_off or metronome)
        """
        exec_time = time.perf_counter() + delay_sec
        priority = 1
        if action == "NOTE_OFF": priority = 0
        elif action == "NOTE_ON": priority = 2
        
        with self.queue_lock:
            heapq.heappush(self.audio_queue, (exec_time, priority, self.event_counter, action, obj, note, vel))
            self.event_counter += 1

    def _process_playback(self, start_window: float, end_window: float, actual_elapsed: float) -> None:
        """
        Schedules all upcoming audio events within the current time window.
         Args:
             start_window: The start of the lookahead window in seconds.
             end_window: The end of the lookahead window in seconds.
             actual_elapsed: The actual elapsed time in seconds.
        """
        
        loop_duration = self._calculate_loop_duration()

        self._schedule_metronome(start_window, end_window, actual_elapsed)

        if self.current_state == "COUNT_IN":
            return # Don't play track notes during count-in
        
        self._schedule_tracks(start_window, end_window, actual_elapsed, loop_duration)

    def _calculate_loop_duration(self) -> float:
        """
        Determines the current loop length in seconds based on master track status.
        """
        armed_track = self.project.get_armed_track()
        is_master = (self.project.master_track is None or self.project.master_track == armed_track)

        if self.current_state == "RECORDING" and is_master:
            return float('inf') # Master is currently defining the loop length
        elif self.project.master_loop_beats > 0:
            return self.project.master_loop_beats * self.project.beat_duration
        else:
            return self.project.time_signature_numerator * self.project.beat_duration

    def _schedule_metronome(self, start_window: float, end_window: float, actual_elapsed: float) -> None:
        """
        Schedules metronome clicks if they fall within the current time window.
         Args:
             start_window: The start of the lookahead window in seconds.
             end_window: The end of the lookahead window in seconds.
             actual_elapsed: The actual elapsed time in seconds.
        """
        should_click = self.current_state in ["COUNT_IN", "RECORDING"] or \
                      (self.current_state == "PLAYING" and self.metronome_on)
        
        if not should_click:
            return

        # Start checking from the nearest beat
        first_beat = math.ceil(start_window / self.project.beat_duration)
        beat_time = first_beat * self.project.beat_duration
        
        while beat_time < end_window:
            delay_sec = beat_time - actual_elapsed
            is_downbeat = (first_beat % self.project.time_signature_numerator == 0)
            self._schedule_event(delay_sec, "METRO", self.project.metronome, is_downbeat)
            
            first_beat += 1
            beat_time = first_beat * self.project.beat_duration

    def _schedule_tracks(self, start_window: float, end_window: float, actual_elapsed: float, loop_duration: float) -> None:
        """
        Iterates through all tracks and schedules their MIDI notes via modulo arithmetic.
         Args:
             start_window: The start of the lookahead window in seconds.
             end_window: The end of the lookahead window in seconds.
             actual_elapsed: The actual elapsed time in seconds.
             loop_duration: The duration of the loop in seconds.
        """
        for track in self.project.tracks:
            if track.is_muted: 
                continue

            with track.event_lock:
                for msg, timestamp in track.midi_events:
                    
                    # 1. Calculate when this note should play in absolute time
                    if loop_duration == float('inf'):
                        play_time = timestamp
                    else:
                        ts_mod = timestamp % loop_duration
                        current_loop_start = (start_window // loop_duration) * loop_duration
                        play_time = current_loop_start + ts_mod
                        if play_time < start_window:
                            play_time += loop_duration

                    # 2. Schedule it if it falls in our current lookahead window
                    if start_window <= play_time < end_window:
                        delay_sec = play_time - actual_elapsed
                        
                        if msg.type == 'note_on' and msg.velocity > 0:
                            self._schedule_event(delay_sec, "NOTE_ON", track, msg.note, msg.velocity)
                        else:
                            self._schedule_event(delay_sec, "NOTE_OFF", track, msg.note)

    