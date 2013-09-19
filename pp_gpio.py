import time
import datetime
import copy
from Tkinter import *
import Tkinter as tk
import os
import re
import subprocess
import ConfigParser
from pp_utils import Monitor
from pp_options import command_options

class PP_GPIO:

    INPUT    = 0
    OUTPUT   = 1
    MODULE   = False
    GPIO     = False
    HARDWARE = False
    PINLIST  = False
    CFG      = False

    PINLIST_RPIV1 = ('P1-03', 'P1-05', 'P1-07', 'P1-08', 'P1-10',
                     'P1-11', 'P1-12', 'P1-13', 'P1-15', 'P1-16',
                     'P1-18', 'P1-19', 'P1-21', 'P1-22', 'P1-23',
                     'P1-24', 'P1-26')

    PINLIST_CB    = ('CB-01', 'CB-03', 'CB-04', 'CB-05', 'CB-06',
                     'CB-07', 'CB-08', 'CB-10', 'CB-11', 'CB-12',
                     'CB-13', 'CB-14', 'CB-15', 'CB-16', 'CB-17',
                     'CB-18', 'CB-19', 'CB-21', 'CB-22', 'CB-23',
                     'CB-24', 'CB-25', 'CB-26', 'CB-27', 'CB-28',
                     'CB-29', 'CB-30', 'CB-31', 'CB-32', 'CB-37',
                     'CB-39', 'CB-40', 'CB-45', 'CB-46', 'CB-47',
                     'CB-48', 'CB-50', 'CB-52', 'CB-53', 'CB-54',
                     'CB-55', 'CB-56', 'CB-57', 'CB-58', 'CB-59',
                     'CB-60', 'CB-61', 'CB-62', 'CB-63', 'CB-64',
                     'CB-65', 'CB-66', 'CB-70', 'CB-72', 'CB-74',
                     'CB-76', 'CB-78', 'CB-80', 'CB-82', 'CB-84',
                     'CB-86', 'CB-88', 'CB-90', 'CB-92', 'CB-94',
                     'CB-96')

    def __init__(self):
        if self.module_exists("RPi"):
            self.MODULE = "RPi"
            import RPi.GPIO as GPIO
        elif self.module_exists("wiringpi2"):
            self.MODULE = "WPi"
            import wiringpi2 as GPIO
        else:
            self.mon.log(self, "No i/o library found (RPi/wiringpi2)")
            return False

        self.GPIO = GPIO
        self.setup()

    def setup(self):
        if self.module == "RPi":
            self.GPIO.setwarnings(False)
            self.GPIO.setmode(self.GPIO.BOARD)
        elif self.module == "WPi":
            self.GPIO.wiringPiSetupSys()
            #self.GPIO.wiringPiSetup()
            self.GPIO.wiringPiSetupGpio()

        command = "cat /proc/cpuinfo"
        all_info = subprocess.check_output(command, shell=True).strip()
        for line in all_info.split("\n"):
            if "Hardware" in line:
                self.HARDWARE = re.sub( ".*Hardware.*:", "", line,1).strip()

        if self.HARDWARE == "BCM2708":
            # Raspberry PI
            self.PINLIST = self.PINLIST_RPIV1
            self.CFG     = "gpio_rpiv1.cfg"
        elif self.HARDWARE == "sun4i" or self.HARDWARE == "sun7i":
            # Cubieboard A10/A20
            self.PINLIST = self.PINLIST_CB
            self.CFG     = "gpio_cb.cfg"
        else:
            self.mon.log(self, "unknown Hardware")

    def cleanup(self):
        if self.module == "RPi":
            self.GPIO.cleanup()
        elif self.module == "WPi":
            # set all pins to input
            for pin in self.PINLIST:
                num = int(pin.split('-')[1:])
                self.pinMode(num,self.INPUT)

    def digitalWrite(self, num, val):
        if self.module == "RPi":
            self.GPIO.output(num, val)
        elif self.module == "WPi":
            self.GPIO.digitalWrite(num, val)

    def digitalRead(self, num):
        if self.module == "RPi":
            self.GPIO.input(num)
        elif self.module == "WPi":
            self.GPIO.digitalRead(num)

    def pinMode(self, num, mode, up_down):
        if mode == self.INPUT:
            if self.module == "RPi":
                self.GPIO.setup(num, mode, up_down)
            elif self.module == "WPi":
                self.GPIO.pinMode(num, mode)

        elif mode == self.OUTPUT:
            if self.module == "RPi":
                self.GPIO.setup(num, mode)
                self.digitalWrite(num, 0)
            elif self.module == "WPi":
                self.GPIO.pinMode(num, mode)
                self.digitalWrite(num, 0)

    def module_exists(module_name):
        try:
            __import__(module_name)
        except ImportError:
            return False
        else:
            return True

