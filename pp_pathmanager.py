import os
import copy
from pp_utils import Monitor


class PathManager:

    def __init__(self):
        self.debug=False
        
        self.path_stack=[]

        
    # pops back to 'stop_at' 
    # then pops back one further and returns the track-ref of this track for replaying
    # if stop-at is not found returns ''

    def back_to(self,stop_at,):
        if self.debug: print 'pathmanager command   -    back_to: ',stop_at
        for page in self.path_stack:
            if page[0]==stop_at:
                break
        else:
            return ''
        
        # found, so pop until we reach it
        while self.path_stack[len(self.path_stack)-1][0]<>stop_at:
            self.path_stack.pop()
        track_to_play = self.path_stack[len(self.path_stack)-1][0]
        self.path_stack.pop()
        if self.debug:  self.print_path()
        return track_to_play


    # pops back 'number' tracks or to 'stop_at' whichever is first
    # then pops back one further and returns the track-ref of this track for replaying
    # if stop-at is not found and everything is popped the stack is left empty and the first track is returned


    def back_by(self,stop_at,back_by_text='1000'):
        if self.debug:  print 'pathmanager command    -    back by: ',back_by_text,' or stop at: ',stop_at
        back_by=int(back_by_text)
        count=0
        while self.path_stack<>[]:
            top = self.path_stack.pop()
            if top[0]==stop_at or count==back_by-1:
                break
            count=count+1
        # go back 1 if not empty
        if self.path_stack<>[]:
            top=self.path_stack.pop()
        track_to_play = top[0]
        if self.debug: 
            print '   removed for playing: ',track_to_play
            self.print_path()
        return track_to_play
    
    def append(self,page):
        if self.debug:  print 'pathmanager command   -   append: ',page
        self.path_stack.append([page])
        if self.debug: self.print_path()

    def empty(self):
        self.path_stack=[]

    # sibling - just pop the media track so sibling is appended and can go back to page track
    def pop_for_sibling(self):
        if self.debug: print 'pathmanger: pop for sibling'
        self.path_stack.pop()
        if self.debug: self.print_path()

        
    def print_path(self):
        print 'Path now is:'
        for page in self.path_stack:
            print "      ",page[0]

# *******************   
# Extract links
# ***********************

    def parse_links(self,links_text):
        links=[]
        lines = links_text.split('\n')
        num_lines=0
        for line in lines:
            if line.strip()=="":
                continue
            num_lines+=1
            error_text,link=self.parse_link(line)
            if error_text<>"":
                return 'error',error_text,links
            links.append(copy.deepcopy(link))
        #print "\nreading"
        #print links
        return 'normal','',links

    def parse_link(self,line):
            fields = line.split()
            if len(fields)<2 or len(fields)>3:
                return "incorrect number of fields in link",['','','']
            symbol=fields[0]
            operation=fields[1]
            if operation not in ('return','home','call','null','exit','goto','play','jump','repeat'):
                return "unknown operation",['','','']
            if len(fields)==3:
                arg=fields[2]
            else:
                arg=''
            return '',[symbol,operation,arg]

    def merge_links(self,current_links,track_links):
        for track_link in track_links:
            for link in current_links:
                if track_link[0]==link[0]:
                        # link exists so overwrite
                        link[1]=track_link[1]
                        link[2]=track_link[2]
                        break
            else:
            # new link so append it
                current_links.append(track_link)
        #print "\n merging"
        #print current_links
                        
    

# **************
# Test Harness
# *************

if __name__ == '__main__':
    path=PathManager()     
    path.append('one')
    path.append('two')
    at=path.back('two','3')

