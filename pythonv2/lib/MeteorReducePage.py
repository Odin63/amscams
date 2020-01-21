import cgitb
import json
import numpy
import datetime

from pathlib import Path
from shutil import copyfile

from lib.CGI_Tools import redirect_to
from lib.MeteorReduce_Tools import * 
from lib.MeteorReduce_Calib_Tools import find_matching_cal_files, find_calib_file
from lib.REDUCE_VARS import REMOTE_FILES_FOLDER, REMOVE_METEOR_FOLDER, METEOR_ARCHIVE
from lib.Make_Graphs import *
 
PAGE_TEMPLATE = "/home/ams/amscams/pythonv2/templates/reducePage.v2.html"

ERROR_FACTOR_SEG_LEN = [2,3,4,5,6]


# GENERATES THE REDUCE PAGE METEOR
# from a URL 
# cmd=reduce2
# &video_file=[PATH]/[VIDEO_FILE].mp4 or JSON File


def reduce_meteor2(json_conf,form):
  
   # Debug
   cgitb.enable()

   HD = True

   # Build the page based on template  
   with open(PAGE_TEMPLATE, 'r') as file:
      template = file.read()

   # Here we have the possibility to "empty" the cache, ie regenerate the files even if they already exists
   # we just need to add "clear_cache=1" to the URL
   if(form.getvalue("clear_cache") is not None):
      clear_cache = True
   else:
      clear_cache = False
 
   # Get Video File & Analyse the Name to get quick access to all info
   # Warning we can also pass the JSON file
   video_full_path = form.getvalue("video_file")
 
   if('.json' in video_full_path):
      json_full_path = video_full_path
      video_sd_full_path = video_full_path.replace('.json','-SD.mp4')  
      video_hd_full_path = video_full_path.replace('.json','-HD.mp4') 
      video_full_path = video_hd_full_path 

   # We get the proper json and the other video file
   if('HD' in video_full_path):
      video_hd_full_path = video_full_path
      video_sd_full_path = video_full_path.replace('-HD','-SD')
      json_full_path = video_full_path.replace('-HD.mp4','.json')
   elif('SD' in video_full_path):
      video_sd_full_path = video_full_path 
      video_hd_full_path = video_full_path.replace('-SD','-HD')
      json_full_path = video_full_path.replace('-SD.mp4','.json')  

       
   # We need at least one video file
   if(video_full_path is not None):
      analysed_name = name_analyser(video_full_path)
   else:
      print_error("<b>You need to add a video file in the URL.</b>")

   # Test if it's a detection from the current device
   # or another one 

   other_station = False

   if(analysed_name['station_id'] != get_station_id()):

      # We need to retrieve the files and copy them on the current machine
      if( not os.path.isfile(video_full_path)):

         # Can we get the real station_id?
         real_station_id = can_we_get_the_station_id(analysed_name['full_path'])
         
         # In this case, we copy the files from wasabi
         remote_video_file_path = REMOTE_FILES_FOLDER + os.sep + str(real_station_id) + REMOVE_METEOR_FOLDER + os.sep + analysed_name['year'] + os.sep + analysed_name['month']  + os.sep + analysed_name['day'] 
         remote_video_file_fullpath = remote_video_file_path +  os.sep + analysed_name['name']
         test_remoTe_video = Path(remote_video_file_fullpath)

         if test_remoTe_video.is_file():
            copy_path = METEOR_ARCHIVE  + str(real_station_id) + REMOVE_METEOR_FOLDER + os.sep + analysed_name['year'] + os.sep + analysed_name['month']  + os.sep + analysed_name['day'] +  os.sep
            
            # CREATE DIR IF Doesn't EXIST
            if not os.path.exists(copy_path):
               os.makedirs(copy_path)
   
            # COPY HD
            try:
               copyfile(remote_video_file_path+ os.sep  + os.path.basename(video_hd_full_path),copy_path + os.path.basename(video_hd_full_path))
            except:
               print_error("Remote File error: <b>IMPOSSIBLE TO COPY THE HD VIDEO</b><br><br>Are you sure the HD video <br>"+ os.path.basename(video_hd_full_path)+" <br>is on the remote folder:<br>"+ remote_video_file_path+' ?')

            # COPY SD
            try:
               copyfile(remote_video_file_path+ os.sep + os.path.basename(video_sd_full_path),copy_path + os.path.basename(video_sd_full_path))
            except:         
               print_error("Remote File error: <b>IMPOSSIBLE TO COPY THE HD VIDEO</b><br><br>Are you sure the SD video <br>"+ os.path.basename(video_sd_full_path)+" <br>is on the remote folder:<br>"+ remote_video_file_path+' ?')
            
            # COPY JSON
            try:
               copyfile(remote_video_file_path+ os.sep + os.path.basename(json_full_path),copy_path + os.path.basename(json_full_path))
            except:         
               print_error("Remote File error: <b>IMPOSSIBLE TO COPY THE JSON FILE</b><br><br>Are you sure the JSON File <br>"+ os.path.basename(json_full_path)+" <br>is on the remote folder:<br>"+ remote_video_file_path+' ?')

            # Redirect to the Reduce page
            redirect_to("/pycgi/webUI.py?cmd=reduce2&video_file=" + copy_path + os.path.basename(video_hd_full_path), "reduction")

      else:
         other_station = True
    
   
   if(cfe(video_hd_full_path)==0):
      video_hd_full_path = ''
      HD = False 
  
  
   if(cfe(json_full_path)==0):
       print_error(json_full_path + " <b>not found.</b>")

   if(cfe(video_sd_full_path)==0):
       print_error(video_sd_full_path + " <b>not found.</b><br/>At least one SD video is required.")


   # Test if the name is ok
   if(len(analysed_name)==0):
      print_error(video_full_path + " <b>is not valid video file name.</b>") 

   # Add the JSON Path to the template
   template = template.replace("{JSON_FILE}", str(json_full_path))   # Video File  

   # Parse the JSON
   meteor_json_file = load_json_file(json_full_path) 


   # Get the HD or SD stack
   tmp_analysed_name = name_analyser(json_full_path) 
   if(video_hd_full_path != ''):
      hd_stack = get_stacks(tmp_analysed_name,clear_cache,True)
   
   stack = get_stacks(tmp_analysed_name,clear_cache,False) 
   
   # Get the HD frames 
   HD_frames = get_HD_frames(tmp_analysed_name,clear_cache)
    
   # Get the thumbs (cropped HD frames) 
   try:
      HD_frames
   except NameError:
      # HD FRAMES NOT DEFINED
      thumbs = ''
      print("Error 0112.b")
   else:
      thumbs = get_thumbs(tmp_analysed_name,meteor_json_file,HD,HD_frames,clear_cache)
  
   # Is it remote?
   if(other_station==True):
      real_station_id = can_we_get_the_station_id(analysed_name['full_path'])
      template = template.replace("{WARNING_STATION}", "<div class='container-fluid mt-4'><div class='alert alert-danger'><span class='icon-notification'></span> WARNING THIS DETECTION HAS BEEN MADE FROM ANOTHER STATION -  STATION: <b>" + str(real_station_id) +"</b> - CAM: <b>"+str(analysed_name['cam_id'])+"</b></div></div>")
   else:
      template = template.replace("{WARNING_STATION}", "") 


   # Fill Template with data
   template = template.replace("{VIDEO_FILE}", str(video_full_path))   # Video File  
   template = template.replace("{SD_VIDEO}",str(video_sd_full_path))   # SD Video File
   template = template.replace("{STACK}", str(stack))                  # SD Stack File 
   if(hd_stack is not None):
      template = template.replace("{HD_STACK}", str(hd_stack))                  # HD Stack File 
   else:
      template = template.replace("{HD_STACK}", "")  

   # For the Event start time
   # either it has already been reduced and we take the time of the first frame
   start_time = 0
 
   if(meteor_json_file is False):
      print_error(" JSON NOT FOUND or CORRUPTED")
 
   if('frames' in meteor_json_file):
      if(len(meteor_json_file['frames'])>0):
         start_time = str(meteor_json_file['frames'][0]['dt'])
        
   # either we take the time of the file name
   if(start_time==0):
      start_time = analysed_name['year']+'-'+analysed_name['month']+'-'+analysed_name['day']+ ' '+ analysed_name['hour']+':'+analysed_name['min']+':'+analysed_name['sec']+'.'+analysed_name['ms']
   

   # We compute the MED_DIST (medium value of frame['dist_from_last'])
   med_dist = 0
   if('frames' in meteor_json_file):  
      if(meteor_json_file['frames'] != {}):
         if('dist_from_last' in meteor_json_file['frames'][0]):

            # We add all the dist_from_last to compute the median value
            tmp_list = []
            for frame in meteor_json_file['frames']:
               tmp_list.append(frame['dist_from_last'])

            med_dist=numpy.median(tmp_list)

   # We add the med dist to the template
   template = template.replace("{MED_DIST}", str(med_dist))
 
   # Build the report details
   report_details = ''

   if('report' in meteor_json_file):
      report_details += '<dt class="col-4">Date &amp; Time</dt><dd class="col-8">'+start_time+'s</dd>'
      if('dur' in meteor_json_file['report']):
         report_details += '<dt class="col-4">Duration</dt><dd class="col-8"><span id="dur">'+str(meteor_json_file['report']['dur'])+'</span>s</dd>'
      if('max_peak' in meteor_json_file['report']):
         report_details += '<dt class="col-4">Max Intensity</dt><dd class="col-8">'+str(meteor_json_file['report']['max_peak'])+'</dd>'
      if('angular_vel' in meteor_json_file['report']):
         report_details += '<dt class="col-4">Ang. Velocity</dt><dd class="col-8">'+str(meteor_json_file['report']['angular_vel'])+'&deg;/sec</dd>'
      if('point_score' in meteor_json_file['report']):
            pts = str(meteor_json_file['report']['point_score'])
            if(meteor_json_file['report']['point_score']>3):
               pts = "<b style='color:#f00'>"+ pts +  "</b>"
            report_details += '<br/><dt class="col-4">Point Score</dt><dd class="col-8" id="point_score_val">'+pts+'</dd>'

   if('calib' in meteor_json_file):
      if('device' in meteor_json_file['calib']):
         if('total_res_px' in meteor_json_file['calib']['device']):
            pts = str(meteor_json_file['calib']['device']['total_res_px'])
            if(meteor_json_file['calib']['device']['total_res_px']>3):
               pts = "<b style='color:#f00'>"+ pts +  "</b>"
            report_details += '<dt class="col-4">Res. Error</dt><dd class="col-8">'+pts+'</dd>'


   # Select to determine the factor of error for seg len  (Med dIST)
   med_dist_select = '<select title="Seg. Len. error factor"  id="error_factor_dist_len" class="custom-select ml-4" style="width: auto;padding-top: 0;padding-bottom: 0;line-height: 1;height: 1.5em;">'
   for err in ERROR_FACTOR_SEG_LEN:
      med_dist_select += "<option value='"+str(err)+"'>x"+str(err)+"</option>"
   med_dist_select +="</select>"
 
   report_details += '<dt class="col-4">Med. dist</dt><dd class="col-8">'+str("{0:.4f}".format(float(med_dist)))+' ' + med_dist_select +'</dd>'
 
    
   # IS IT A MULTI DETECTION?
   if('info' in meteor_json_file):
      if('multi_station' in meteor_json_file['info']):
         # We build {MULTI_DETAILS}
         multi_box = '<div class="box"><h2>Multi-detection</h2><div class="alert alert-danger">NO INFO IN THE JSON FOR THE MOMENT</div></div>'
         template = template.replace("{MULTI_DETAILS}",multi_box)
      else:
         template = template.replace("{MULTI_DETAILS}",'')

   # Basic X,Y of points
   plots = make_basic_plot(meteor_json_file) 
   print("PLOTS")
   print(plots)
   template = template.replace("{%PLOTS_TABLE%}", plots)

   # Link to old version
   if('info' in meteor_json_file):
      if('org_sd_vid' in meteor_json_file['info']):
         to = meteor_json_file['info']['org_sd_vid'].replace('.mp4','.json')
         template = template.replace("{GO_TO_OLD_VERSION}","<a class='btn btn-primary d-block mt-4' href='/pycgi/webUI.py?cmd=reduce&video_file="+to +"'>Go to Old Version</a>")


   # We complete the template
   if(report_details!=''):
      template = template.replace("{REPORT_DETAILS}", report_details)
   else:
      template = template.replace("{REPORT_DETAILS}", "<dt class='d-block mx-auto'><div class='alert alert-danger'>Reduction info are missing</div></dt>")
 
   # Does this detection relies only on SD data? (ie the HD video is in fact the resized SD video)
   if('info' in meteor_json_file):
      if('HD_fix' in meteor_json_file['info']):
         template = template.replace("{HD_fix}", '<div class="box"><dl class="row mb-0 mt-2"><dt class="col-12"><span class="icon-notification"></span> This detection only relies on SD video data.</dt></dl></div>')
         template = template.replace("{HD_fix_button}",'')
      elif('SD_fix' in  meteor_json_file['info']):
         template = template.replace("{HD_fix}", '<div class="box"><dl class="row mb-0 mt-2"><dt class="col-12"><span class="icon-notification"></span> This detection only relies on HD video data.</dt></dl></div>')
         template = template.replace("{HD_fix_button}",'')
      else:
         template = template.replace("{HD_fix}", "")
         template = template.replace("{HD_fix_button}",'<a class="btn btn-primary d-block mt-2" id="hd_fix">Fix Video</a>')
         
   else:
      template = template.replace("{HD_fix}", "")
      template = template.replace("{HD_fix_button}",'<a class="btn btn-primary d-block mt-2" id="hd_fix">Fix Video</a>')
 
   # Are HD & SD sync?
   if('sync' not in meteor_json_file):
      template = template.replace("{NO_SYNC}", "<div class='container-fluid mt-4'><div class='alert alert-danger'><span class='icon-notification'></span> <b>Both HD and SD videos aren't synchronized.</b> <a id='manual_synchronization' class='btn btn-danger ml-3'><b>Manually synchronize both videos now</b></a></div></div>")
   else:
      template = template.replace("{NO_SYNC}", "")
 
 
 
         

   # Display Template
   print(template)
