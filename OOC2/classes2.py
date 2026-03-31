import os
import fluidsynth
import platform

class Track:
    def __init__(self, name, midi_file_name=None, sf2_file_name="basic_piano.SF2"):
        self.name = name
        self.length = 0 
        self.midi_file_name = midi_file_name
        
        # The file calculates its own absolute path
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.sf2_file_name = os.path.join(base_dir, sf2_file_name)
        
        self.fs = fluidsynth.Synth()
        self.initialize_synth()

    def initialize_synth(self):
        # Setting the volume of the sound
        self.fs.setting("synth.gain", 5.0)
        # Automatic driver choice (Mac or PC)
        driver = "coreaudio" if platform.system() == "Darwin" else "wasapi"
        self.fs.start(driver=driver)  
        
        # Safety measures against crashes
        sfid = self.fs.sfload(self.sf2_file_name)
        if sfid != -1:
            self.fs.program_select(0, sfid, 0, 0)
        else:
            print(f"ERREUR : Impossible de charger la banque de sons à {self.sf2_file_name}")

    def update_soundfont(self, sf2_file_name):
        self.sf2_file_name = sf2_file_name
        sfid = self.fs.sfload(self.sf2_file_name)
        if sfid != -1:
            self.fs.program_select(0, sfid, 0, 0)

class Project:
    def __init__(self, pname, bpm=120, tpb=480,t_s=(4,4)):
        self.pname = pname #name of the project
        self.bpm = bpm #beats per minutes
        self.tpb = tpb # tiks per beat, value of resolution
        self.time_signature = t_s #tuple with the fraction numbers
        self.tracks = [] #list of tracks

    def add_track(self, track_name):
        track = Track(track_name)
        self.tracks.append(track)
        return track
