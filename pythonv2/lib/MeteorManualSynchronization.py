import cgitb
import os
import sys
import json

from lib.FileIO import load_json_file
from lib.MeteorReducePage import print_error
from lib.Old_JSON_converter import get_analysed_name
from lib.MeteorReduce_Tools import get_stacks, get_cache_path, does_cache_exist


MANUAL_SYNC_TEMPLATE_STEP1 = "/home/ams/amscams/pythonv2/templates/manual_sync_template_step0.html"
MANUAL_SYNC_TEMPLATE_STEP2 = "/home/ams/amscams/pythonv2/templates/manual_sync_template_step1.html"

# Second (and last step) of the manual sync
def manual_synchronization_chooser(form):

   # Debug
   cgitb.enable()

   video_file  = form.getvalue('video_file')  
   stack_file  = form.getvalue('stack_file')  
   type_file   = form.getvalue('type')  
   x_start     = float(form.getvalue('x_start'))
   y_start     = float(form.getvalue('y_start'))
   w           = float(form.getvalue('w'))
   h           = float(form.getvalue('h'))
   json_file   = form.getvalue('json')

   # Get Analysed name (old or new)
   analysed_name = get_analysed_name(video_file)

   # Create destination folder for the HD if necessary
   dest_folder = get_cache_path(analysed_name,'tmp_cropped_sync')
   cache_path  = does_cache_exist(analysed_name,'tmp_cropped_sync')

   # Create destination folder for the HD if necessary
   dest_hd_folder = get_cache_path(analysed_name,'tmp_hd_cropped_sync')
   cache_hd_path  = does_cache_exist(analysed_name,'tmp_hd_cropped_sync')
   dest_sd_folder = get_cache_path(analysed_name,'tmp_sd_cropped_sync')
   cache_sd_path  = does_cache_exist(analysed_name,'tmp_sd_cropped_sync')

   # Parse the JSON file
   mr = load_json_file(json_file)

   if "frames" in mr:
      for ind, frame in enumerate(mr['frames']):   
         print(ind + " > ")
         print(frame)
         print("<br/>")

         # Recreate the corresponding thumb
         #original_HD_frame = get_HD_frame(analysed_name,val['fn'])   
         #destination_cropped_frame = get_thumb(analysed_name,val['fn'])    

         #if(len(original_HD_frame)!=0 and len(destination_cropped_frame)!=0): 
            #   new_crop_thumb(original_HD_frame[0],int(val['x']),int(val['y']),destination_cropped_frame[0])
         #else:
         #   resp['error'].append("Impossible to update the frame " + str(int(val['fn'])))
  


# First step of the manual synchronization
def manual_synchronization(form):

   # Debug
   cgitb.enable()

   stack_file = form.getvalue('stack')
   video_file = form.getvalue('video')
   type_file  = form.getvalue('type')    # HD or SD
   json_file  = form.getvalue('json') 

   # Build the page based on template  
   with open(MANUAL_SYNC_TEMPLATE_STEP1, 'r') as file:
      template = file.read()
 
    # Video File
   if(video_file is None):
      print_error("<b>You need to add a video file in the URL.</b>")
       
   analysed_name = get_analysed_name(json_file)
   
   # No matter if the stack is SD or not
   # we resize it to HD
   stack = get_stacks(analysed_name,True, True)

   # We add it to the template
   template = template.replace("{STACK}", str(stack))  
  
   # Add Video to template
   template = template.replace("{VIDEO}", str(video_file))

   # Add Initial type to template
   template = template.replace("{TYPE}", str(type_file))

   # Add json
   template = template.replace("{JSON}",str(json_file))

   print(template)  