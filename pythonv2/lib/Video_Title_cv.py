import cv2 
import numpy as np
from PIL import ImageFont, ImageDraw, Image
from lib.VIDEO_VARS import * 
from lib.Video_Tools_cv import add_text

# From Mike
from lib.VideoLib import load_video_frames, make_movie_from_frames

TITLE_1280x720 = "/home/ams/amscams/dist/vids/ams_intro/1280x720.mp4"
DEFAULT_TITLE = TITLE_1280x720
 

# Add big text centered 
def add_big_text(background,text,y,color,size, the_font=VIDEO_FONT_BOLD):

    # Convert background to RGB (OpenCV uses BGR)  
    cv2_background_rgb = cv2.cvtColor(background,cv2.COLOR_BGR2RGB)  
    
    # Pass the image to PIL to use ttf fonts
    pil_im  = Image.fromarray(cv2_background_rgb)  
    draw    = ImageDraw.Draw(pil_im)  
    font    = ImageFont.truetype(the_font, size)  

    x = cv2_background_rgb.shape[1]/2 - font.getsize(text)[0]/2
     
    draw.text((x, y), text, font=font, fill=color)  
    return  cv2.cvtColor(np.array(pil_im), cv2.COLOR_RGB2BGR)  


# This function create a quick video (lenght of DEFAULT_TITLE ~ 3sec )
# with the animated AMS logo and a custom text (ONE LINE TEXT ONLY)
def create_title_video(text,text2,output):

    # Get the original frames 
    cap = cv2.VideoCapture(DEFAULT_TITLE)

    frames = []
    frame_count = 0
    go = 1
    while go == 1:
        _ , frame = cap.read()
      
        if frame is not None: 
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) 
            frames.append(frame) 
        else:
            go = 0 
    
    cap.release()
   
    new_frames = []

    for frame in frames:
 
        #Convert to proper colors
        n_frame = frame

        #Add Text 
        n_frame = add_big_text(n_frame,"AMERICAN METEOR SOCIETY", 290, (255,255,255,255), 35)
        n_frame = add_big_text(n_frame,text,370, (250,250,209,255), 60)
        #2nd ligne smaller
        n_frame = add_big_text(n_frame,text2,460, (250,250,209,255), 20,VIDEO_FONT)

        new_frames.append(n_frame)

    make_movie_from_frames(new_frames, [0,len(new_frames) - 1], output, 1)
    print('OUTPUT ' + output)