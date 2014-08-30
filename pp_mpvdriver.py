import pexpect
import re
import sys

from threading import Thread
from time import sleep
from pp_utils import Monitor

"""
 pyomxplayer from https://github.com/jbaiter/pyomxplayer
 extensively modified by KenT

 playerDriver hides the detail of using the mpv command  from audioplayer
 This is meant to be used with pp_audioplayer.py
 Its easy to end up with many copies of mpv running if this class is not used with care.
 use pp_audioplayer.py for a safer interface.


 External commands
 ----------------------------
 __init__ just creates the instance and initialises variables (e.g. mpv=playerDriver())
 play      - plays a track
 pause     - toggles pause
 control   - sends controls to mpv while a track is playing (use stop and pause instead of q and p)
 stop      - stops a video that is playing.
 terminate - Stops a video playing. Used when aborting an application.

 Advanced:
 prepare  - processes the track up to where it is ready to display, at this time it pauses.
 show     - plays the video from where 'prepare' left off by resuming from the pause.


Signals
----------
 The following signals are produced while a track is playing
         self.start_play_signal = True when a track is ready to be shown
         self.end_play_signal= True when a track has finished due to stop or because it has come to an end
 Also is_running() tests whether the sub-process running mpv is alive.

mpv -no-border -geometry 960x540+480+270 -ao alsa:device=[hw:1,0] --hwdec vdpau ~/Desktop/big_buck_bunny_1080p_H264_AAC_25fps_7200K.MP4

kill pulseaudio
-ao alsa:device=[hw:0,0] = headphones
-ao alsa:device=[hw:1,0] = hdmi

"""

class playerDriver(object):

    _STATUS_REXP = re.compile(r"V :\s*([\d.]+).*")
    _DONE_REXP = re.compile(r"Exiting*")
    # audio mixer matrix settings
    _LEFT   = "channels=2:1:0:0:1:1"
    _RIGHT  = "channels=2:1:0:1:1:0"
    _STEREO = "channels=2"

    _LAUNCH_CMD = 'mpv -quiet -no-border --hwdec vdpau '

    def __init__(self, widget):

        self.widget = widget
        self.mon    = Monitor()
        self.mon.off()
        self._process = None
        self.paused   = None
        self.options  = []
        self.af_options = []

    def control(self, char):
        if self._process:
            self._process.send(char)

    def set_audio(self, val):
        if val == "hdmi":
            self.options.append("-ao alsa:device=[hw:1,0]")
        else:
            self.options.append("-ao alsa:device=[hw:0,0]")

    def set_volume(self, val):
        if val != "":
            self.mon.log(self, "playerDriver: set_volume not implemented")

    def set_speaker(self, val):
        if val != "":
            if val == 'left':
                self.af_options.append(playerDriver._LEFT)
            elif val == 'right':
                self.af_options.append(playerDriver._RIGHT)
            else:
                self.af_options.append(playerDriver._STEREO)

    def set_window(self, val):
        if val != "":
            fields = val.split()
            self.options.append("-geometry " + str(int(fields[2]) - int(fields[0])) + '+' + str(int(fields[3]) - int(fields[1])) + '+' + str(fields[0]) + '+' + str(fields[1]))

    def add_options(self, val):
        if val != "":
            self.options.append(str(val))

    def pause(self):
        if self._process:
            self._process.send('p')
            if not self.paused:
                self.paused = True
            else:
                self.paused = False

    def play(self, track):
        self._pp(track, False)

    def prepare(self, track):
        self._pp(track, True)

    def show(self):
        # unpause to start playing
        if self._process:
            self._process.send('p')
            self.paused = False

    def stop(self):
        if self._process:
            self._process.send('q')

    # kill the subprocess (mpv). Used for tidy up on exit.
    def terminate(self, reason):
        self.terminate_reason = reason
        if self._process:
           self._process.send('q')
        else:
            self.end_play_signal = True

    def terminate_reason(self):
        return self.terminate_reason

   # test of whether _process is running
    def is_running(self):
        return self._process.isalive()

# ***********************************
# INTERNAL FUNCTIONS
# ************************************

    def _pp(self, track, pause_before_play):
        self.paused            = False
        self.start_play_signal = False
        self.end_play_signal   = False
        self.terminate_reason  = ''
        track = "'" + track.replace("'", "'\\''") + "'"
        cmd   = playerDriver._LAUNCH_CMD + ' '
        if len(self.options):
            cmd += ' '.join(self.options) + ' '
        if len(self.af_options):
            cmd += '-af ' + ','.join(self.af_options) + ' '
        cmd += track
        self.mon.log(self, "Send command to mpv: " + cmd)
        self._process = pexpect.spawn(cmd)

        # uncomment to monitor output to and input from mpv (read pexpect manual)
        # fout= file('/home/pi/pipresents/mpvlogfile.txt','w')  #uncomment and change sys.stdout to fout to log to a file
        # self._process.logfile_send = sys.stdout  # send just commands to stdout
        # self._process.logfile=fout  # send all communications to log file

        if pause_before_play:
            self._process.send('p')
            self.paused = True

        #start the thread that is going to monitor sys.stdout. Presumably needs a thread because of blocking

        self._position_thread = Thread(target = self._get_position)
        self._position_thread.start()

    def _get_position(self):
        self.start_play_signal = True
        self.video_position    = 0.0
        self.audio_position    = 0.0

        while True:
            index = self._process.expect([playerDriver._STATUS_REXP,
                                            pexpect.TIMEOUT,
                                            pexpect.EOF,
                                            playerDriver._DONE_REXP])
            if index == 1:
                continue            # timeout - it doesn't block so is a thread needed?
            elif index in (2, 3):
                #Exiting
                self.end_play_signal = True
                break
            else:
                # presumably matches _STATUS_REXP so get video position
                # has a bug, position is not displayed for an audio track (mp3). Need to look at another field in the status, but how to extract it
                #self.video_position = float(self._process.match.group(1))
                self.audio_position = 0.0
            sleep(0.05)

