#!/usr/bin/python3

"""
This script is the work manager for each day. 
  * Run this script through the day to keep data up to date and in sync.
  * Run this script after a day has finished to close out all work relating to that day. 
  * Script will perform the following functions.
     - Make sure all processed video files, stack images and data file are in the right place
     - Create archive time lapse videos of 24 hours of stack images for the day
     - Create meteor index for the day
     - Make sure all meteor thumbs exist
     - Make sure all meteors have been moved to the archive
     - Delete any false meteors tagged by admins or others
     - Sync all relevant files for the day to wasabi (archive meteors, preview images, NOAA files, event date
     - Run detections for the day (if master node)
     - Run all event solutions for the day
     - Stack daytime images
     - Produce Ops report for the day
     - Purge Disk Space



"""

import os
import glob
import sys
from datetime import datetime, timedelta
import subprocess

from lib.FileIO import load_json_file, save_json_file, cfe
from lib.UtilLib import check_running

json_conf = load_json_file("../conf/as6.json")

def load_events(day):
   year = day[0:4]
   event_index = "/mnt/archive.allsky.tv/" + "/EVENTS/" + year + "/" + day + "/" + day +"-events.json"
   event_files_index = "/mnt/archive.allsky.tv/" + "/EVENTS/" + year + "/" + day + "/" + day + "-event-files.json"
   event_files = {}
   if cfe(event_index) == 1:
      events = load_json_file(event_index)
      for event in events:
         if events[event]['count'] >= 2:
            for file in events[event]['files']:
               event_files[file] = event
      save_json_file(event_files_index,event_files ) 
      print("Saved:", event_files_index)
   else:
      events = {}
      event_files = {}
   return(events,event_files)

def run_df():
   df_data = []
   mounts = {}
   if True:
      cmd = "df -h "
      output = subprocess.check_output(cmd, shell=True).decode("utf-8")
      #Filesystem                 Size  Used Avail Use% Mounted on

      for line in output.split("\n"):
         file_system = line[0:20]
         size = line[20:26]
         used = line[27:38]
         avail = line[38:44]
         used_perc = line[44:49]
         mount = line[49:].replace(" ", "")
         if mount == "/" or mount == "/mnt/ams2" or mount == "/mnt/archive.allsky.tv":
            df_data.append((file_system, size, used, avail, used_perc, mount))
            used_perc = used_perc.replace(" ", "")
            mounts[mount] = int(used_perc.replace("%", ""))
   else:
      print("Failed du")
   return(df_data, mounts)

def check_disk():
   df_data, mounts = run_df()

   if "/mnt/archive.allsky.tv" not in mounts:
      print("Wasabi is not mounted! Mounting now.")
      os.system("./wasabi.py mnt")
   if mounts["/mnt/ams2"] > 80:
      print("Data volume /mnt/ams2 is greater than 80%!", mounts["/mnt/ams2"]) 
   if mounts["/"] > 80:
      print("Root volume / is greater than 80%!", mounts["/mnt/ams2"]) 

   # first get the HD files and start deleting some of then (remove the last 12 hours) 
   # then check disk again if it is still over 80% delete some more. 
   # continue to do this until the disk is less than 80% or there are only a max of 2 days of HD files left
   if mounts["/mnt/ams2"] > 80:
      print("Data volume /mnt/ams2 is greater than 80%!", mounts["/mnt/ams2"]) 
      hd_files = sorted(glob.glob("/mnt/ams2/HD/*.mp4"))
      print(len(hd_files), " HD FILES")
      del_count = int(len(hd_files) / 10)
      for file in hd_files[0:del_count]:
         if "meteor" not in file:
            print("Delete this file!", file)
            os.system("rm " + file)

   # check SD dir  
   # if the disk usage is over 80% 
   # get folders in /proc2, delete the folders one at a time and re-check disk until disk <80% or max of 30 folders exist

   # remove trash and other tmp dirs

def batch(num_days):

   # first make sure the batch is not already running.
   running = check_running("doDay.py")
   print("Running:", running)
   if running > 1:
      print("Already running.")
      exit()

   today = datetime.today()
   for i in range (0,int(num_days)):
      past_day = datetime.now() - timedelta(hours=24*i)
      past_day = past_day.strftime("%Y_%m_%d")
      print(past_day)
      do_all(past_day)

