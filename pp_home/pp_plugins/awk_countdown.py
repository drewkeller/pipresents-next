"""
This example just writes to the screen directly.
The track file is just pased through unaltered

The local time is read and is written direct to the Tkinter canvas 
that is used by Pi Presents to display its output.

Writing to the screen is done in a function which is triggered by Tkinter canvas.after()
which is a non-blocking equivalent of sleep()


"""

import os
import time
from datetime import *
from Tkinter import *
import Tkinter
import Image, ImageChops, ImageDraw, ImageFont, ImageFilter


class Plugin:

    def __init__(self,root,canvas,plugin_params,track_params,show_params,pp_dir,pp_home,pp_profile):
        self.root          = root
        self.canvas        = canvas
        self.plugin_params = plugin_params
        self.track_params  = track_params
        self.show_params   = show_params
        self.pp_dir        = pp_dir
        self.pp_home       = pp_home
        self.pp_profile    = pp_profile

        self.timer=None
        self.flashed = False

 
    def do_plugin(self,track_file):

        # was the player called from a liveshow?
        self.liveshow = self.show_params['type'] == 'liveshow'

        # if plugin is called in a liveshow then  a track file will not be provided so maybe get one from the plugin cfg file
        if self.liveshow:
            self.track_file = self.plugin_params['track-file']
        else:
            # just pass the track file though unmodified
            self.track_file = track_file

        
        # just return the track file
        self.used_file = self.track_file


        #kick off the function to draw the time to the screen
        self.timer = self.canvas.after(10, self.draw_time)
        
        #and return the track to play.
        return 'normal', '', self.used_file


    def draw_time(self):
        
        # parse date/time info
        now = datetime.now()
        target_date = self.plugin_params['countdown_to_date']
        target_time = self.plugin_params['countdown_to_time']
        if (target_date):
          target = datetime.strptime(target_date + ' ' + target_time, '%Y-%m-%d %H:%M:%S')
        else:
          target = datetime.strptime(target_time, '%H:%M:%S')
          target = now.replace(hour=target.hour, minute=target.minute, second=target.second)
        
        # calculate date/time difference and build text string
        diff = target - now
        seconds = diff.total_seconds()
        prepost = '_pre' if (now < target) else '_post'
        show_for_pre  = int(self.plugin_params['show_for_pre'])
        show_for_post = int(self.plugin_params['show_for_post'])
        if (seconds > 0 and seconds > show_for_pre)   or \
           (seconds < 0 and abs(seconds) > show_for_post):
          return
        text_format = self.plugin_params['text_format'+prepost]
        if text_format is None or text_format == "":
          print 'Nothing to output'
          return
        text = text_format.format(diff=abs(diff), date=target_date, time=target_time)
        text = text.replace('\\n', '\n')

        # This tag is an identifier for the text that we write
        # So this operation deletes (clears) the text we wrote previously
        self.canvas.delete('awk-countdown')
        
        #krt-time tag allows deletion before update
        # pp-content tag ensures that Pi Presents deletes the text at the end of the track
        # it must be inclued
        x         = int(self.plugin_params['x'+prepost])
        y         = int(self.plugin_params['y'+prepost])
        delta     = int(self.plugin_params['delta'+prepost])
        anchor    = self.plugin_params['anchor'+prepost]
        forecolor = self.plugin_params['font_forecolor'+prepost]
        backcolor = self.plugin_params['font_backcolor'+prepost]
        font      = self.plugin_params['font'+prepost]
        justify   = self.plugin_params['justify'+prepost]
        flash     = self.plugin_params['flash'+prepost]
        if flash == "" or flash == "0":
          flash = False
        elif flash == "1":
          flash = True
        else:
          flash = bool(flash)
        flash_rate = self.plugin_params['flash_rate'+prepost]
        flash_rate = 1000 if flash_rate is None or flash_rate == "" else int(flash_rate)
        self.flashed = not self.flashed
        if flash and self.flashed and flash_rate > 0:
          temp = backcolor
          backcolor = forecolor
          forecolor = temp
        self.draw_shadow(x, y, delta, text, backcolor, font, anchor=anchor, justify=justify, 
                         tag=('awk-countdown','pp-content'))
        #self.draw_blur(x,y,text,forecolor,backcolor, font, anchor=NW, tag=('awk-countdown','pp-content'))
        self.canvas.create_text(x,y, text=text, anchor=anchor, justify=justify,
                                fill=forecolor, font=font, tag=('awk-countdown','pp-content'))
        
        # and kick off draw_time() again in one second
        self.timer=self.canvas.after(flash_rate,self.draw_time)

    def draw_shadow(self, x,y,delta,text,color,font,*args,**kwargs):
        self.canvas.create_text(x-delta, y,       text=text, fill=color, font=font, **kwargs)
        self.canvas.create_text(x+delta, y,       text=text, fill=color, font=font, **kwargs)
        self.canvas.create_text(x,       y-delta, text=text, fill=color, font=font, **kwargs)
        self.canvas.create_text(x,       y-delta, text=text, fill=color, font=font, **kwargs)
        
        self.canvas.create_text(x-delta, y-delta, text=text, fill=color, font=font, **kwargs)
        self.canvas.create_text(x-delta, y+delta, text=text, fill=color, font=font, **kwargs)
        self.canvas.create_text(x+delta, y-delta, text=text, fill=color, font=font, **kwargs)
        self.canvas.create_text(x+delta, y+delta, text=text, fill=color, font=font, **kwargs)
        
    def draw_blur(self, x,y, text, forecolor, backcolor, font, *args, **kwargs):
        width = self.canvas.cget('width')
        height = self.canvas.cget('height')
        img = Image.open(self.track_file)
        blur = Image.new('RGBA', img.size, (0,0,0,0))
        ImageDraw.Draw(blur).text((x,y), text, fill=backcolor)
        blurred = blur.filter(ImageFilter.BLUR)
        ImageDraw.Draw(blurred).text((x,y), text, fill=forecolor)
        img = Image.composite(img, blurred, ImageChops.invert(blurred))
        # always get an error from this line
        self.canvas.create_image((x,y), image=img)


    def stop_plugin(self):
        # gets called by Pi Presents at the end of the track
        #stop the timer as the stop_plugin may have been called while it is running
        if self.timer<>None:
            self.canvas.after_cancel(self.timer)

        