class PPIO:
    """
    PPIO provides some IO facilties for Pi presents
     - configures GPIO pins from data in gpio.cfg
     - reads and debounces inputs pins, provides callbacks on state changes which are used to trigger mediashows
     - for output pins allows players to put events, which request the change of state of pins, into a queue. Events are executed at the required time.
    """

# constants for buttons
# cofiguration from gpio.cfg
    PIN          = 0 # pin on RPi board GPIO connector e.g. P1-11
    DIRECTION    = 1 # IN/OUT/NONE (None is not used)
    NAME         = 2 # name for output
    RISING_NAME  = 3 # name for rising edge callback
    FALLING_NAME = 4 # name for falling edge callback
    ONE_NAME     = 5 # name for one state callback
    ZERO_NAME    = 6 # name for zero state callback
    REPEAT       = 7 # reperat interval for state callbacks (mS)
    THRESHOLD    = 8 # threshold of debounce count for state change to be considered
    PULL         = 9 # pull up or down or none
# dynamic data
    COUNT        = 10 # variable - count of the number of times the input has been 0 (limited to threshold)
    PRESSED      = 11 # variable - debounced state
    LAST         = 12 # varible - last state - used to detect edge
    REPEAT_COUNT = 13


    TEMPLATE = ['',              # pin
                '',              # direction
                '',              # name
                '','','','',     # input names
                0,               # repeat
                0,               # threshold
                '',              # pull
                0,False,False,0] # dynamics

    # index of shutdown pin
    SHUTDOWN_INDEX = 0

# constants for sequencer

    SEQUENCER_PIN      = 0 # GPIO pin number, the xx in P1-xx
    SEQUENCER_TO_STATE = 1 # False = off, True = on
    SEQUENCER_TIME     = 2 # time since the epoch in seconds
    SEQUENCER_TAG      = 3 # tag used to delete all matching event, usually a track reference.

