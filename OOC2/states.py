
#list of global variables that define the state of the program, used for communication between threads and functions
last_msg_time = None #timestamp of the last received MIDI message, used to calculate time deltas for recording
m_p = None #main project object, holds the project settings and tracks
s_t = None #selected track object, holds the track settings and MIDI data
midi_track = None #MIDI track object from mido, used to store recorded MIDI messages
recorded_ticks = 0 #counter for the number of ticks recorded, used to determine when to stop recording based on track length and tempo

#flags
terminate_flag = False #flag to signal threads to stop
record_flag = False #flag to control recording state
