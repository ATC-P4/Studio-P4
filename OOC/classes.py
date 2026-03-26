class Track:
    def __init__(self, name, midi_file_name=None, sf2_file_name="basic_piano.SF2"):
        self.name = name
        self.length = 0 # number of measures
        self.midi_file_name = midi_file_name
        self.sf2_file_name = sf2_file_name


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
