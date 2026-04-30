import os
import json
import time
import mido
from core.utils import MidiExporter

class ProjectIO:
    """Handles saving and loading of the Project state and MIDI files."""

    @staticmethod
    def save(project, folder_name: str | None = None) -> None:
        """Exports tracks to MIDI and generates a project.json metadata file."""
        print("[PROJECT IO] Saving project...")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        
        import locale
       
        locale.setlocale(locale.LC_TIME, '')
        timestamp = time.strftime("le_%d_%B_a_%H_heure_%M")
        folder_name = folder_name or f"project_{timestamp}"
        base_dir = os.path.abspath(".")
        project_folder = os.path.join(base_dir, "Saves", folder_name)
        os.makedirs(project_folder, exist_ok=True)
        # 1. Export MIDI Files
        for track in project.tracks:
            full_path = os.path.join(project_folder, f"{track.name}.mid")
            MidiExporter.export_track(track, full_path, project.bpm, project.master_loop_beats)
        # 2. Build and Save Metadata JSON
        metadata = {
            "name": project.name,
            "bpm": project.bpm,
            "time_signature": project.time_signature,
            "master_loop_beats": project.master_loop_beats,
            "tracks": []
        }
        for track in project.tracks:
            metadata["tracks"].append({
                "name": track.name,
                "is_muted": track.is_muted,
                "volume": track.volume,
                "program_id": track.program_id,
                "sf2_filename": os.path.basename(track.sf2_path),
                "is_master": project.master_track == track
            })
# 2. Build and Save Metadata JSON
        metadata = {
            "name": project.name,
            "bpm": project.bpm,
            "time_signature": project.time_signature,
            "master_loop_beats": project.master_loop_beats,
            "tracks": []
        }

        # Determine the root sf2 directory
        sf2_dir = os.path.abspath("./sf2")

        for track in project.tracks:
            # FIX 5: Save the relative path so the folder name isn't lost
            try:
                rel_sf2 = os.path.relpath(track.sf2_path, sf2_dir)
            except ValueError:
                rel_sf2 = os.path.basename(track.sf2_path)

            metadata["tracks"].append({
                "name": track.name,
                "is_muted": track.is_muted,
                "volume": track.volume,
                "program_id": track.program_id,
                # Replace backslashes with forward slashes for safe JSON formatting
                "sf2_filename": rel_sf2.replace("\\", "/"), 
                "is_master": project.master_track == track
            })
        json_path = os.path.join(project_folder, "project.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
        print(f"[PROJECT IO] Project saved successfully to: {project_folder}")


    @staticmethod
    def load_into_project(project, folder_path: str) -> None:
        """Safely wipes the current project and rebuilds it from a saved folder."""
        json_path = os.path.join(folder_path, "project.json")
        if not os.path.exists(json_path):
            raise FileNotFoundError("project.json not found in the selected folder.")

        with open(json_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # 1. Reset Global State
        project.name = metadata["name"]
        project.bpm = metadata["bpm"]
        project.beat_duration = 60.0 / project.bpm
        project.time_signature = metadata.get("time_signature", (4, 4))
        project.time_signature_numerator = project.time_signature[0]
        project.master_loop_beats = metadata["master_loop_beats"]
        
        # Reset tracks and channels safely
        for track in project.tracks:
            track.flush_notes()
        project.tracks.clear()
        project.master_track = None
        project.available_channels = [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15]

        # 2. Rebuild Tracks
        for t_data in metadata["tracks"]:
            project.add_track(t_data["name"])
            track = project.tracks[-1] # The one we just added
            
            # Restore state
            track.is_muted = t_data["is_muted"]
            track.set_volume(t_data.get("volume", 100))
            track.set_soundfont(t_data["sf2_filename"])
            track.set_instrument(t_data["program_id"])
            
            if t_data.get("is_master"):
                project.master_track = track

            # 3. Import MIDI Data
            midi_path = os.path.join(folder_path, f"{track.name}.mid")
            if os.path.exists(midi_path):
                ProjectIO._import_midi_to_track(track, midi_path, project.bpm)
                
        print(f"[PROJECT IO] Project '{project.name}' loaded successfully.")


    @staticmethod
    def _import_midi_to_track(track, filepath: str, bpm: int, ticks_per_beat: int = 480) -> None:
        """Reverses MIDI ticks back into absolute seconds for the engine."""
        try:
            mid = mido.MidiFile(filepath)
            tempo = mido.bpm2tempo(bpm)
            absolute_time = 0.0
            
            with track.event_lock:
                for msg in mid.tracks[0]:
                    # Convert delta ticks to delta seconds
                    delta_seconds = mido.tick2second(msg.time, ticks_per_beat, tempo)
                    absolute_time += delta_seconds
                    
                    # CRITICAL FIX: Only import actual note events. 
                    # This safely ignores program_change, control_change, and meta messages.
                    if msg.type in ['note_on', 'note_off']:
                        track.midi_events.append((msg, absolute_time))
        except Exception as e:
            print(f"[PROJECT IO] Failed to load MIDI for {track.name}: {e}")
