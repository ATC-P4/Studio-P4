import os
import fluidsynth as fs_cls
import platform

class Track:
    def __init__(self, name:str, midi_file_name:str = "", sf2_file_name:str ="basic_piano.SF2"):
        self.name = name
        self.length = 0 # number of bars
        self.midi_file_name = midi_file_name
        self.sf2_file_name = sf2_file_name
        self.fs: fs_cls.Synth = fs_cls.Synth()
        self.channel = 0

        self.sfid = -1

        # auto-run on object creation
        self.initialize_synth()

    #initialize the synthesizer with the default soundfont, can be called again to change the soundfont on the fly
    def initialize_synth(self) -> None:

        # TODO (Audio driver selection): let it choose some default value and see what happens for now
        # dev = self.fs.audio_driver
        # print(f"audio driver: {dev}")
        self.fs.start(driver="coreaudio")
        # Supported on Mac: coreaudio, file, portaudio
        # Windows: wasapi, dsound

        self.sfid = self.fs.sfload(self.sf2_file_name)
        # print(f"SFID:{self.sfid}")
        # Channel may be wrong initially, but this doesn't matter
        self.fs.program_select(self.channel, self.sfid, 0, 0)
        self.fs.setting('synth.gain', 1.0)

    #update the soundfont used by the track, call after changing the sf2_file_name attribute to apply the change
    def update_soundfont(self, channel: int, sf2_file_name: str="") -> None:
        self.sf2_file_name = sf2_file_name

        if sf2_file_name:
            self.sfid = self.fs.sfload(self.sf2_file_name)

        self.fs.program_select(channel, self.sfid, 0, 0)

    def play_note(self, msg):
        # Optional live monitoring through fluidsynth
        if msg.type == "note_on":
            self.fs.noteon(self.channel, msg.note, msg.velocity)
        elif msg.type == "note_off":
            self.fs.noteoff(self.channel, msg.note)
        elif msg.type == "program_change":
            self.fs.program_change(self.channel, msg.program)


class Project:
    def __init__(self, pname, bpm=120, tpb=480,t_s=(4,4)):
        self.pname = pname #name of the project
        self.bpm = bpm #beats per minutes
        self.tpb = tpb # tiks per beat, value of resolution
        self.time_signature = t_s #tuple with the fraction numbers
        self.tracks = [] #list of tracks

    def add_track(self, track_name):
        track = Track(track_name)#, sf2_file_name="arachno_soundfont_v1.0.sf2")
        self.tracks.append(track)
        return track