def make_station_report(day, proc_info = ""):
   print("PROC INFO:", proc_info)
   # MAKE STATION REPORT FOR CURRENT DAY
   station = json_conf['site']['ams_id']
   year,mon,dom = day.split("_")
   STATION_RPT_DIR =  "/mnt/archive.allsky.tv/" + station + "/REPORTS/" + year + "/" + mon + "_" + dom + "/"
   NOAA_DIR =  "/mnt/archive.allsky.tv/" + station + "/NOAA/ARCHIVE/" + year + "/" + mon + "_" + dom + "/"
   if cfe(STATION_RPT_DIR, 1) == 0:
      os.makedirs(STATION_RPT_DIR)
   html_index = STATION_RPT_DIR + "index.html"
   noaa_files = glob.glob(NOAA_DIR + "*.jpg")
   data = {}
   data['files'] = noaa_files

   events,event_files = load_events(day)
   detect_html = html_get_detects(day, station, event_files,events)

   header_html, footer_html = html_header_footer()


   html = header_html
   show_date = day.replace("_", "/")
   html += "<h1>" + station + " Daily Report for " + show_date + "</h1>\n"
   html += "<h2><a href=\"#\" onclick=\"showHideDiv('live_view')\">Live View</a></h2>\n <div id='live_view'>"
   if len(data['files']) > 0:
      data['files'] = sorted(data['files'], reverse=True)
      fn = data['files'][0].replace("/mnt/archive.allsky.tv", "")
      html += "<img src=" + fn + "><BR>\n"
   html += "</div>"

   html += "<h2><a href=\"#\" onclick=\"showHideDiv('live_snaps')\">Weather Snap Shots</a></h2>\n <div id='live_snaps' style='display: none'>"
   for file in sorted(data['files'],reverse=True):
      fn = file.replace("/mnt/archive.allsky.tv", "")
      html += "<img src=" + fn + "><BR>\n"
   html += "</div>"

   html += "<h2><a href=\"#\" onclick=\"showHideDiv('meteors')\">Meteors</a></h2>\n <div id='meteors'>"
   html += detect_html
   html += "</div>"

   html += "</div>"
   html += "<div style='clear: both'></div>"
   html += "<h2><a href=\"#\" onclick=\"showHideDiv('proc_info')\">Processing Info</a></h2>\n <div id='proc_info'>"
   html += "<PRE>" + proc_info + "</PRE>"
   html += "</div>"

   fpo = open(html_index, "w")
   fpo.write(html)
   fpo.close()
   print(html_index)

def do_css():
   css = """

      <style>
         #pending {
            background-color: blue;
            color: black;
            float: left;
            padding: 5px;
         }
         #arc {
            background-color: green;
            color: black; 
            float: left;
            padding: 5px;
         }
         #multi {
            background-color: red;
            color: black; 
            float: left;
            padding: 5px;
         }
      </style>

   """
   return(css)

def html_get_detects(day,tsid,event_files, events):
   year = day[0:4]
   mi = "/mnt/ams2/meteor_archive/" + json_conf['site']['ams_id'] + "/DETECTS/MI/" + year + "/" +  day + "-meteor_index.json"
   print(mi)
   mid = load_json_file(mi)
   meteor_detects = []
   prev_dir = "/mnt/archive.allsky.tv/" + tsid + "/DETECTS/PREVIEW/" + year + "/" + day + "/" 
   prev_file = "/mnt/archive.allsky.tv/" + tsid + "/DETECTS/PREVIEW/" + year + "/" + day + "/" + "index.html"
   html = ""
   was_prev_dir = "/mnt/archive.allsky.tv/" + tsid + "/DETECTS/PREVIEW/" + year + "/" + day + "/" 
   was_vh_dir = "/" + tsid + "/DETECTS/PREVIEW/" + year + "/" + day + "/" 

   if day in mid:
      for key in mid[day]:
         if "archive_file" in mid[day][key]:
            arc = 1
            arc_file = mid[day][key]['archive_file']
            style = "arc"
         else:
            arc = 0
            arc_file = "pending"
            style = "pending"
         if key in event_files:
            event_id = event_files[key]
            
            event_info = events[event_id]

            print("KEY", key, event_files[key])
            style = "multi"
            # look for the event solution dir
            event_dir = "/mnt/archive.allsky.tv/EVENTS/" + year + "/" + day + "/" + event_id + "/"
            event_vdir = "/EVENTS/" + year + "/" + day + "/" + event_id + "/"
            event_file = event_dir + event_id + "-report.html"
            event_vfile = event_vdir + event_id + "-report.html"
          
            if cfe(event_dir,1) == 1:
               print("Event dir found.", event_dir)
               if cfe(event_file) == 1:
                  elink = "<a href=" + event_vfile + ">"
               else:
                  print("NT F:", event_file)
                  elink = ""
            else:
               print("Event dir not found.", event_dir)
               elink = ""
         else:
            event_id = None
         mfile = key.split("/")[-1]
         prev_crop = mfile.replace(".json", "-prev-crop.jpg")
         prev_full = mfile.replace(".json", "-prev-full.jpg")
         if event_id is not None:
            html += "<div style id='" + style + "'><figure><img src=" + was_vh_dir + prev_crop + "><figcaption>" + elink + event_id+ "</a></figcaption></figure></div>"
         else:
            html += "<div style id='" + style + "'><figure><img src=" + was_vh_dir + prev_crop + "><figcaption>" + "no event id" + "</figcaption></figure></div>"
   else:
      html += "No meteors detected."

   return(html)


