import datetime
import os
import subprocess
import numpy as np
import cv2
import glob
import urllib.request
import json
from lib.FileIO import get_day_stats, load_json_file, cfe, get_days, save_json_file,load_json_file, purge_hd_files, purge_sd_daytime_files, purge_sd_nighttime_files
from lib.ImageLib import draw_stack, thumb, stack_glob, stack_stack, stack_frames
from PIL import Image
from lib.VideoLib import load_video_frames
from lib.UtilLib import convert_filename_to_date_cam

def get_kml(kml_file):
   fp = open(kml_file, "r")
   lc = 0
   kml_txt = ""
   lines = fp.readlines()
   for line in lines: 
      if lc >= 3 and lc < len(lines)-2:
         kml_txt = kml_txt + line
      lc = lc + 1 
   fp.close()
   return(kml_txt)
      

def get_kmls(ms_dir):
   kmls = sorted(glob.glob(ms_dir + "/*.kml"))
   return(kmls)
   

def merge_kml_files(json_conf):
   kml_header = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
    <Document id="1">

   """
   kml_footer = """
    </Document>
</kml>
   """
   solutions = {}
   ms_dirs = sorted(glob.glob("/mnt/ams2/multi_station/*"))
   for ms_dir in ms_dirs:
      if cfe(ms_dir, 1) == 1:
         solutions[ms_dir] = get_kmls(ms_dir)
   master_kml = kml_header
   for ms_dir in solutions:
      el = ms_dir.split("/")
      day_folder_name = el[-1]
      master_kml = master_kml + "\n<Folder>\n\t<name>" + day_folder_name + "</name>"
      print(ms_dir, len(solutions[ms_dir]))
      for kml_file in solutions[ms_dir]:
         el = kml_file.split("/")
         ef = el[-1]
         event_folder_name = ef[0:20] 
         master_kml = master_kml + "\n<Folder>\n\t<name>" + event_folder_name + "</name>"
         kml_text = get_kml(kml_file) 
         master_kml = master_kml + kml_text + "\n</Folder>\n"
      master_kml = master_kml + "</Folder>\n"
   master_kml = master_kml + kml_footer
   out = open("/mnt/ams2/master_meteor_kml.kml", "w")
   out.write(master_kml)
   out.close()

def solve_event(event_id, meteor_events):
   meteor = meteor_events[event_id]
   obs = []
   for station_name in meteor['observations']:
      if len(meteor['observations'][station_name]) > 1:
         # pick the best video from this station since there is more than one
         for device_name in meteor['observations'][station_name]:
            video_file = meteor['observations'][station_name][device_name]
      else:
         for device_name in meteor['observations'][station_name]:
            video_file = meteor['observations'][station_name][device_name]
      reduced_file = video_file.replace(".mp4", "-reduced.json")
      if cfe(reduced_file) == 0:
         reduced_file = reduced_file.replace("/meteors/", "/multi_station/")
      obs.append(reduced_file)

   print("OBS:", obs)
   arglist = ""
   for ob in obs:
      arglist = arglist + ob + " " 

   cmd = "./mikeSolve.py " + arglist
   os.system(cmd)
   print(cmd)
         

def get_meteor_files(mdir):
   files = glob.glob(mdir + "/*-reduced.json")
   return(files)

def id_event(meteor_events, meteor_file, meteor_json, event_start_time) :
   
   total_events = len(meteor_events)
   station_name = meteor_json['station_name']
   device_name = meteor_json['device_name']
   sd_video_file = meteor_json['sd_video_file']
   if total_events == 0:
      event_id = 1
      meteor_events[event_id] = {}
      meteor_events[event_id]['start_time'] = event_start_time
      meteor_events[event_id]['observations'] = {}
      meteor_events[event_id]['observations'][station_name]  = {}
      meteor_events[event_id]['observations'][station_name][device_name] = sd_video_file
      return(meteor_events) 

   for ekey in meteor_events:
      this_start_time = meteor_events[ekey]['start_time']
      evst_datetime = datetime.datetime.strptime(event_start_time, "%Y-%m-%d %H:%M:%S.%f")
      this_datetime = datetime.datetime.strptime(this_start_time, "%Y-%m-%d %H:%M:%S.%f")
      tdiff = (evst_datetime-this_datetime).total_seconds() 
      print(ekey, this_start_time, tdiff)
      if abs(tdiff) < 5:
         print("second capture of same event")
         meteor_events[ekey]['observations'][station_name][device_name] = sd_video_file
         return(meteor_events)

   # no matches found so make new event
   event_id = total_events + 1
   print("new event:", event_id)
   meteor_events[event_id] = {}
   meteor_events[event_id]['start_time'] = event_start_time
   meteor_events[event_id]['observations'] = {}
   meteor_events[event_id]['observations'][station_name]  = {}
   meteor_events[event_id]['observations'][station_name][device_name] = sd_video_file

   return(meteor_events)

def find_multi_station_meteors(json_conf, meteor_date="2019_03_20"):
   meteor_events = {}
   meteor_dir = "/mnt/ams2/meteors/" + meteor_date
   multi_station_dir = "/mnt/ams2/multi_station/" + meteor_date
   meteor_files = get_meteor_files(meteor_dir)
   ms_files = get_meteor_files(multi_station_dir)
   multi_station_meteors = {}
   for meteor_file in meteor_files:
      meteor_json = load_json_file(meteor_file)
      event_start_time = meteor_json['event_start_time']
      print(meteor_file) 
      meteor_events = id_event(meteor_events, meteor_file, meteor_json, event_start_time)

   event_file = "/mnt/ams2/multi_station/" + meteor_date + "/" + "events_" + meteor_date + ".json"

   for event_id in meteor_events:
      event_start_time = meteor_events[event_id]['start_time']
      evst_datetime = datetime.datetime.strptime(event_start_time, "%Y-%m-%d %H:%M:%S.%f")
      for ms_file in ms_files:
         ms_json = load_json_file(ms_file)
         ms_start_time = ms_json['event_start_time'] 
         ms_datetime = datetime.datetime.strptime(ms_start_time, "%Y-%m-%d %H:%M:%S.%f")
         ms_station_name = ms_json['station_name']
         ms_device_name = ms_json['device_name']
         ms_sd_video_file = ms_json['sd_video_file']
         time_diff = abs((evst_datetime-ms_datetime).total_seconds())
          
         if time_diff < 5:
            print("MULTI-STATION DETECTION:", event_id, ms_file)
            if ms_device_name in meteor_events:
               meteor_events[event_id]['observations'][ms_station_name][ms_device_name] = ms_sd_video_file
            else:
               meteor_events[event_id]['observations'][ms_station_name]  = {}
               meteor_events[event_id]['observations'][ms_station_name][ms_device_name] = ms_sd_video_file

   save_json_file(event_file, meteor_events)
   for event_id in meteor_events:
      total_obs = len(meteor_events[event_id]['observations'])
      if total_obs > 1:
         print(event_id, " TOTAL OBS " , total_obs)
         solve_event(event_id, meteor_events)
   
   exit()
   for meteor_file in meteor_files:
      multi_station_matches = []
      meteor_datetime, cam_id, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(meteor_file)
      print(meteor_datetime)
      for ms_file in ms_files:
         ms_datetime, ms_cam_id, ms_date, ms_y, ms_m, ms_d, ms_h, ms_M, ms_s = convert_filename_to_date_cam(ms_file)
         time_diff = abs((meteor_datetime-ms_datetime).total_seconds())
         if time_diff < 120:
            print("\t", ms_datetime, time_diff)
            #multi_station_matches
            cmd = "./mikeSolve.py " + meteor_file  + " " + ms_file
            os.system(cmd)
            print(cmd)


def sync_event(meteor_json_url, meteor_date):
   meteor_data = urllib.request.urlopen(meteor_json_url).read()
   meteor_data_json = json.loads(meteor_data.decode("utf-8"))
   el = meteor_json_url.split("/")
   event_file = el[-1]
   data_file = "/mnt/ams2/multi_station/" + meteor_date + "/" + event_file
   print("Syncing...", data_file)
   save_json_file(data_file, meteor_data_json)


def sync_multi_station(json_conf, meteor_date='2019_03_20'):
   sync_urls = load_json_file("/home/ams/amscams/conf/sync_urls.json")
   stations = json_conf['site']['multi_station_sync']
   for station in stations:
      url = sync_urls['sync_urls'][station]
      url = url + "pycgi/webUI.py?cmd=list_meteors&meteor_date=" + meteor_date 
      multi_dir = "/mnt/ams2/multi_station/" + meteor_date
      if cfe(multi_dir, 1) == 0:
         os.system("mkdir " + multi_dir)
      station_data = urllib.request.urlopen(url).read()
      dc_station_data = json.loads(station_data.decode("utf-8"))
      print(dc_station_data)
      multi_file = multi_dir + "/" + station + "_" + meteor_date + ".txt"
      save_json_file(multi_file, dc_station_data)
      data = load_json_file(multi_file)
      for file in data:
         print(station, file)
         file_url = sync_urls['sync_urls'][station] + file
         sync_event(file_url, meteor_date)
      

def batch_doHD(json_conf):
   proc_dir = json_conf['site']['proc_dir']
   all_days = get_days(json_conf)
   meteors = []
   for day_dir in all_days:
      meteor_glob = proc_dir + day_dir + "/passed/*.mp4"
      print(meteor_glob)
      meteor_files = glob.glob(meteor_glob)
      for mf in meteor_files:
         if "meteor" not in mf:
            meteors.append(mf) 

   for meteor in meteors:
      base_meteor = meteor.replace(proc_dir, "")
      base_meteor = base_meteor.replace("/passed", "")
      arc_meteor = "/mnt/ams2/meteors/" + base_meteor
      if cfe(arc_meteor) == 1:
         done = 1
      else:
         cmd = "./detectMeteors.py doHD " + meteor
         print(cmd)
         os.system(cmd)

def purge_data(json_conf):
   proc_dir = json_conf['site']['proc_dir']
   hd_video_dir = json_conf['site']['hd_video_dir']
   disk_thresh = 80   

   try:
      cmd = "df -h | grep ams2"
      output = subprocess.check_output(cmd, shell=True).decode("utf-8")
      stuff = output.split(" ")
      print(stuff)
      for st in stuff:
         if "%" in st:
            disk_perc = int(st.replace("%", ""))
   except:
      disk_perc = 81
   if disk_perc > disk_thresh:
      print("DELETE some stuff...")
      # delete HD Daytime Files older than 1 day
      # delete HD Nighttime Files older than 3 days
      # delete SD Daytime Files older than 3 days
      # delete NON Trim SD Nighttime Files (and stacks) older than 15 days
      # delete NON Meteor SD Nighttime Files older than 30 days
      # Keep all dirs in the proc2 dir (for archive browsing), but after time delete everything
      # except the passed dir and its contents. *?refine maybe?*
   print(disk_perc)
   purge_hd_files(hd_video_dir,json_conf)
   purge_sd_daytime_files(proc_dir,json_conf)
   purge_sd_nighttime_files(proc_dir,json_conf)


def stack_night_all(json_conf, limit=0, tday = None):
   proc_dir = json_conf['site']['proc_dir']
   all_days = get_days(json_conf)
   if limit > 0:
      days = all_days[0:limit]
   else:
      days = all_days
   if tday is not None:
      for cam in json_conf['cameras']:
         cams_id = json_conf['cameras'][cam]['cams_id']
         glob_dir = proc_dir + tday + "/" 
         print(glob_dir,cams_id)
         stack_day_cam_all(json_conf, glob_dir, cams_id)
   else:
      for day in sorted(days,reverse=True):
         for cam in json_conf['cameras']:
            cams_id = json_conf['cameras'][cam]['cams_id']
            glob_dir = proc_dir + day + "/" 
            print(glob_dir,cams_id)
            stack_day_cam_all(json_conf, glob_dir, cams_id)

def stack_night(json_conf, limit=0, tday = None):
   proc_dir = json_conf['site']['proc_dir']
   all_days = get_days(json_conf)
   if limit > 0:
      days = all_days[0:limit]
   else:
      days = all_days

   if tday is not None:
      for cam in json_conf['cameras']:
         cams_id = json_conf['cameras'][cam]['cams_id']
         glob_dir = proc_dir + tday + "/" 
         print(glob_dir,cams_id)
         stack_day_cam(json_conf, glob_dir, cams_id)
   else:
      for day in sorted(days,reverse=True):
         for cam in json_conf['cameras']:
            cams_id = json_conf['cameras'][cam]['cams_id']
            glob_dir = proc_dir + day + "/" 
            print(glob_dir,cams_id)
            stack_day_cam(json_conf, glob_dir, cams_id)

   
def stack_day_cam_all(json_conf, glob_dir, cams_id ):
   print ("stacking failures")
   # stack failed captures
   img_dir = glob_dir + "/images/"
   f_glob_dir = glob_dir + "/images/*" + cams_id + "*-stacked.png"
   out_file = img_dir + cams_id + "-night-stack.png"
   stack_glob(f_glob_dir, out_file)


def stack_day_cam(json_conf, glob_dir, cams_id ):
   print ("stacking failures")
   # stack failed captures
   img_dir = glob_dir + "/images/"
   f_glob_dir = glob_dir + "/failed/*" + cams_id + "*-stacked.png"
   out_file = img_dir + cams_id + "-failed-stack.png"
   stack_glob(f_glob_dir, out_file)

   print ("stacking meteors")
   # then stack meteors, then join together
   glob_dir = f_glob_dir.replace("failed", "passed")
   print("GLOB:", glob_dir)
   meteor_out_file = img_dir + cams_id + "-meteors-stack.png"
   stack_glob(glob_dir, meteor_out_file)

   # now join the two together (if both exist)
   if cfe(out_file) == 1 and cfe(meteor_out_file) == 1:
      print ("Both files exist")
      im1 = cv2.imread(out_file, 0)
      im2 = cv2.imread(meteor_out_file, 0)
      im1p = Image.fromarray(im1)
      im2p = Image.fromarray(im2)

      print(out_file, meteor_out_file)
      final_stack = stack_stack(im1p,im2p)
      night_out_file = img_dir + cams_id + "-night-stack.png"
      final_stack_np = np.asarray(final_stack)
      cv2.imwrite(night_out_file, final_stack_np)
      print(night_out_file)
   elif cfe(out_file) == 1 and cfe(meteor_out_file) == 0:
      im1 = cv2.imread(out_file, 0)
      ih,iw = im1.shape
      empty = np.zeros((ih,iw),dtype=np.uint8)
      cv2.imwrite(meteor_out_file, empty)
      night_out_file = img_dir + cams_id + "-night-stack.png"
      print ("Only fails and no meteors exist")
      os.system("cp " + out_file + " " + night_out_file)
      print(night_out_file)
   elif cfe(out_file) == 0 and cfe(meteor_out_file) == 0:
      ih,iw = 576,704
      empty = np.zeros((ih,iw),dtype=np.uint8)
      night_out_file = img_dir + cams_id + "-night-stack.png"
      cv2.imwrite(meteor_out_file, empty)
      cv2.imwrite(out_file, empty)
      cv2.imwrite(night_out_file, empty)
      print(meteor_out_file)
      print(out_file)
      print(night_out_file)


def move_images(json_conf):
 
   proc_dir = json_conf['site']['proc_dir']
   days = get_days(json_conf)
   for day in days:
      cmd = "mv " + proc_dir + day + "/*.png " + proc_dir + day + "/images/"
      print(cmd)
      os.system(cmd)
      cmd = "mv " + proc_dir + day + "/*.txt " + proc_dir + day + "/data/"
      print(cmd)
      os.system(cmd)
  
def update_file_index(json_conf):
   proc_dir = json_conf['site']['proc_dir']
   data_dir = proc_dir + "/json/"
 
   stats = {}

   json_file = data_dir + "main-index.json"
   stats = load_json_file(json_file) 
   days = get_days(json_conf)
   days = sorted(days, reverse=True)
   new_stats = {}
   days = days[0:3]

   for day in days:
      (failed_files, meteor_files,pending_files,min_files) = get_day_stats(proc_dir + day + "/", json_conf)

      new_stats[day] = {}
      new_stats[day]['failed_files'] = len(failed_files)
      new_stats[day]['meteor_files'] = len(meteor_files)
      new_stats[day]['pending_files'] = len(pending_files)
      new_min_files, cam_counts = count_min_files(min_files,json_conf)
      new_stats[day]['min_files'] = len(new_min_files)
      for key in cam_counts:
         new_stats[day][key] = cam_counts[key]


   new_stats_copy = new_stats.copy()
   for day in stats:
      new_stats[day] = stats[day]
   for day in new_stats_copy:
      new_stats[day] = new_stats_copy[day]
   save_json_file(json_file, new_stats)
   print(json_file)

def count_min_files(min_files,json_conf):
   new_min_files = []
   cam_counts = {}
   for camera in json_conf['cameras']:
      cams_id = json_conf['cameras'][camera]['cams_id']
      cam_counts[cams_id] = 0
   
   for file in min_files:
      el = file.split("_")
      if "trim" in file or len(el) <=9:
         skip = 1
      else:
         cams_id = el[9].replace(".mp4","")
         cam_counts[cams_id] = cam_counts[cams_id] + 1
         new_min_files.append(file)
   return(new_min_files, cam_counts)



def make_file_index(json_conf ):
   proc_dir = json_conf['site']['proc_dir']
   data_dir = proc_dir + "/json/"
   days = get_days(json_conf)
   
   d = 0
   html = ""
   stats = {}

   json_file = data_dir + "main-index.json"

   for day in days:

      (failed_files, meteor_files,pending_files,min_files) = get_day_stats(proc_dir + day + "/", json_conf)

      stats[day] = {}
      stats[day]['failed_files'] = len(failed_files)
      stats[day]['meteor_files'] = len(meteor_files)
      stats[day]['pending_files'] = len(pending_files)
      new_min_files, cam_counts = count_min_files(min_files,json_conf)
      stats[day]['min_files'] = len(new_min_files)
      for key in cam_counts:
         stats[day][key] = cam_counts[key]
      
      print(day)
   json_file = data_dir + "main-index.json"
   save_json_file(json_file, stats)
   print(json_file)


def thumb_mp4s(mp4_files,json_conf):
   stack_image = None
   objects = []
   # there should be 3 types of MP4 files (sd, hd, crop)
   # for each of these there should be a : stack & stack_tn
   # the sd file should also have an obj and obj_tn

   for file in mp4_files:
      print("WORKING ON FILE:", file)

      stack_file = file.replace(".mp4", "-stacked.png") 
      draw_file = file.replace(".mp4", "-stacked-obj.png") 
      stack_thumb = stack_file.replace(".png", "-tn.png") 
      meteor_json_file = file.replace(".mp4", ".json") 

      if "crop" in meteor_json_file:
         if cfe(stack_file) == 0 :
            frames = load_video_frames(file,json_conf)
            stack_file, stack_image = stack_frames(frames, file)
         if cfe(stack_thumb) == 0 :
            thumb(stack_file)

      elif "HD" in meteor_json_file and "crop" not in meteor_json_file:
         if cfe(stack_file) == 0 :
            frames = load_video_frames(file,json_conf)
            stack_file, stack_image = stack_frames(frames, file)
         if cfe(stack_thumb) == 0 :
            thumb(stack_file)

      else:
         meteor_json = load_json_file(meteor_json_file)
         objects = meteor_json['sd_objects']
         if cfe(stack_file) == 0 :
            frames = load_video_frames(file,json_conf)
            stack_file, stack_image = stack_frames(frames, file)
         if cfe(stack_thumb) == 0 :
            thumb(stack_file)

      draw_file_tn = draw_file.replace(".png", "-tn.png")
      if cfe(draw_file) == 0:
         print("DRAW:", draw_file)
         stack_image = cv2.imread(stack_file, 0)
         if len(objects) > 0:
            print(objects)
            draw_stack(objects,stack_image,stack_file)
         else:
            cmd = "cp " + stack_file + " " + draw_file
            os.system(cmd)
            draw_file_tn = draw_file.replace(".png", "-tn.png")
      if cfe(draw_file_tn) == 0  :
         thumb(draw_file)

def batch_meteor_thumb(json_conf):
   meteor_base_dir = "/mnt/ams2/meteors/"
   meteor_dirs = glob.glob(meteor_base_dir + "/*")
   for meteor_dir in meteor_dirs:
      mp4_files = glob.glob(meteor_dir + "/*.mp4")
      thumb_mp4s(mp4_files,json_conf)

def batch_thumb(json_conf):
   print("BATCH THUMB")
   proc_dir = json_conf['site']['proc_dir']
   temp_dirs = glob.glob(proc_dir + "/*")
   proc_days = []
   for proc_day in temp_dirs :
      if "daytime" not in proc_day and "json" not in proc_day and "meteors" not in proc_day and cfe(proc_day, 1) == 1:
         proc_days.append(proc_day+"/")

   for proc_day in sorted(proc_days,reverse=True):
      folder = proc_day + "/images/"
      print("FOLDER", folder)
      glob_dir = folder + "*-stacked.png"
      image_files = glob.glob(glob_dir) 
      for file in image_files:
         tn_file = file.replace(".png", "-tn.png")
         if cfe(tn_file) == 0:
            print(file)
            thumb(file)

def batch_obj_stacks(json_conf):
   proc_dir = json_conf['site']['proc_dir']

   temp_dirs = glob.glob(proc_dir + "/*")
   proc_days = []
   for proc_day in temp_dirs :
      if "daytime" not in proc_day and "json" not in proc_day and "meteors" not in proc_day and cfe(proc_day, 1) == 1:
         proc_days.append(proc_day+"/")
   for proc_day in sorted(proc_days,reverse=True):
      folder = proc_day + "/"
      stack_folder(folder,json_conf)

def stack_folder(folder,json_conf):
   print("GOLD:", folder)
   [failed_files, meteor_files,pending_files] = get_day_stats(folder, json_conf)
   for file in meteor_files:
      stack_file = file.replace(".mp4", "-stacked.png")
      stack_img = cv2.imread(stack_file,0)
      stack_obj_file = file.replace(".mp4", "-stacked-obj.png")
      obj_json_file = file.replace(".mp4", ".json")
      objects = load_json_file(obj_json_file)
      if cfe(stack_obj_file) == 0: 
         try:
            draw_stack(objects,stack_img,stack_file)
         except:
            print("draw failed")
   for file in failed_files:
      stack_file = file.replace(".mp4", "-stacked.png")
      stack_img = cv2.imread(stack_file,0)
      stack_obj_file = file.replace(".mp4", "-stacked-obj.png")
      obj_json_file = file.replace(".mp4", ".json")
      objects = load_json_file(obj_json_file)
      if cfe(stack_obj_file) == 0:
         try:
            draw_stack(objects,stack_img,stack_file)
         except:
            print("draw failed")
