import cv2 
import numpy as numpy
from lib.VIDEO_VARS import * 
from lib.Video_Tools_cv import add_text

# From Mike
from lib.VideoLib import load_video_frames, make_movie_from_frames

TITLE_1280x720 = "/home/ams/amscams/dist/vids/ams_intro/1280x720.mp4"
DEFAULT_TITLE = TITLE_1280x720


# This function create a quick video (lenght of DEFAULT_TITLE ~ 3sec )
# with the animated AMS logo and a custom text (ONE LINE TEXT ONLY)
def create_title_video(text,output):

    # Get the original frames 
    frames = load_video_frames(DEFAULT_TITLE,"")
    new_frames = []

    for frame in frames:
 
        #Add Text
        n_frame = add_text(frame,text,0,0,True)
        new_frames.append(n_frame)

    make_movie_from_frames(new_frames, [0,len(new_frames) - 1], output, 1)
    print('OUTPUT ' + output)