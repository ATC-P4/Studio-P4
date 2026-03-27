import fluidsynth
#classes definition
class Track:
    def __init__(self, name, midi_file_name=None, sf2_file_name="basic_piano.SF2"):
        self.name = name
        self.length = 0 # number of measures
        self.midi_file_name = midi_file_name
        self.sf2_file_name = sf2_file_name
        self.fs = fluidsynth.Synth()

        # auto-run on object creation
        self.initialize_synth()

    #initialize the synthesizer with the default soundfont, can be called again to change the soundfont on the fly
    def initialize_synth(self):
        self.fs.start(driver="wasapi")  # or dsound
        sfid = self.fs.sfload(self.sf2_file_name)
        self.fs.program_select(0, sfid, 0, 0)

    #update the soundfont used by the track, call after changing the sf2_file_name attribute to apply the change
    def update_soundfont(self, sf2_file_name):
        self.sf2_file_name = sf2_file_name
        sfid = self.fs.sfload(self.sf2_file_name)
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