def html_header_footer(info=None):
   js = javascript()
   css = do_css() 
   html_header = """
     <head>
        <meta http-equiv="Cache-control" content="public, max-age=500, must-revalidate">
   """
   html_header += js + "\n" + css + """
     </head>
   """

   html_footer = """

   """
   return(html_header, html_footer)

def javascript():
   js = """
      <script>
      function showHideDiv(myDIV) {
         var x = document.getElementById(myDIV);
         if (x.style.display === "none") {
            x.style.display = "block";
         } else {
            x.style.display = "none";
         }
      }

      </script>
   """
   return(js)


def get_processing_status(day):
   proc_dir = "/mnt/ams2/SD/proc2/" + day + "/*"
   proc_img_tn_dir = "/mnt/ams2/SD/proc2/" + day + "/images/*tn.png"
   proc_vids = glob.glob(proc_dir)
   proc_tn_imgs = glob.glob(proc_img_tn_dir)

   #proc_img_dir = "/mnt/ams2/SD/proc2/" + day + "/images/*.png"
   #proc_imgs = glob.glob(proc_img_dir)


   day_vids = glob.glob("/mnt/ams2/SD/proc2/daytime/" + day + "*.mp4")
   cams_queue = glob.glob("/mnt/ams2/CAMS/queue/" + day + "*.mp4")
   in_queue = glob.glob("/mnt/ams2/SD/" + day + "*.mp4")
   return(proc_vids, proc_tn_imgs, day_vids,cams_queue,in_queue)

def get_meteor_status(day):
   detect_files = []
   arc_file = []
   year, mon, dom = day.split("_")
   detect_dir = "/mnt/ams2/meteors/" + day + "/"
   arc_dir = "/mnt/ams2/meteor_archive/" + json_conf['site']['ams_id'] + "/METEOR/" + year + "/" + mon + "/" + dom + "/"

   
   # get detect and arc files
   dfiles = glob.glob(detect_dir + "*trim*.json")
   arc_files = glob.glob(arc_dir + "*trim*.json")

   # filter out non-meteor or dupe meteor json files
   for df in dfiles:
      if "reduced" not in df and "manual" not in df and "stars" not in df:
         detect_files.append(df)

   return(detect_files, arc_files)
   

def do_all(day):
   proc_vids, proc_tn_imgs, day_vids,cams_queue,in_queue = get_processing_status(day)
   detect_files, arc_files = get_meteor_status(day)

   # figure out how much of the day has completed processing
   rpt = """
   Processing report for day: """ + day + """
   Processed Videos:""" + str(len(proc_vids)) + """
   Processed Thumbs:""" +  str(len(proc_tn_imgs)) + """
   Un-Processed Daytime Videos:""" +  str(len(day_vids)) + """
   Un-Processed CAMS Queue:""" + str(len(cams_queue)) + """
   Un-Processed IN Queue:""" + str(len(in_queue)) + """
   Possible Meteor Detections:""" + str(len(detect_files)) + """
   Archived Meteors :""" + str(len(arc_files)) + """
   Unique Meteors: ???"""  + """
   Multi-station Events: ???"""  + """
   Solved Events: ???"""  + """
   Events That Failed to Solve: ???""" 

   print ("RPT:", rpt)
   if len(cams_queue) < 10 and len(in_queue) < 10:
      proc_status = "up-to-date"

 
   # make the meteor detection index for today
   os.system("./autoCal.py meteor_index " + day)

   # make the detection preview images for the day
   os.system("./flex-detect.py bmpi " + day)

   # make the detection preview images for the day
   os.system("./wasabi.py sa " + day)

   make_station_report(day, rpt)


cmd = sys.argv[1]


if cmd == "all":
   do_all(sys.argv[2])
if cmd == "msr":
   make_station_report(sys.argv[2])
if cmd == "batch":
   batch(sys.argv[2])
if cmd == "cd":
   check_disk()