# CLASS VARIABLES
    events         = []
    pins           = []
    last_poll_time = 0
    options        = None
    # gpio_enabled = False

    EVENT_TEMPLATE = [0, False, 0, None]

    #executed by main program and by each object using gpio
    def __init__(self):
        self.mon = Monitor()
        self.mon.on()
        self.options = command_options()

     # executed once from main program
    def init(self, pp_dir, pp_home, pp_profile, widget, button_tick, callback = None):

        # instantiate arguments
        self.widget      = widget
        self.pp_dir      = pp_dir
        self.pp_profile  = pp_profile
        self.pp_home     = pp_home
        self.button_tick = button_tick
        self.callback    = callback

        PPIO.SHUTDOWN_INDEX = 0

        # read gpio.cfg file.
        if not self.read(self.pp_dir, self.pp_home, self.pp_profile):
            return False

        # setup GPIO
        self.GPIO = PP_GPIO()

        #construct the GPIO control list from the configuration
        for index, pin_def in enumerate(self.GPIO.PINLIST):
            pin           = copy.deepcopy(PPIO.TEMPLATE)
            pin_bits      = pin_def.split('-')
            pin_num       = pin_bits[1:]
            pin[PPIO.PIN] = int(pin_num[0])

            if not self.config.has_section(pin_def):
                self.mon.log(self, "no pin definition for " + pin_def)
                pin[PPIO.DIRECTION] = 'none'
            else:
                # unused pin
                if self.config.get(pin_def, 'direction') == 'none':
                    pin[PPIO.DIRECTION] = 'none'
                else:
                    pin[PPIO.DIRECTION] = self.config.get(pin_def, 'direction')
                    if pin[PPIO.DIRECTION] == 'in':
                        # input pin
                        pin[PPIO.RISING_NAME]  = self.config.get(pin_def, 'rising-name')
                        pin[PPIO.FALLING_NAME] = self.config.get(pin_def, 'falling-name')
                        pin[PPIO.ONE_NAME]     = self.config.get(pin_def, 'one-name')
                        pin[PPIO.ZERO_NAME]    = self.config.get(pin_def, 'zero-name')

                        if pin[PPIO.FALLING_NAME] == 'pp-shutdown':
                            PPIO.SHUTDOWN_INDEX = index
                        if self.config.get(pin_def, 'repeat') != '':
                            pin[PPIO.REPEAT] = int(self.config.get(pin_def, 'repeat'))
                        else:
                            pin[PPIO.REPEAT] = -1
                        pin[PPIO.THRESHOLD] = int(self.config.get(pin_def, 'threshold'))
                        if self.config.get(pin_def, 'pull-up-down') == 'up':
                            pin[PPIO.PULL] = GPIO.PUD_UP
                        elif self.config.get(pin_def, 'pull-up-down') == 'down':
                            pin[PPIO.PULL] = GPIO.PUD_DOWN
                        else:
                            pin[PPIO.PULL] = GPIO.PUD_OFF
                    else:
                        # output pin
                        pin[PPIO.NAME] = self.config.get(pin_def, 'name')

            # print pin
            PPIO.pins.append(copy.deepcopy(pin))

        # set up the GPIO inputs and outputs
        for index, pin in enumerate(PPIO.pins):
            num = pin[PPIO.PIN]
            if pin[PPIO.DIRECTION] == 'in':
                self.GPIO.pinMode(num, self.GPIO.INPUT, pull_up_down = pin[PPIO.PULL])
            elif pin[PPIO.DIRECTION] == 'out':
                self.GPIO.pinMode(num, self.GPIO.OUTPUT)
                self.GPIO.digitalWrite(num, 0)
        self.reset_inputs()
        PPIO.gpio_enabled = True

        #init timer
        self.button_tick_timer = None
        PPIO.last_scheduler_time = long(time.time())
        return True

    # called by main program only
    def poll(self):
        # look at the buttons
        self.do_buttons()

        # kick off output pin sequencer
        poll_time = long(time.time())

        # is current time greater than last time the sceduler was run (previous second or more)
        # run in a loop to catch up because root.after can get behind when images are being rendered etc.
        while PPIO.last_scheduler_time <= poll_time:
            self.do_sequencer(PPIO.last_scheduler_time)
            PPIO.last_scheduler_time += 1

        # and loop
        self.button_tick_timer = self.widget.after(self.button_tick, self.poll)

# called by main program only
    def terminate(self):
        if self.button_tick_timer:
            self.widget.after_cancel(self.button_tick_timer)
        self.clear_events_list(None)
        self.reset_outputs()
        self.GPIO.cleanup()


# ************************************************
# gpio input functions
# called by main program only
# ************************************************

    def reset_inputs(self):
        for pin in PPIO.pins:
            pin[PPIO.COUNT]        = 0
            pin[PPIO.PRESSED]      = False
            pin[PPIO.LAST]         = False
            pin[PPIO.REPEAT_COUNT] = pin[PPIO.REPEAT]

    # index is of the pins array, provided by the callback ***** needs to be name
    def shutdown_pressed(self):
        if PPIO.SHUTDOWN_INDEX:
            return PPIO.pins[PPIO.SHUTDOWN_INDEX][PPIO.PRESSED]
        else:
            return False

    def do_buttons(self):
        for index, pin in enumerate(PPIO.pins):
            if pin[PPIO.DIRECTION] == 'in':
                # debounce
                if not self.GPIO.digitalRead(pin[PPIO.PIN]):
                    if pin[PPIO.COUNT] < pin[PPIO.THRESHOLD]:
                        pin[PPIO.COUNT] += 1
                        if pin[PPIO.COUNT] == pin[PPIO.THRESHOLD]:
                            pin[PPIO.PRESSED] = True
                else: # input us 1
                    if pin[PPIO.COUNT] > 0:
                        pin[PPIO.COUNT] -= 1
                        if pin[PPIO.COUNT] == 0:
                             pin[PPIO.PRESSED] = False

                #detect edges
                # falling edge
                if pin[PPIO.PRESSED] and not pin[PPIO.LAST]:
                    pin[PPIO.LAST] = pin[PPIO.PRESSED]
                    pin[PPIO.REPEAT_COUNT] = pin[PPIO.REPEAT]
                    if pin[PPIO.FALLING_NAME] != '' and self.callback:
                        self.callback(index, pin[PPIO.FALLING_NAME], "falling")
               #rising edge
                if not pin[PPIO.PRESSED] and pin[PPIO.LAST]:
                    pin[PPIO.LAST] = pin[PPIO.PRESSED]
                    pin[PPIO.REPEAT_COUNT] = pin[PPIO.REPEAT]
                    if pin[PPIO.RISING_NAME] != '' and self.callback:
                         self.callback(index, pin[PPIO.RISING_NAME], "rising")

                # do state callbacks
                if pin[PPIO.REPEAT_COUNT]==0:
                    if pin[PPIO.ZERO_NAME] != '' and pin[PPIO.PRESSED] and self.callback:
                        self.callback(index, pin[PPIO.ZERO_NAME], "zero")
                    if pin[PPIO.ONE_NAME] != '' and not pin[PPIO.PRESSED] and self.callback:
                        self.callback(index, pin[PPIO.ONE_NAME], "zero")
                    pin[PPIO.REPEAT_COUNT] = pin[PPIO.REPEAT]
                else:
                    if pin[PPIO.REPEAT] != -1:
                        pin[PPIO.REPEAT_COUNT] -= 1


