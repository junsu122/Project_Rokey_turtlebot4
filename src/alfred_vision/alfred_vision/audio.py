from builtin_interfaces.msg import Duration
from irobot_create_msgs.msg import AudioNote, AudioNoteVector

SOUND_AMBULANCE = [
    (880, 0, 300_000_000),
    (440, 0, 300_000_000),
    (880, 0, 300_000_000),
    (440, 0, 300_000_000),
    (880, 0, 300_000_000),
    (440, 0, 300_000_000),
]

SOUND_POLICE = [
    (660, 0, 500_000_000),
    (880, 0, 500_000_000),
    (660, 0, 500_000_000),
    (880, 0, 500_000_000),
]


def make_audio_msg(pattern):
    msg = AudioNoteVector()
    msg.append = False
    for freq, sec, nsec in pattern:
        note = AudioNote()
        note.frequency = freq
        note.max_runtime = Duration(sec=sec, nanosec=nsec)
        msg.notes.append(note)
    return msg


def make_silence_msg():
    msg = AudioNoteVector()
    msg.append = False
    return msg