# ************************************************
# gpio output sequencer functions
# ************************************************

    # execute events at the appropriate time and remove from list (runs from main program only)
    # runs through list a number of times because of problems with pop messing up list
    def do_sequencer(self, schedule_time):
        # print 'sequencer run for: ' + str(schedule_time) + ' at ' + str(long(time.time()))
        while True:
            event_found = False
            for index, item in enumerate(PPIO.events):
                if item[PPIO.SEQUENCER_TIME] <= schedule_time:
                    event = PPIO.events.pop(index)
                    event_found = True
                    self.do_event(event[PPIO.SEQUENCER_PIN], event[PPIO.SEQUENCER_TO_STATE], item[PPIO.SEQUENCER_TIME])
                    break
            if not event_found:
                break

    # execute an event
    def do_event(self, pin, to_state, req_time):
        self.mon.log (self, 'pin P1-' + str(pin) + ' set  ' + str(to_state) + ' required: ' + str(req_time) + ' actual: ' + str(long(time.time())))
        # print 'pin P1-' + str(pin) + ' set  ' + str(to_state) + ' required: ' + str(req_time) + ' actual: ' + str(long(time.time()))
        self.GPIO.digitalWrite(pin, to_state)

# ************************************************
# gpio output sequencer interface methods
# these can be called from many classes so need to operate on class variables
# ************************************************
    def animate(self, text, tag):
        if self.options['gpio']:
            lines = text.split("\n")
            for line in lines:
                error_text = self.parse_animate_fields(line, tag)
                if error_text != '':
                    return 'error', error_text
            return 'normal', ''
        return 'normal', ''

    # clear event list
    def clear_events_list(self, tag):
        if self.options['gpio']:
            self.mon.log(self,'clear events list ')
            # empty event list
            if not tag:
                PPIO.events = []
            else:
                self.remove_events(tag)

    def reset_outputs(self):
        if self.options['gpio']:
            self.mon.log(self, 'reset outputs')
            for index, pin in enumerate(PPIO.pins):
                num = pin[PPIO.PIN]
                if pin[PPIO.DIRECTION] == 'out':
                    self.GPIO.digitalWrite(num, 0)

# ************************************************
# internal functions
# these can be called from many classes so need to operate on class variables
# ************************************************

    def parse_animate_fields(self, line, tag):
        fields = line.split()
        if len(fields) == 0:
            return ''

        name = fields[0]
        pin = self.pin_of(name)
        if pin == -1:
            return 'Unknown gpio logical output in: ' + line

        to_state_text = fields[1]
        if not (to_state_text in ('on', 'off')):
            return 'Illegal to-state in : ' + line

        if to_state_text == 'on':
            to_state = True
        else:
            to_state = False

        if len(fields) == 2:
            delay_text = '0'
        else:
            delay_text = fields[2]

        if not delay_text.isdigit():
            return 'Delay is not an integer in : ' + line
        delay = int(delay_text)

        self.add_event(pin, to_state, delay, tag)
        # self.print_events()
        return ''

    def pin_of(self,name):
        for pin in PPIO.pins:
            # print " in list" + pin[PPIO.NAME] + str(pin[PPIO.PIN] )
            if pin[PPIO.NAME] == name and pin[PPIO.DIRECTION] == 'out':
                return pin[PPIO.PIN]
        return -1

    def print_events(self):
        print
        for i in PPIO.events:
            print i

    def add_event(self, sequencer_pin, sequencer_to_state, sequencer_time, sequencer_tag):
        poll_time = long(time.time())
        # delay is 0 so just do it, don't queue it.
        #if sequencer_time == 0:
            #print "firing now",poll_time
            #self.do_event(sequencer_pin,sequencer_to_state,poll_time)
            #return
        # prepare the event
        event = PPIO.EVENT_TEMPLATE
        event[PPIO.SEQUENCER_PIN]      = sequencer_pin
        event[PPIO.SEQUENCER_TO_STATE] = sequencer_to_state
        event[PPIO.SEQUENCER_TIME]     = sequencer_time + poll_time + 1
        event[PPIO.SEQUENCER_TAG]      = sequencer_tag
        # print event
        # find the place in the events list and insert
        # first item in the list is earliest, if two have the same time then last to be added is fired last.
        abs_time = sequencer_time + poll_time
        copy_event = copy.deepcopy(event)
        for index, item in enumerate(PPIO.events):
            if abs_time < item[PPIO.SEQUENCER_TIME]:
                PPIO.events.insert(index, copy_event)
                return copy_event
        PPIO.events.append(copy_event)
        return copy_event

    # remove an event not used and does not work
    def remove_event(self, event):
        for index, item in enumerate(PPIO.events):
            if event == item:
                del PPIO.events[index]
                return True
        return False


    # remove all the events with the same tag, usually a track reference
    def remove_events(self, tag):
        left = []
        for item in PPIO.events:
            if tag != item[PPIO.SEQUENCER_TAG]:
                left.append(item)
        PPIO.events = left
        #self.print_events()


# ***********************************
# reading gpio.cfg functions
# ************************************

    def read(self, pp_dir, pp_home, pp_profile):
            # try inside profile
            tryfile = pp_profile + os.sep + self.GPIO.CFG
            # self.mon.log(self,"Trying " + self.GPIO.CFG + " in profile at: "+ tryfile)
            if os.path.exists(tryfile):
                 filename = tryfile
            else:
                # try inside pp_home
                # self.mon.log(self, self.GPIO.CFG + " not found at "+ tryfile+ " trying pp_home")
                tryfile = pp_home + os.sep + self.GPIO.CFG
                if os.path.exists(tryfile):
                    filename = tryfile
                else:
                    # try inside pipresents
                    # self.mon.log(self, self.GPIO.CFG + " not found at "+ tryfile + " trying inside pipresents")
                    tryfile = pp_dir + os.sep + 'pp_home' + os.sep + self.GPIO.CFG
                    if os.path.exists(tryfile):
                        filename = tryfile
                    else:
                        self.mon.log(self, self.GPIO.CFG + " not found at " + tryfile)
                        self.mon.err(self, self.GPIO.CFG + " not found")
                        return False
            self.config = ConfigParser.ConfigParser()
            self.config.read(filename)
            self.mon.log(self, self.GPIO.CFG + " read from " + filename)
            return True


# ******************************
# test harness
# ******************************

if __name__ == '__main__':

    def callback(index, name, edge):
        global pevent
        if name == 'play':
            #print name,  edge
            # event with 0 delay is executed immeadiately and cannot be removed.
            # pin, state, time, tag
            ppio.add_event(0, 1, 0, 1)
            ppio.add_event(2, 1, 2, 1)
            ppio.add_event(3, 1, 3, 1)
            ppio.add_event(4, 1, 3, 2)
            ppio.add_event(1, 1, 1, 1)
            ppio.add_event(5, 1, 10, 2)
            pevent = ppio.add_event(6, 1, 11, 2)
        elif name == 'pause':
            ppio.remove_events(2)
            ppio.remove_event(pevent)

    pevent = None

    pp_dir = '/home/pi/pipresents'
    pp_profile = '/home/pi/pp_home/pp_profiles/trigger_test'
    Monitor.log_path = pp_dir
    Monitor.global_enable = True
    print "runnning"
    my_window = Tk()
    my_window.title("PPIO Test Harness")
    ppio = PPIO()
    ppio.init(pp_dir, pp_profile, my_window, 50, callback)
    ppio.read()
    ppio.poll()
    my_window.mainloop()

