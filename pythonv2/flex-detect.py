#!/usr/bin/python3

from sklearn.cluster import DBSCAN

from lib.REDUCE_VARS import *
from lib.Video_Tools_cv_pos import *
from lib.Video_Tools_cv import *
from PIL import ImageFont, ImageDraw, Image, ImageChops
from lib.VIDEO_VARS import *
from lib.UtilLib import calc_dist,find_angle, best_fit_slope_and_intercept
from lib.MeteorTests import test_objects
import datetime
import time
import glob
import os
import math
import cv2
import math
import numpy as np
import scipy.optimize
import ephem
from lib.flexCal import flex_get_cat_stars, reduce_fov_pos


from lib.VideoLib import get_masks, find_hd_file_new, load_video_frames, sync_hd_frames, make_movie_from_frames, add_radiant

from lib.UtilLib import check_running, angularSeparation
from lib.CalibLib import radec_to_azel, clean_star_bg, get_catalog_stars, find_close_stars, XYtoRADec, HMS2deg, AzEltoRADec, get_active_cal_file

from lib.ImageLib import mask_frame , stack_frames, preload_image_acc, thumb
from lib.ReducerLib import setup_metframes, detect_meteor , make_crop_images, perfect, detect_bp, best_fit_slope_and_intercept, id_object, metframes_to_mfd

from lib.MeteorTests import meteor_test_cm_gaps


import sys
from lib.CalibLib import distort_xy_new, find_image_stars, distort_xy_new, XYtoRADec, radec_to_azel, get_catalog_stars,AzEltoRADec , HMS2deg, get_active_cal_file, RAdeg2HMS, clean_star_bg
from lib.UtilLib import calc_dist, find_angle, bound_cnt, cnt_max_px

from lib.UtilLib import angularSeparation, convert_filename_to_date_cam, better_parse_file_date
from lib.FileIO import load_json_file, save_json_file, cfe
from lib.UtilLib import calc_dist,find_angle
import lib.brightstardata as bsd
from lib.DetectLib import eval_cnt, check_for_motion2

json_conf = load_json_file("../conf/as6.json")
show = 0

ARCHIVE_DIR = "/mnt/NAS/meteor_archive/"

def fix_missing_hd(dir):
   files = glob.glob(dir + "*.json")
   for file in files:
      if "reduced" not in file:
         data = load_json_file(file)
         if "hd_trim" in data:
            if data['hd_trim'] == 0:
               print("hd trim is 0:", file)
               print("hd file is :", data['hd_video_file'])
               if data['hd_video_file'] != 0: 
                  hd_fn = data['hd_video_file'].split("/")[-1]
                  hd_fn = hd_fn.replace(".mp4", "*HD-meteor.mp4")
                  trim_wild = dir + hd_fn
                  trims = glob.glob(trim_wild)
                  if len(trims) > 0:
                     print("NEW FOUND TRIM IS :", trims[0])
                     data['hd_trim'] = trims[0]
                     save_json_file(file, data)
                  else:
                     print("No trims found.") 
               else:
                  print("no hd_video_file variable either!", file)

            else:
               print("hd trim is good:", file)
         else:
               print("hd_trim is missing.", file)

def stack_non_meteors():
   files = glob.glob("/mnt/ams2/non_meteors/*.mp4")
   for file in files:
      stack_file = file.replace(".mp4", "-stacked.png")
      data_file = file.replace(".mp4", "-detect.json")
      if cfe(data_file) == 1:
         data = load_json_file(data_file)
      else:
         data = []
      print("STACK:", stack_file, data)
      #if cfe(stack_file) == 0:
      if True:
         frames,color_frames,subframes,sum_vals,max_vals = load_frames_fast(file, json_conf, 0, 0, [], 0,[])
         stacked_file, stacked_image = stack_frames(frames, file, 0)
         for obj in data:
            x1,y1,x2,y2 = minmax_xy(obj)
            cv2.rectangle(stacked_image, (x1, y1), (x2, y2), (255,255,255), 1, cv2.LINE_AA)
            desc = obj['report']['obj_class']
            cv2.putText(stacked_image, desc,  (x1,y1), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)


def batch_move():
   files = glob.glob("/mnt/ams2/CAMS/queue/*.mp4")
   for video_file in files:
      if "trim" in video_file:
         trim = 1
         stack_file = video_file.replace(".mp4", "-stacked.png")
      
      else:
         trim = 0
         stack_file = video_file.replace(".mp4", "-stacked.png")
         meteor_file = video_file.replace(".mp4", "-meteor.json")
         fail_file = video_file.replace(".mp4", "-fail.json")
      if cfe(stack_file) == 1 and trim != 1:
         # processing is done for this file
         video_fn = video_file.split("/")[-1]
         stack_fn = stack_file.split("/")[-1]
         meteor_fn = meteor_file.split("/")[-1]
         fail_fn = meteor_file.split("/")[-1]
         (hd_datetime, cam, sd_date, sd_y, sd_m, sd_d, sd_h, sd_M, sd_s) = convert_filename_to_date_cam(video_file)
         proc_dir = "/mnt/ams2/SD/proc2/" + sd_y + "_" + sd_m + "_" + sd_d + "/" 
         if cfe(proc_dir, 1) == 0 or cfe(proc_dir + "images", 1 ) == 0:
            os.system("mkdir " + proc_dir)
            os.system("mkdir " + proc_dir + "failed")
            os.system("mkdir " + proc_dir + "passed")
            os.system("mkdir " + proc_dir + "images")
            os.system("mkdir " + proc_dir + "data")
         if cfe(meteor_file) == 0:
            cmd = "mv " + video_file + " " + proc_dir
            print(cmd)
            os.system(cmd)
            cmd = "mv " + stack_file + " " + proc_dir + "images/"
            print(cmd)
            os.system(cmd)
            if cfe(fail_file) == 1:
               cmd = "mv " + fail_file + " " + proc_dir + "failed/"
               print(cmd)
               os.system(cmd)
            #cmd = "mv " + meteor_file + " " + proc_dir + "passed/"

def find_sun_alt(capture_date):

   device_lat = json_conf['site']['device_lat']
   device_lng = json_conf['site']['device_lng']

   obs = ephem.Observer()

   obs.pressure = 0
   obs.horizon = '-0:34'
   obs.lat = device_lat
   obs.lon = device_lng
   obs.date = capture_date

   sun = ephem.Sun()
   sun.compute(obs)

   (sun_alt, x,y) = str(sun.alt).split(":")

   saz = str(sun.az)
   (sun_az, x,y) = saz.split(":")
   if int(sun_alt) < -1:
      sun_status = "night"
   else:
      sun_status = "day"
   print("SUN AZ:", sun_az)
   print("SUN ALT:", sun_alt)
   return(int(sun_alt))


def objects_to_clips(meteor_objects):
   clips = []
   good_objs = []
   for obj in meteor_objects:
      if len(obj['ofns']) > 2:
         ok = 1 
         for clip in clips:
            if abs(obj['ofns'][0] - clip) < 25:
               ok = 0
         if ok == 1:
            clips.append(obj['ofns'][0])
            good_objs.append(obj)
      
   return(good_objs)

def batch_confirm():
   files = glob.glob("/mnt/ams2/CAMS/queue/*meteor.json")
   for file in files:
      print(file)
      confirm_meteor(file)

def minmax_xy(obj):
   min_x = min(obj['oxs'])
   max_x = max(obj['oxs'])
   min_y = min(obj['oys'])
   max_y = max(obj['oys'])
   return(min_x, min_y, max_x, max_y)

def save_new_style_meteor_json (meteor_obj, trim_clip ):
   print("MO:", meteor_obj)
   mj = {}
   (hd_datetime, cam, sd_date, sd_y, sd_m, sd_d, sd_h, sd_M, sd_s) = convert_filename_to_date_cam(trim_clip)
   mj['calib'] = meteor_obj['calib']
   mj['dt'] = hd_datetime
   tc = trim_clip.split("/")[-1]
   mj['dt'] = meteor_obj['dt']
   mj['info'] = {}
   mj['info']['station'] = json_conf['site']['ams_id'].upper()
   mj['info']['hd_vid'] = meteor_obj['hd_file']
   mj['info']['sd_vid'] = meteor_obj['sd_file']
   mj['info']['org_hd_vid'] = meteor_obj['hd_trim']
   mj['info']['org_sd_vid'] = meteor_obj['trim_clip']
   mj['info']['device'] = cam
   if "report" in meteor_obj:
      mj['report'] = meteor_obj['report']
      mj['report']['max_peak'] = max(meteor_obj['oint'])
      mj['report']['dur'] = meteor_obj['dur']

   mj['frames'] = []
   used_fn = {}
   for i in range(0, len(meteor_obj['ofns'])):
      fd = {}
      fd['fn'] = meteor_obj['ofns'][i] + 1
      fd['x'] = meteor_obj['oxs'][i]
      fd['y'] = meteor_obj['oys'][i]
      fd['dt'] = meteor_obj['ftimes'][i]

      new_x, new_y, ra ,dec , az, el = XYtoRADec(fd['x'],fd['y'],trim_clip,meteor_obj['cal_params'],json_conf)
      print("AZ:EL", fd['x'], fd['y'], az, el, fd['dt'], meteor_obj['cal_params']['ra_center'], meteor_obj['cal_params']['dec_center']) 

      fd['az'] = az 
      fd['el'] = el
      fd['dec'] = dec
      fd['ra'] = ra 

      fd['w'] = meteor_obj['ows'][i]
      fd['h'] = meteor_obj['ohs'][i]
      fd['max_px'] = meteor_obj['oint'][i]
      if fd['fn'] not in used_fn:
         mj['frames'].append(fd)
      used_fn[fd['fn']] = 1
   mj['sync'] = {}
   mj['sync']['sd_ind'] = meteor_obj['ofns'][0]
   mj['sync']['hd_ind'] = meteor_obj['ofns'][0]
   #mj['sync']['sd_ind'] = sd_start_frame
   #mj['sync']['hd_ind'] = hd_start_frame
   
   print("NEW METEOR SAVE!")
   print(mj)
   return(mj)

def archive_path(old_file):
   ofn = old_file.split("/")[-1]
   station_id = json_conf['site']['ams_id']
   (hd_datetime, cam, sd_date, sd_y, sd_m, sd_d, sd_h, sd_M, sd_s) = convert_filename_to_date_cam(old_file)
   new_archive_file = METEOR_ARCHIVE + station_id + "/" + METEOR + "/" + sd_y + "/" + sd_m + "/" + sd_d + "/" + ofn
   return(new_archive_file)
   
   

def save_old_style_meteor_json(meteor_json_file, meteor_obj, trim_clip ):
   #old json object
   mfj = meteor_json_file.split("/")[-1]
   meteor_dir = meteor_json_file.replace(mfj, "")
   if "hd_trim" in meteor_obj:
      if meteor_obj['hd_trim'] != 0:
         if "/mnt/ams2/HD" in meteor_obj['hd_trim'] :
            print("FIX HD TRIM!")
            hdf = meteor_obj['hd_trim'].split("/")[-1]
            hd_trim = meteor_dir + hdf 
            print("HDF!", hdf, hd_trim)
         else:
            hd_trim = meteor_obj['hd_trim']
   else:
      print("No HD trim in obj", meteor_obj)
      meteor_obj['hd_trim'] = 0
      meteor_obj['hd_video_file'] = 0
      meteor_obj['hd_crop'] = 0
   oj = {}
   oj['sd_video_file'] = meteor_json_file.replace(".json", ".mp4")
   sd_stack = meteor_json_file.replace(".json", "-stacked.png")

   oj['sd_stack'] = sd_stack
   oj['hd_stack'] = sd_stack
   oj['hd_video_file'] = meteor_obj['hd_video_file']
   oj['hd_trim'] = hd_trim
   oj['hd_crop_file'] = 0
   oj['hd_box'] = [0,0,0,0]
   oj['hd_objects'] = []
   if "new_json_file" in meteor_obj:
      oj['archive_file'] = archive_path(meteor_obj['new_json_file'])

   # make SD objects from new meteor
   sd_objects = {}
   ofns = meteor_obj['ofns']
   oxs = meteor_obj['oxs']
   oys = meteor_obj['oys']
   ows = meteor_obj['ows']
   ohs = meteor_obj['ohs']
   hist = []
   for i in range (0, len(ofns)-1):
      fn = ofns[i]
      x = oxs[i]
      y = oys[i]
      w = ows[i]
      h = ohs[i]
      hist.append((fn,x,y,w,h,0,0))
   sd_objects['oid'] = 1
   sd_objects['fc'] = len(ofns)
   sd_objects['x'] = oxs[0]
   sd_objects['y'] = oys[0]
   sd_objects['w'] = max(ows)
   sd_objects['h'] = max(ohs)
   sd_objects['history'] = hist
      

   oj['sd_objects'] = [sd_objects]
   oj['status'] = "moving"
   oj['total_frames'] = len(ofns)
   oj['meteor'] = 1
   oj['test_results'] = []
   oj['hd_trim_dur'] = []
   oj['hd_trim_time_offset'] = []
   oj['flex_detect'] = meteor_obj
   save_json_file(meteor_json_file, oj)

def detect_meteor_in_clip(trim_clip, frames = None, fn = 0, crop_x = 0, crop_y = 0):
   objects = {}
   print("TC:", trim_clip)


   if frames is None: 
        
      frames,color_frames,subframes,sum_vals,max_vals = load_frames_fast(trim_clip, json_conf, 0, 1, [], 0,[])
   if len(frames) == 0:
      return(objects, []) 

   if frames[0].shape[1] == 1920:
      hd = 1
      sd_multi = 1
   else:
      hd = 0
      sd_multi = 1920 / frames[0].shape[1]

   image_acc = frames[0]
   image_acc = np.float32(image_acc)

   for i in range(0,len(frames)):
      frame = frames[i]
      blur_frame = cv2.GaussianBlur(frame, (7, 7), 0)
      alpha = .5
      hello = cv2.accumulateWeighted(blur_frame, image_acc, alpha)

   for frame in frames:
      show_frame = frame.copy()
      frame = np.float32(frame)
      blur_frame = cv2.GaussianBlur(frame, (7, 7), 0)
      alpha = .5


      image_diff = cv2.absdiff(image_acc.astype(frame.dtype), blur_frame,)
      hello = cv2.accumulateWeighted(blur_frame, image_acc, alpha)

      show_frame = frame.copy()
      avg_px = np.mean(image_diff)
      min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(image_diff)
      thresh = avg_px + ((max_val - avg_px) / 2)
      if thresh < 5:
         thresh = 5 

      cnts,rects = find_contours_in_frame(image_diff, thresh)

      icnts = []
      if len(cnts) < 5 and fn > 4:
         for (cnt) in cnts:
            px_diff = 0
            x,y,w,h = cnt
            if w > 1 and h > 1:
               intensity,mx,my,cnt_img = compute_intensity(x,y,w,h,frame,frames[0])
               cx = int(mx) 
               cy = int(my) 
               cv2.circle(show_frame,(cx+crop_x,cy+crop_y), 10, (255,255,255), 1)

               object, objects = find_object(objects, fn,cx+crop_x, cy+crop_y, w, h, intensity, hd, sd_multi, cnt_img)
               #if len(objects[object]['ofns']) > 2:
                  #le_x, le_y = find_leading_edge(objects[object]['report']['x_dir_mod'], objects[object]['report']['y_dir_mod'],cx,cy,w,h,frame)

               objects[object]['trim_clip'] = trim_clip
               cv2.rectangle(show_frame, (x, y), (x+w, y+h), (255,255,255), 1, cv2.LINE_AA)
               desc = str(fn) + " " + str(intensity) + " " + str(objects[object]['obj_id']) + " " + str(objects[object]['report']['obj_class']) + " " + str(objects[object]['report']['angular_vel'])
               cv2.putText(show_frame, desc,  (x,y), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
      
      show_frame = cv2.convertScaleAbs(show_frame)
      if show == 1:
         cv2.imshow('Detect Meteor In Clip', show_frame)
         cv2.waitKey(70)
      fn = fn + 1

   for obj in objects:
      objects[obj] = analyze_object(objects[obj])


   if show == 1:
      cv2.destroyAllWindows()

   return(objects, frames)   

def merge_cnts(cnts): 
   merge_cnts = []
   for (i,c) in enumerate(cnts):
      px_diff = 0
      x,y,w,h = cv2.boundingRect(cnts[i])
      if len(merge_cnts) == 0:
         merge_cnts.append((x,y,w,h))
      else:
         print("...")
         

def compute_intensity(x,y,w,h,frame, bg_frame):
   frame = np.float32(frame)
   bg_frame = np.float32(bg_frame)
   cnt = frame[y:y+h,x:x+w]
   size=max(w,h)
   min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(cnt)
   cx1,cy1,cx2,cy2 = bound_cnt(x+mx,y+my,frame.shape[1],frame.shape[0], size)
   cnt = frame[cy1:cy2,cx1:cx2]
   bgcnt = bg_frame[cy1:cy2,cx1:cx2]


   sub = cv2.subtract(cnt, bgcnt)
   min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(cnt)
   val = int(np.sum(sub))

   #print(cnt.shape)
   #show_image = cv2.convertScaleAbs(cnt)


   return(val,cx1+mx,cy1+my, cnt)

def reject_meteor(meteor_json_file):
   min_file = meteor_json_file.replace("-meteor.json", ".mp4")
   (hd_datetime, cam, sd_date, sd_y, sd_m, sd_d, sd_h, sd_M, sd_s) = convert_filename_to_date_cam(min_file)
   meteor_date = sd_y + "_" + sd_m + "_" + sd_d
   stack_file = meteor_json_file.replace("-meteor.json", "-stacked.png")
   proc_dir = "/mnt/ams2/SD/proc2/" + sd_y + "_" + sd_m + "_" + sd_d + "/"
   if cfe(proc_dir, 1) == 0:
      os.system("mkdir " + proc_dir)
      os.system("mkdir " + proc_dir + "images")
      os.system("mkdir " + proc_dir + "failed")
      os.system("mkdir " + proc_dir + "passed")
   
   cmd = "mv " + min_file + " " + proc_dir 
   print(cmd)
   os.system(cmd)

   cmd = "mv " + stack_file + " " + proc_dir + "images/"
   print(cmd)
   os.system(cmd)

   wild_card = meteor_json_file.replace("-meteor.json", "*")
   cmd = "mv " + wild_card + " /mnt/ams2/non_meteors/"
   print(cmd)
   os.system(cmd)

def get_cat_image_stars(cat_stars, frame,cal_params_file):
   show_frame = frame.copy()
   cat_image_stars = []
   used_istars = {}
   used_cstars = {}
   for cat_star in cat_stars:
      name,mag,ra,dec,new_cat_x,new_cat_y = cat_star
      cx1,cy1,cx2,cy2 = bound_cnt(new_cat_x,new_cat_y,frame.shape[1],frame.shape[0], 50)
      c_key = str(new_cat_x) + str(new_cat_y)

      pos_star = frame[cy1:cy2,cx1:cx2]
      min_val, max_val, min_loc, (ix,iy)= cv2.minMaxLoc(pos_star)
      if max_val - min_val > 20:
         cv2.rectangle(show_frame, (cx1,cy1), (cx2, cy2), (128, 128, 128), 1)

      cx1,cy1,cx2,cy2 = bound_cnt(cx1+ix,cy1+iy,frame.shape[1],frame.shape[0], 20)
      pos_star = frame[cy1:cy2,cx1:cx2]
      star_avg = np.median(pos_star)
      star_sum = np.sum(pos_star)
      star_int = star_sum - (star_avg * (pos_star.shape[0] * pos_star.shape[1]))

      min_val, max_val, min_loc, (ix,iy)= cv2.minMaxLoc(pos_star)
      ix = ix + cx1
      iy = iy + cy1
      px_diff = max_val - star_avg
      i_key = str(ix) + str(iy)

      if (new_cat_x < 10 or new_cat_x > 1910) or (new_cat_y < 10 or new_cat_y > 1070):
         star_int = 0
         px_diff = 0
      if mag >= 4 and star_int > 25000:
         bad =  1
      else:
         bad = 0

      if mag <= 3:
         cv2.circle(show_frame,(int(new_cat_x),int(new_cat_y)), 20, (128,128,128), 1)
      if star_int > 100 and px_diff > 15:
         dist = calc_dist((ix,iy),(new_cat_x,new_cat_y))
         cv2.line(show_frame, (ix,iy), (int(new_cat_x),int(new_cat_y)), (255), 2)
         #print("POS STAR:", name, star_int, px_diff, bad,dist)

      if star_int > 50 and px_diff > 10 and bad == 0:
         cv2.circle(show_frame,(int(ix),int(iy)), 5, (255,255,255), 1)
         px_dist = calc_dist((ix,iy), (new_cat_x, new_cat_y))
         #name #.decode("unicode_escape")
         if px_dist < 10 and i_key not in used_istars and c_key not in used_cstars:
            #cat_image_stars.append((name.decode("unicode_escape"),mag,ra,dec,new_cat_x,new_cat_y,ix,iy,star_int,px_dist,cal_params_file))
            cat_image_stars.append((name,mag,ra,dec,new_cat_x,new_cat_y,ix,iy,star_int,px_dist,cal_params_file))
            used_istars[i_key] = 1
            used_cstars[c_key] = 1
   if show == 1:
      cv2.imshow('cat_stars', show_frame)
      cv2.waitKey(70)
   return(cat_image_stars)



def format_calib(trim_clip, cal_params, cal_params_file):
   calib = {}
   tc = trim_clip.split("/")[-1]
   calib['dt'] = tc[0:23]
   calib['device'] = {}
   calib['device']['poly'] = {}
   calib['device']['poly']['x_fwd'] = cal_params['x_poly_fwd']
   calib['device']['poly']['y_fwd'] = cal_params['y_poly_fwd']
   calib['device']['poly']['x'] = cal_params['x_poly']
   calib['device']['poly']['y'] = cal_params['y_poly']
   calib['device']['center'] = {}
   calib['device']['center']['az'] = cal_params['center_az']
   calib['device']['center']['el'] = cal_params['center_el']
   calib['device']['center']['ra'] = cal_params['ra_center']
   calib['device']['center']['dec'] = cal_params['dec_center']
   calib['stars'] = []
   for (name,mag,ra,dec,new_cat_x,new_cat_y,ix,iy,intensity,px_dist,cpfile) in cal_params['cat_image_stars']:
      star = {}
      star['name'] = name
      star['mag'] = mag
      star['ra'] = ra
      star['dec'] = dec
      star['dist_px'] = px_dist
      star['intensity'] = int(intensity)
      star['i_pos'] = [int(ix),int(iy)]
      star['cat_dist_pos'] = [int(new_cat_x),int(new_cat_y)]
      star['cat_und_pos'] = [int(new_cat_x),int(new_cat_y)]
      calib['stars'].append(star)

   calib['img_dim'] = [1920,1080]
   calib['device']['alt'] = cal_params['device_alt']
   calib['device']['lat'] = cal_params['device_lat']
   calib['device']['lng'] = cal_params['device_lng']
   calib['device']['angle'] = cal_params['position_angle']
   calib['device']['scale_px'] = cal_params['pixscale']
   calib['device']['org_file'] = cal_params_file

   if "total_res_px" in cal_params:
      calib['device']['total_res_px'] = cal_params['total_res_px']
      calib['device']['total_res_deg'] = (cal_params['total_res_px'] * calib['device']['scale_px']) / 3600
   else:
      cal_params['total_res_px'] = 99
      calib['device']['total_res_px'] = 99
      calib['device']['total_res_deg'] = (cal_params['total_res_px'] * calib['device']['scale_px']) / 3600
   return(calib)

def get_image_stars(file,img=None, show=0):
   stars = []
   if img is None:
      img = cv2.imread(file, 0)
   avg = np.mean(img)
   best_thresh = avg + 12
   _, star_bg = cv2.threshold(img, best_thresh, 255, cv2.THRESH_BINARY)
   thresh_obj = cv2.dilate(star_bg, None , iterations=4)
   (_, cnts, xx) = cv2.findContours(thresh_obj.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
   cc = 0
   for (i,c) in enumerate(cnts):
      x,y,w,h = cv2.boundingRect(cnts[i])
      px_val = int(img[y,x])
      cnt_img = img[y:y+h,x:x+w]
      cnt_img = cv2.GaussianBlur(cnt_img, (7, 7), 0)
      max_px, avg_px, px_diff,max_loc = eval_cnt(cnt_img.copy())
      name = "/mnt/ams2/tmp/cnt" + str(cc) + ".png"
      #star_test = test_star(cnt_img)
      x = x + int(w/2)
      y = y + int(h/2)
      if px_diff > 5 and w > 1 and h > 1 and w < 50 and h < 50:
          stars.append((x,y,int(max_px)))
          cv2.circle(img,(x,y), 5, (128,128,128), 1)

      cc = cc + 1
   #if show == 1:
   #   cv2.imshow('pepe', img)
   #   cv2.waitKey(1)

   temp = sorted(stars, key=lambda x: x[2], reverse=True)
   stars = temp[0:50]
   return(stars)

def find_best_cat_stars(cat_stars, ix,iy, frame, cp_file):
   cx1,cy1,cx2,cy2 = bound_cnt(ix,iy,frame.shape[1],frame.shape[0], 5)
   intensity = int(np.sum(frame[cy1:cy2,cx1:cx2]))
   min_dist = 999 
   min_star = None 
   for cat_star in cat_stars:
      name,mag,ra,dec,new_cat_x,new_cat_y = cat_star

      dist = calc_dist((new_cat_x, new_cat_y), (ix,iy))
      if dist < min_dist and mag < 4:
         #print("DIST:", dist, cat_star)
         min_dist = dist
         min_star = cat_star
   name,mag,ra,dec,new_cat_x,new_cat_y = min_star
   px_dist = 0
   #cat_image_star = ((name.decode("unicode_escape"),mag,ra,dec,new_cat_x,new_cat_y,ix,iy,intensity,min_dist,cp_file))
   cat_image_star = ((name,mag,ra,dec,new_cat_x,new_cat_y,ix,iy,intensity,min_dist,cp_file))
   return(cat_image_star)

   

def refit_arc_meteor(archive_file):
   show = 0
   max_err = 50
   am = load_json_file(archive_file)
   hd_vid = am['info']['hd_vid']
   calib = am['calib']
   cal_params = load_cal_params_from_arc(calib)
   cat_stars = flex_get_cat_stars(archive_file, archive_file, json_conf, cal_params )

   hd_frames,hd_color_frames,hd_subframes,sum_vals,max_vals = load_frames_fast(hd_vid, json_conf, 0, 0, [], 1,[])
   frame = hd_frames[0]
   cframe = hd_color_frames[0]

   image_stars = get_image_stars(archive_file,frame, show=1)
   cat_image_stars = [] 

   res_err = []
   for star in image_stars:
      print("STAR:", star)
      best_star = find_best_cat_stars(cat_stars, star[0], star[1], frame, archive_file)
      if best_star[9] < max_err :
         res_err.append(best_star[9])

   std_err = float(np.std(res_err))
   med_err = float(np.median(res_err))
   print("MED ERR / STD DEV:", med_err, std_err)
   ac_err = med_err + std_err 

   for star in image_stars:
      #print("STAR:", star)
      best_star = find_best_cat_stars(cat_stars, star[0], star[1], frame, archive_file)
      #print("BEST:", best_star)
      if best_star[9] <  ac_err * 1.1:
         cv2.line(frame, (star[0], star[1]), (int(best_star[4]), int(best_star[5])), (128,128,128), 1) 
         cat_image_stars.append(best_star)
   if show == 1:
      cv2.imshow('pepe', frame)
      cv2.waitKey(70)

   this_poly = np.zeros(shape=(4,), dtype=np.float64)
   cal_params['cat_image_stars'] = cat_image_stars
   res = scipy.optimize.minimize(reduce_fov_pos, this_poly, args=( cal_params,archive_file,frame,json_conf, cat_image_stars,1,show), method='Nelder-Mead')
   print(res)
   fov_pos_poly = res['x']
   fov_pos_fun = res['fun']
   cal_params['x_poly'] = calib['device']['poly']['x']
   cal_params['y_poly'] = calib['device']['poly']['y']
   cal_params['fov_pos_poly'] = fov_pos_poly.tolist()
   cal_params['fov_pos_fun'] = fov_pos_fun

   cal_params['center_az'] = float(cal_params['orig_az_center']) + float(fov_pos_poly[0] )
   cal_params['center_el'] = float(cal_params['orig_el_center']) + float(fov_pos_poly[1] )
   cal_params['position_angle'] = float(cal_params['position_angle']) + float(fov_pos_poly[2] )
   cal_params['pixscale'] = float(cal_params['orig_pixscale']) + float(fov_pos_poly[3] )
   cal_params['orig_pos_angle'] = float(cal_params['position_angle']) + float(fov_pos_poly[2] )
   cal_params['orig_pixscale'] = float(cal_params['orig_pixscale']) + float(fov_pos_poly[3] )

   fov_pos_poly = np.zeros(shape=(4,), dtype=np.float64)
   final_res = reduce_fov_pos(fov_pos_poly, cal_params,archive_file,frame,json_conf, cat_image_stars,0,show)
   cal_params['total_res_px'] = final_res
   print("FINAL RES:", final_res)


   rah,dech = AzEltoRADec(cal_params['center_az'],cal_params['center_el'],archive_file,cal_params,json_conf)
   rah = str(rah).replace(":", " ")
   dech = str(dech).replace(":", " ")
   ra_center,dec_center = HMS2deg(str(rah),str(dech))
   cal_params['ra_center'] = ra_center
   cal_params['dec_center'] = dec_center
   cal_params['fov_fit'] = 1
   calib = format_calib(archive_file, cal_params, archive_file)
   am['calib'] = calib
   save_json_file(archive_file, am)
   print(archive_file)


   
def load_cal_params_from_arc(calib):
   print(calib)
   cal_params = {}
   cal_params['device_lat'] = calib['device']['lat']
   cal_params['device_lng'] = calib['device']['lng']
   cal_params['device_alt'] = calib['device']['alt']
   cal_params['orig_ra_center'] = calib['device']['center']['ra']
   cal_params['orig_dec_center'] = calib['device']['center']['dec']
   cal_params['orig_az_center'] = calib['device']['center']['az']
   cal_params['orig_el_center'] = calib['device']['center']['el']
   cal_params['orig_pos_ang'] = calib['device']['angle']
   cal_params['orig_pixscale'] = calib['device']['scale_px']
   cal_params['ra_center'] = calib['device']['center']['ra']
   cal_params['dec_center'] = calib['device']['center']['dec']
   cal_params['az_center'] = calib['device']['center']['az']
   cal_params['el_center'] = calib['device']['center']['el']
   cal_params['center_az'] = calib['device']['center']['az']
   cal_params['center_el'] = calib['device']['center']['el']
   cal_params['position_angle'] = calib['device']['angle']
   cal_params['pixscale'] = calib['device']['scale_px']
   cal_params['imagew'] = calib['img_dim'][0]
   cal_params['imageh'] = calib['img_dim'][1]

   cal_params['pixscale'] = calib['device']['scale_px']
   cal_params['x_poly'] = calib['device']['poly']['x']
   cal_params['y_poly'] = calib['device']['poly']['y']
   cal_params['x_poly_fwd'] = calib['device']['poly']['x_fwd']
   cal_params['y_poly_fwd'] = calib['device']['poly']['y_fwd']
   return(cal_params)


def apply_calib(obj ):
   print("CAL:", obj['hd_trim'])
   print("CAL:", obj['trim_clip'])
   if obj['hd_trim'] != 0:
      if cfe(obj['hd_trim']) == 1:   
         hd_frames,hd_color_frames,hd_subframes,sum_vals,max_vals = load_frames_fast(obj['hd_trim'], json_conf, 0, 0, [], 0,[])
         print("HD FRAMES:", len(hd_frames))
      elif "/mnt/ams2/HD/" in obj['hd_trim']:
         fl = obj['hd_trim'].split("/")[-1]
         m_date = fl[0:10]
         print("NEED TO UPDATE THE FILE PLEASE!", m_date, fl)
         obj['hd_trim'] = obj['hd_trim'].replace("/mnt/ams2/HD/", "/mnt/ams2/meteors/" + m_date + "/" )
         hd_frames,hd_color_frames,hd_subframes,sum_vals,max_vals = load_frames_fast(obj['hd_trim'], json_conf, 0, 0, [], 0,[])
   else:
      hd_frames,hd_color_frames,hd_subframes,sum_vals,max_vals = load_frames_fast(obj['trim_clip'], json_conf, 0, 0, [], 0,[])
      print("SD FRAMES:", len(hd_frames))

   frame = hd_frames[0]
   frame = cv2.resize(frame, (1920,1080))

   # find best free cal files
   best_cal_files = get_best_cal_file(obj['trim_clip'])
   cal_params_file = best_cal_files[0][0]
   print("BEST CAL FILE:", cal_params_file)

   # find last_best_calib
   last_best_calibs = find_last_best_calib(obj['hd_trim'])
   print("Last Best Calib:", last_best_calibs)
   if len(last_best_calibs) > 0:
      calib = load_json_file(last_best_calibs[0][0])
      calib['stars'] = []
      cal_params = calib_to_calparams(calib, obj['hd_trim'])
   else:
      cal_params = load_json_file(cal_params_file)
   cal_params['device_lat'] = json_conf['site']['device_lat']
   cal_params['device_lng'] = json_conf['site']['device_lng']
   cal_params['device_alt'] = json_conf['site']['device_alt']
   cal_params['orig_ra_center'] = cal_params['ra_center']
   cal_params['orig_dec_center'] = cal_params['dec_center']

   cal_params['orig_az_center'] = cal_params['center_az']
   cal_params['orig_el_center'] = cal_params['center_el']
   cal_params['orig_pos_ang'] = cal_params['position_angle']
   cal_params['orig_pixscale'] = cal_params['pixscale']

   cat_stars = flex_get_cat_stars(obj['trim_clip'], cal_params_file, json_conf, cal_params )
   #cat_image_stars = get_cat_image_stars(cat_stars, frame, cal_params_file)
   archive_file = obj['hd_trim']
   image_stars = get_image_stars(archive_file,frame, show=1)
   cat_image_stars = [] 
   used_cat_stars = {}
   used_img_stars = {}
   for star in image_stars:
      print("STAR:", star)
      best_star = find_best_cat_stars(cat_stars, star[0], star[1], frame, archive_file)
      print("BEST:", best_star)
      istar_key = str(star[0]) + str(star[1])
      cstar_key = str(best_star[4]) + str(best_star[5])
      if istar_key not in used_img_stars and cstar_key not in used_cat_stars:
         cv2.line(frame, (star[0], star[1]), (int(best_star[4]), int(best_star[5])), (128,128,128), 1) 
         cat_image_stars.append(best_star)
         used_img_stars[istar_key] = 1
         used_cat_stars[cstar_key] = 1



   if len(cat_image_stars) > 7:
      this_poly = np.zeros(shape=(4,), dtype=np.float64)

      start_res = reduce_fov_pos(this_poly, cal_params, obj['hd_trim'],frame,json_conf, cat_image_stars,0,show)
      cal_params_orig = cal_params.copy()
      res = scipy.optimize.minimize(reduce_fov_pos, this_poly, args=( cal_params,obj['hd_trim'],frame,json_conf, cat_image_stars,1,show), method='Nelder-Mead')

      fov_pos_poly = res['x']
      fov_pos_fun = res['fun']
      cal_params['x_poly'] = cal_params_orig['x_poly']
      cal_params['y_poly'] = cal_params_orig['y_poly']
      final_res = reduce_fov_pos(fov_pos_poly, cal_params,obj['hd_trim'],frame,json_conf, cat_image_stars,0,show)
      print("FINAL RES:", final_res)
      cal_params['fov_pos_poly'] = fov_pos_poly.tolist()
      cal_params['fov_pos_fun'] = fov_pos_fun
      cal_params['total_res_px'] = final_res

      cal_params['center_az'] = float(cal_params['orig_az_center']) + float(fov_pos_poly[0] )
      cal_params['center_el'] = float(cal_params['orig_el_center']) + float(fov_pos_poly[1] )
      cal_params['position_angle'] = float(cal_params['position_angle']) + float(fov_pos_poly[2] )

      rah,dech = AzEltoRADec(cal_params['center_az'],cal_params['center_el'],obj['hd_trim'],cal_params,json_conf)
      rah = str(rah).replace(":", " ")
      dech = str(dech).replace(":", " ")
      ra_center,dec_center = HMS2deg(str(rah),str(dech))
      cal_params['ra_center'] = ra_center
      cal_params['dec_center'] = dec_center
      cal_params['fov_fit'] = 1
      close_stars = []

      cat_image_stars = get_cat_image_stars(cat_stars, frame,cal_params_file)

   cal_params['cat_image_stars'] = cat_image_stars

   calib = format_calib(obj['trim_clip'], cal_params, cal_params_file)
   
   return(calib, cal_params)

def calib_to_calparams(calib, json_file ):
   cal_params = {}
   cal_params['x_poly'] = calib['device']['poly']['x'] 
   cal_params['y_poly'] = calib['device']['poly']['y'] 
   cal_params['y_poly_fwd'] = calib['device']['poly']['y_fwd'] 
   cal_params['x_poly_fwd'] = calib['device']['poly']['x_fwd'] 
   cal_params['center_ra'] = calib['device']['center']['ra'] 
   cal_params['center_dec'] = calib['device']['center']['dec'] 
   cal_params['ra_center'] = calib['device']['center']['ra'] 
   cal_params['dec_center'] = calib['device']['center']['dec'] 
   cal_params['center_az'] = calib['device']['center']['az'] 
   cal_params['center_el'] = calib['device']['center']['el'] 
   cal_params['pixscale'] = calib['device']['scale_px']
   cal_params['orig_pixscale'] = calib['device']['scale_px']
   cal_params['orig_pos_ang'] = calib['device']['angle']
   cal_params['orig_center_az'] = calib['device']['center']['az'] 
   cal_params['orig_center_el'] = calib['device']['center']['el'] 
   cal_params['orig_az_center'] = calib['device']['center']['az'] 
   cal_params['orig_el_center'] = calib['device']['center']['el'] 
   cal_params['position_angle'] = calib['device']['angle']
   cal_params['imagew'] = calib['img_dim'][0]
   cal_params['imageh'] = calib['img_dim'][1]
   cat_image_stars = []

   for star in calib['stars']:
      if "intensity" not in star:
         star['intensity'] = 0
      cat_star = (star['name'],star['mag'],star['ra'],star['dec'],star['cat_und_pos'][0],star['cat_und_pos'][1],star['i_pos'][0],star['i_pos'][1],star['intensity'], star['dist_px'],json_file)
      cat_image_stars.append(cat_star)
   cal_params['cat_image_stars'] = cat_image_stars
   return(cal_params)


def batch_fit_arc_file(date):
   year, mon, day = date.split("_")
   files = glob.glob("/mnt/ams2/meteor_archive/" + json_conf['site']['ams_id'] + "/METEOR/" + year + "/" + mon + "/" + day + "/*.json" )
   for file in files:
      cmd = "./flex-detect.py faf " + file
      print(cmd)
      os.system(cmd)

def remove_bad_stars(stars):
   new_stars = []
   err = []
   for star in stars:
      print(star)
      err.append(star['dist_px'])

   avg_err = np.mean(err)
   med_err = np.median(err)
   print("AVG STAR ERR:", avg_err)
   print("MEDIAN STAR ERR:", med_err)
   for star in stars:
      if star['dist_px'] < med_err * 7 or star['dist_px'] < 2:
         new_stars.append(star)
   return(new_stars)

def fit_arc_file(json_file):
   json_data = load_json_file(json_file)
   (hd_datetime, cam, sd_date, sd_y, sd_m, sd_d, sd_h, sd_M, sd_s) = convert_filename_to_date_cam(json_file)
   station = json_file.split("/")[4]
   master_lens_file = "/mnt/ams2/meteor_archive/" + station + "/CAL/master_lens_model/master_cal_file_" + cam + ".json"
   print("MASTER:", master_lens_file)

   hd_file = json_file.replace(".json", "-HD.mp4")
   hd_frames,hd_color_frames,hd_subframes,sum_vals,max_vals = load_frames_fast(hd_file, json_conf, 0, 0, [], 0,[])
   frame = hd_frames[0]

   calib = json_data['calib']

   last_best_calibs = find_last_best_calib(json_file)
   if len(last_best_calibs) > 0:
      last_best_calib = load_json_file(last_best_calibs[0][0])
      cal_params = calib_to_calparams(calib, json_file)
      calib['device'] = last_best_calib['device']

   calib['stars'] = remove_bad_stars(calib['stars'])
   print("YO")

   cal_params = calib_to_calparams(calib, json_file)

   orig = {}
   orig['center_az'] = cal_params['orig_az_center']
   orig['center_el'] = cal_params['orig_el_center']
   orig['pos_ang'] = cal_params['orig_pos_ang']
   orig['pixscale'] = cal_params['orig_pixscale']


   cat_image_stars = cal_params['cat_image_stars']

   if cfe(master_lens_file) == 1:
      mld = load_json_file(master_lens_file)
      cal_params['x_poly'] = mld['x_poly']
      cal_params['y_poly'] = mld['y_poly']
      cal_params['y_poly_fwd'] = mld['y_poly_fwd']
      cal_params['x_poly_fwd'] = mld['x_poly_fwd']
   print(cal_params)




   if True:
      this_poly = np.zeros(shape=(4,), dtype=np.float64)

      print("YOYO", show)
      start_res = reduce_fov_pos(this_poly, cal_params, json_file,frame,json_conf, cat_image_stars,0,show)
      print("YOYOyo")
      cal_params_orig = cal_params.copy()
      res = scipy.optimize.minimize(reduce_fov_pos, this_poly, args=( cal_params,json_file,frame,json_conf, cat_image_stars,1,show), method='Nelder-Mead')

      fov_pos_poly = res['x']
      fov_pos_fun = res['fun']
      cal_params['x_poly'] = cal_params_orig['x_poly']
      cal_params['y_poly'] = cal_params_orig['y_poly']

      cal_params['fov_pos_poly'] = fov_pos_poly.tolist()
      cal_params['fov_pos_fun'] = fov_pos_fun



      cal_params['center_az'] = float(cal_params['orig_az_center']) + float(fov_pos_poly[0] )
      cal_params['center_el'] = float(cal_params['orig_el_center']) + float(fov_pos_poly[1] )

      cal_params['position_angle'] = float(cal_params['position_angle']) + float(fov_pos_poly[2] )
      #cal_params['orig_pos_angle'] = float(cal_params['orig_pos_ang']) + float(fov_pos_poly[2] )

      cal_params['pixscale'] = float(cal_params['orig_pixscale']) + float(fov_pos_poly[3] )
      #cal_params['orig_pixscale'] = float(cal_params['orig_pixscale']) + float(fov_pos_poly[3] )



      rah,dech = AzEltoRADec(cal_params['center_az'],cal_params['center_el'],json_file,cal_params,json_conf)
      rah = str(rah).replace(":", " ")
      dech = str(dech).replace(":", " ")
      ra_center,dec_center = HMS2deg(str(rah),str(dech))
      cal_params['ra_center'] = ra_center
      cal_params['dec_center'] = dec_center
      cal_params['fov_fit'] = 1

      this_poly = np.zeros(shape=(4,), dtype=np.float64)
      #final_res = reduce_fov_pos(this_poly, cal_params,json_file,frame,json_conf, cat_image_stars,0,show)
      #print("FINAL RES:", final_res)

      cal_params['total_res_px'] = fov_pos_fun

      #cat_image_stars = get_cat_image_stars(cat_stars, frame,cal_params_file)

   calib = format_calib(json_file, cal_params, json_file)
   new_stars = update_arc_cat_stars(calib,json_file)
   print(new_stars)
   calib['stars'] = new_stars
   save_json_file("test.json", new_stars)


   json_data['calib'] = calib
   save_json_file(json_file, json_data)
   print("FOV POLY:", fov_pos_poly)
   print("ORIG:", orig)
   print("FINAL", calib['device']) 
   if len(calib['stars']) > 15 and cal_params['total_res_px'] < 2.4:
      last_best = calib
      del last_best['stars']
      lbf = json_file.split("/")[-1]
      last_best_file = "/mnt/ams2/meteor_archive/" + station + "/CAL/last_best/" + lbf
      save_json_file(last_best_file, last_best)

   print(json_file)

# Catalog Stars
def update_arc_cat_stars(calib, json_file):
   star_points = []
   cal_params = calib_to_calparams(calib, json_file)
   for star in calib['stars']:
      ix = star['i_pos'][0]
      iy = star['i_pos'][1]
      star_points.append((ix,iy))


   # Get the values from the form
   #hd_stack_file = form.getvalue("hd_stack_file")   # Stack
   #video_file = form.getvalue("video_file")         # Video file
   #meteor_red_file = form.getvalue("json_file")
   #hd_image = cv2.imread(hd_stack_file, 0)


   cat_stars = flex_get_cat_stars(json_file, json_file, json_conf, cal_params )


   my_close_stars = []
   cat_dist = []
   used_cat_stars = {}
   used_star_pos = {}

   if True:
      for ix,iy in star_points:
         close_stars = find_close_stars((ix,iy), cat_stars)

         if len(close_stars) == 1:
            name,mag,ra,dec,cat_x,cat_y,scx,scy,cat_star_dist = close_stars[0]
            #new_x, new_y, img_ra,img_dec, img_az, img_el = XYtoRADec(ix,iy,video_file,meteor_red['calib'])
            new_x, new_y, img_ra ,img_dec , img_az, img_el = XYtoRADec(ix,iy,json_file,cal_params,json_conf)
            new_star = {}

            new_star['name'] = name
            new_star['mag'] = mag
            new_star['ra'] = ra
            new_star['dec'] =  dec
            new_star['dist_px'] = cat_star_dist
            cat_dist.append(cat_star_dist)

            # The image x,y of the star (CIRCLE)
            new_star['i_pos'] = [ix,iy]
            # The lens distorted catalog x,y position of the star  (PLUS SIGN)
            new_star['cat_dist_pos'] = [new_x,new_y]
            # The undistorted catalog x,y position of the star  (SQUARE)
            new_star['cat_und_pos'] = [cat_x,cat_y]

            # distorted position should be the new_x, new_y and + symbol
            # only add if this star/position combo has not already be used
            used_star = 0
            this_rakey = str(ra) + str(dec)
            if this_rakey not in used_cat_stars:
               my_close_stars.append(new_star)
               used_cat_stars[this_rakey] = 1

   return(my_close_stars)

def find_last_best_calib(input_file):
   (f_datetime, cam_id, f_date_str,Y,M,D, H, MM, S) = better_parse_file_date(input_file)
   station_id = json_conf['site']['ams_id']
   matches = []
   cal_dir = "/mnt/ams2/meteor_archive/" + station_id + "/CAL/last_best/*.json"
   print(cal_dir)
   all_files = glob.glob(cal_dir)
   for file in all_files:
      if cam_id in file :
         el = file.split("/")
         fn = el[-1]
         cp = file 
         if cfe(cp) == 1:
            matches.append(cp)
         else:
            print("CP NOT FOUND!", cp)

   td_sorted_matches = []

   for match in matches:
      (t_datetime, cam_id, f_date_str,Y,M,D, H, MM, S) = better_parse_file_date(match)
      tdiff = abs((f_datetime-t_datetime).total_seconds())
      td_sorted_matches.append((match,f_date_str,tdiff))

   temp = sorted(td_sorted_matches, key=lambda x: x[2], reverse=False)

   return(temp)




def get_best_cal_file(input_file):
   #print("INPUT FILE", input_file)
   if "png" in input_file:
      input_file = input_file.replace(".png", ".mp4")
   (f_datetime, cam_id, f_date_str,Y,M,D, H, MM, S) = better_parse_file_date(input_file)

   # find all cal files from his cam for the same night
   matches = find_matching_cal_files(json_conf['site']['ams_id'], cam_id, f_datetime)
   #print("MATCHED:", matches)
   if len(matches) > 0:
      return(matches)
   else:
      return(None)


def confirm_meteor(meteor_json_file):

   if "meteors" in meteor_json_file:
      old_scan = 1
   else:
      old_scan = 0 

   if old_scan == 0:
      video_file = meteor_json_file.replace("-meteor.json", ".mp4")
   else:
      video_file = meteor_json_file.replace(".json", ".mp4")
   orig_stack_file = meteor_json_file.replace("-meteor.json", "-stacked.png")
   print("CONFIRM:", video_file)
   (hd_datetime, cam, sd_date, sd_y, sd_m, sd_d, sd_h, sd_M, sd_s) = convert_filename_to_date_cam(video_file)

   masks = get_masks(cam, json_conf,0)

   meteor_date = sd_y + "_" + sd_m + "_" + sd_d
   sun_alt = find_sun_alt(hd_datetime)
   if sun_alt > -5:
      sun_up = 1
      print("SUN is up:", sun_alt)
   else:
      sun_up = 0
   
   meteor_objects = load_json_file(meteor_json_file)
   if old_scan == 1:
      mo = []
      if "flex_detect" in meteor_objects:
         mo.append(meteor_objects['flex_detect'])
      else:
         mo = quick_scan(video_file, 1)
      meteor_objects = mo
      print("METEOR OBJECTS:", len(meteor_objects))


   meteor_objects = objects_to_clips(meteor_objects)
   print("METEOR OBJECTS:", meteor_objects)

   # make trim clips for the possible meteors
   if old_scan == 0:
      if sun_up == 0:
         trim_clips, trim_starts, trim_ends,meteor_objects = make_trim_clips(meteor_objects, video_file)   
      else:
         trim_clips, trim_starts, trim_ends,meteor_objects = make_trim_clips(meteor_objects, video_file)   
         print("Process daytime file instead.", trim_clips)
   else:
      trim_clips = []
      trim_starts = []
      for mo in meteor_objects:
         print("MO:", mo)
         tc = mo['trim_clip'].replace("/mnt/ams2/CAMS/queue/", "/mnt/ams2/meteors/" + meteor_date + "/" )
         trim_clips.append(tc)
         xxx = video_file.split("-")
         trim_num = xxx[-1].replace("trim", "")
         trim_num = trim_num.replace(".mp4", "")
         trim_starts.append(int(trim_num))


   print("TRIM CLIPS!", trim_clips)
   print("TRIM METEORS!", len(meteor_objects))

   for mo in meteor_objects:
      print(mo)
   motion_meteors = []
   no_motion_meteors = []
   tc = 0
   for trim_clip in trim_clips:
      motion_objects,meteor_frames = detect_meteor_in_clip(trim_clip , None, trim_starts[tc])
      for mid in motion_objects:
         mobject = motion_objects[mid]
         if mobject['report']['meteor_yn'] == 'Y':
            motion_meteors.append(mobject)
         else:
            no_motion_meteors.append(mobject)
         
      tc = tc + 1


   print("Total motion meteors:", len(motion_meteors))
   for mm in motion_meteors:
      poly_fit(mm) 
   print("Total non motion meteors:", len(no_motion_meteors))
   for mo in no_motion_meteors:
      print(mo['report']['bad_items'])







   if len(motion_meteors) == 0:
      reject_meteor(meteor_json_file) 
      return()
   meteor_objects = motion_meteors

 
   old_meteor_dir = "/mnt/ams2/meteors/" + meteor_date + "/"
   oc =0
   old_meteor_dir = "/mnt/ams2/meteors/" + meteor_date + "/"
   for obj in meteor_objects:
      start = mm['ofns'][0]
      end = mm['ofns'][-1]
      # sync HD
      df = int ((end - start) / 25)
      hd_file, hd_trim,time_diff_sec, dur = find_hd_file_new(video_file, start, df, 1)
      print("START END:", start, end, df)
      print("HD TRIM:", hd_trim)
      if hd_trim is not None:
         print("HD SYNC:", hd_file, hd_trim, time_diff_sec, dur, df)
         # Make the HD stack file too.  And then sync the HD to SD video file.
         obj['hd_trim'] = hd_trim
         obj['hd_video_file'] = hd_file
         if hd_trim != 0 and cfe(hd_trim) == 1:
            hd_crop, crop_box = crop_hd(obj, meteor_frames[0])
            hd_crop_objects,hd_crop_frames = detect_meteor_in_clip(hd_crop, None, start, crop_box[0], crop_box[1])
            #refine_points(hd_crop, hd_crop_frames )
            obj['hd_crop_file'] = hd_crop
            obj['crop_box'] = crop_box 
            obj['hd_crop_objects'] = hd_crop_objects
            os.system("mv " + hd_trim + " " + old_meteor_dir)
         else:
            obj['hd_trim'] = 0
            obj['hd_video_file'] = 0

         print("REAL METEORS:", mm)
         process_meteor_files(obj, meteor_date, video_file, old_scan)
         oc = oc + 1

def process_meteor_files(obj, meteor_date, video_file, old_scan ):
   # save object to old style archive and then move the trim file and copy the stack file to the archive as well
   # move the new json dedtect file someplace else and then do the same for the new archive style
   trim_clip = obj['trim_clip']
   cx1, cy1,cx2,cy2= minmax_xy(obj)

   old_meteor_dir = "/mnt/ams2/meteors/" + meteor_date + "/"
   if cfe(old_meteor_dir, 1) == 0:
      os.system("mkdir " + old_meteor_dir)
   mf = trim_clip.split("/")[-1]
   mf = mf.replace(".mp4", ".json")
   meteor_json_file = video_file.replace(".mp4", "-meteor.json")
   old_meteor_json_file = old_meteor_dir + mf
   old_meteor_json_file = old_meteor_json_file.replace(".mp4", ".json")
   old_meteor_stack_file = old_meteor_json_file.replace(".json", "-stacked.png")
   orig_stack_file = video_file.replace(".mp4", "-stacked.png")

   if old_scan == 0:
      print("Save old meteor json", old_meteor_json_file)
      proc_dir = "/mnt/ams2/SD/proc2/" + meteor_date + "/" 
      # mv the trim video
      cmd = "mv " + trim_clip + " " + old_meteor_dir
      print(cmd)
      os.system(cmd)
      # copy the stack file

      cmd = "cp " + orig_stack_file + " " + proc_dir + "/images/"
      os.system(cmd)
      print(cmd)
      cmd = "mv " + orig_stack_file + " " + old_meteor_stack_file
      print(cmd)
      os.system(cmd)
      thumb(old_meteor_stack_file)
      stack_img = cv2.imread(old_meteor_stack_file)
      old_meteor_stack_obj_file = old_meteor_stack_file.replace(".png", "-obj.png")
      cv2.rectangle(stack_img, (cx1, cy1), (cx2, cy2), (255,255,255), 1, cv2.LINE_AA)
      cv2.imwrite(old_meteor_stack_obj_file, stack_img)
      thumb(old_meteor_stack_obj_file)

      # remove original meteor object file?
      cmd = "mv " + meteor_json_file + " /mnt/ams2/DEBUG/"
      print(cmd)
      os.system(cmd)
      one_min_file = meteor_json_file.replace("-meteor.json", ".mp4")
      if cfe(proc_dir, 1) == 0:
         os.system("mkdir " + proc_dir)
      cmd = "mv " + one_min_file + " " + proc_dir
      os.system(cmd)
      print(cmd)
      if old_scan == 0:
         save_old_style_meteor_json(old_meteor_json_file, obj, trim_clip )
   print("Meteor Files Processed and saved!", old_meteor_json_file)


def find_leading_edge(x_dir_mod, y_dir_mod,x,y,w,h,frame):
   if x_dir_mod == 1:
      leading_x = x
   else:
      leading_x = x + w
   if y_dir_mod == 1:
      leading_y = y
   else:
      leading_y =  y + h

   if True:
      leading_edge_x_size = int(w / 2)
      leading_edge_y_size = int(h / 2)

      le_x1 = leading_x
      le_x2 = leading_x + (x_dir_mod*leading_edge_x_size)
      le_y1 = leading_y
      le_y2 = leading_y + (y_dir_mod*leading_edge_y_size)
      tm_y = sorted([le_y1,le_y2])
      tm_x = sorted([le_x1,le_x2])
      le_x1 = tm_x[0]
      le_x2 = tm_x[1]
      le_y1 = tm_y[0]
      le_y2 = tm_y[1]

      le_cnt = frame[le_y1:le_y2,le_x1:le_x2]
      blur_frame = cv2.GaussianBlur(le_cnt, (7, 7), 0)
      min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(blur_frame)

      le_x = mx + (le_x1)
      le_y = my + (le_y1)
      cv2.circle(frame,(leading_x,leading_y), 10, (0,255,0), 1)
      cv2.circle(frame,(le_x,le_y), 5, (255,0,0), 1)
      #cv2.rectangle(frame, (x, y), (x+w, y+h), (255,255,255), 1, cv2.LINE_AA)
      cv2.rectangle(frame, (leading_x, leading_y), (leading_x+(x_dir_mod*leading_edge_x_size), leading_y+(y_dir_mod*leading_edge_y_size)), (255,255,255), 1, cv2.LINE_AA)





   return(le_x, le_y)
        
def refine_points_old(hd_crop, frames = None, color_frames = None):
   scx = 10
   scy = 10
   #hd_x1, hd_y1, hd_cw, hd_ch = crop_box
   if frames is None: 
      frames,color_frames,subframes,sum_vals,max_vals = load_frames_fast(hd_crop, json_conf, 0, 0, [], 0,[])
   fn = 0

   motion_objects,meteor_frames = detect_meteor_in_clip(hd_crop, frames, 0)
   meteors = {}
   for obj_id in motion_objects:
      obj = motion_objects[obj_id]
      if obj['report']['meteor_yn'] == "Y":
         meteors[obj_id] = obj
   motion_objects = meteors

   first_frame = frames[0]
   for obj in motion_objects:
      if "center_xs" not in motion_objects[obj]:
         motion_objects[obj]['crop_center_xs'] = []
         motion_objects[obj]['crop_center_ys'] = []
      for i in range(0, len(motion_objects[obj]['ofns'])):
         fn = motion_objects[obj]['ofns'][i]
         x = motion_objects[obj]['oxs'][i] - int(motion_objects[obj]['ows'][i]/2)
         y = motion_objects[obj]['oys'][i] - int(motion_objects[obj]['ohs'][i]/2) 
         w = motion_objects[obj]['ows'][i] 
         h = motion_objects[obj]['ohs'][i] 
         if color_frames is not None:
            show_frame = color_frames[fn].copy()
         else:
            show_frame = frames[fn].copy()
         frame = frames[fn]
         desc = str(fn) 

         cx1,cy1,cx2,cy2 = bound_cnt(x,y,frames[0].shape[1],frames[0].shape[0], 20)

         crop_img = frame[cy1:cy2,cx1:cx2]
         crop_bg = first_frame[cy1:cy2,cx1:cx2]
         crop_img_big = cv2.resize(crop_img, (0,0),fx=scx, fy=scy)
         crop_sub = cv2.subtract(crop_img,crop_bg)
         crop_sub_big = cv2.resize(crop_sub, (0,0),fx=scx, fy=scy)
         #min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(crop_sub_big)
         min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(crop_img_big)
         med_val = np.median(crop_img_big)
         px_diff = max_val - med_val
         
         thresh = med_val + (px_diff / 3)
         if thresh < med_val:
            thresh = med_val + 10 

         cnts,rects = find_contours_in_frame(crop_img_big, thresh)
         if len(cnts) > 1:
            cnts = merge_contours(cnts)
         for cnt in cnts:
            x, y, w, h = cnt 
            cv2.rectangle(crop_sub_big, (x, y), (x+w, x+h), (128,129,128), 1, cv2.LINE_AA)
            cv2.rectangle(crop_img_big, (x, y), (x+w, x+h), (128,129,128), 1, cv2.LINE_AA)
            main_x = int(((x+(w/2))/scx) + cx1)
            main_y = int(((y+(h/2))/scy) + cy1)
            mx1,my1,mx2,my2 = bound_cnt(main_x,main_y,show_frame.shape[1],show_frame.shape[0], 10)
            motion_objects[obj]['crop_center_xs'].append(main_x)
            motion_objects[obj]['crop_center_ys'].append(main_y) 


            cv2.rectangle(show_frame, (mx1, my1), (mx2, my2), (0,0,128), 1, cv2.LINE_AA)
            




   # Ok now that we have at least refined the main object's center, lets re-crop the frames around that 
   # and find the leading edge!
   if show == 1:
      cv2.destroyAllWindows()

   print(motion_objects)
   exit()

   for obj in motion_objects:
      x_dir_mod,y_dir_mod = meteor_dir(motion_objects[obj]['oxs'][0], motion_objects[obj]['oys'][0], motion_objects[obj]['oxs'][-1], motion_objects[obj]['oys'][-1])
      for i in range(0, len(motion_objects[obj]['ofns'])):
         fn = motion_objects[obj]['ofns'][i]
         x = motion_objects[obj]['oxs'][i] - int(motion_objects[obj]['ows'][i]/2)
         y = motion_objects[obj]['oys'][i] - int(motion_objects[obj]['ohs'][i]/2)
         w = motion_objects[obj]['ows'][i]
         h = motion_objects[obj]['ohs'][i]
         if "crop_center_xs" not in motion_objects[obj]:
            print("NO CENTER X", motion_objects[obj])
            exit() 
         center_x = motion_objects[obj]['crop_center_xs'][i]
         center_y = motion_objects[obj]['crop_center_ys'][i]
         if color_frames is not None:
            show_frame = color_frames[fn].copy()
         else:
            show_frame = frames[fn].copy()
         frame = frames[fn].copy()
         if color_frames is not None: 
            color_frame = color_frames[fn].copy()
         else:
            color_frame = frames[fn].copy()
         desc = str(fn)

         cx1,cy1,cx2,cy2 = bound_cnt(center_x,center_y,frames[0].shape[1],frames[0].shape[0], 10)
         crop_img = frame[cy1:cy2,cx1:cx2]
         crop_img_cl = color_frame[cy1:cy2,cx1:cx2]
         crop_img_big = cv2.resize(crop_img, (0,0),fx=scx, fy=scy)
         crop_img_big_cl = cv2.resize(crop_img_cl, (0,0),fx=scx, fy=scy)

         min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(crop_img_big)
         med_val = np.median(crop_img_big)
         px_diff = max_val - med_val

         thresh = med_val + (px_diff / 3)
         if thresh < med_val:
            thresh = med_val + 10

         cnts,rects = find_contours_in_frame(crop_img_big, thresh)
         if len(cnts) > 0:
            x,y,w,h = cnts[0]

            lx, ly = find_leading_edge(x_dir_mod, y_dir_mod,x,y,w,h,crop_img_big)
            lx = int(lx/scx) + cx1
            ly = int(ly/scy) + cy1
            if "leading_xs" not in motion_objects[obj]:
               motion_objects[obj]['leading_xs'] = []
               motion_objects[obj]['leading_ys'] = []
            motion_objects[obj]['leading_xs'].append(lx)
            motion_objects[obj]['leading_ys'].append(ly)


         cv2.circle(crop_img_big_cl,(lx,ly), 1, (255,255,255), 1)

   for obj in motion_objects:
      motion_objects[obj] = remove_bad_frames(motion_objects[obj])
      print("REFINED OBJECT!:", motion_objects[obj])

   for obj in motion_objects:
      xobj = motion_objects[obj]
      for i in range(0, len(xobj['ofns'])):
         fn = xobj['ofns'][i]
         lx = xobj['leading_xs'][i]
         ly = xobj['leading_ys'][i]
         ly = xobj['leading_ys'][i]
         if color_frames is not None:
            show_frame = color_frames[fn].copy()
         else:
            show_frame = frames[fn].copy()
         cv2.circle(show_frame,(lx,ly), 1, (0,0,255), 1)
         if show == 1:
            cv2.imshow("REFINE", show_frame)
            cv2.waitKey(70)

   return(motion_objects)

def calc_leg_segs(xobj):
   dist_from_start = []
   line_segs = []
   x_segs = []
   ms = []
   bs = []
   fx, fy = xobj['oxs'][0],xobj['oys'][0]
   # find distance from start point for each frame
   # turn that into seg_dist for each frame
   for i in range(0, len(xobj['ofns'])):
      tx = xobj['oxs'][i]
      ty = xobj['oys'][i]
      dist = calc_dist((fx,fy),(tx,ty))
      dist_from_start.append(dist)
      if i > 0 and i < len(xobj['ofns']):
         tm,tb = best_fit_slope_and_intercept([fx,tx],[fy,ty])
         seg_len = dist_from_start[i] - dist_from_start[i-1]
         line_segs.append(seg_len)
         x_segs.append(xobj['oxs'][i-1] - tx)
         ms.append(tm)
         bs.append(tb)

      else:
         line_segs.append(0)
         ms.append(0)
         bs.append(0)
   xobj['dist_from_start'] = dist_from_start
   xobj['line_segs'] = line_segs
   xobj['x_segs'] = x_segs
   xobj['ms'] = ms 
   xobj['bs'] = bs
   #del(xobj['crop_center_xs'])
   #del(xobj['crop_center_ys'])



   return(xobj)


def remove_bad_frames(obj):
   # frame bad if the intensity is negative really low 
   # frame bad if the line seg is way off from the med_seg_len
   print("REMOVE BAD!" )
   obj = calc_leg_segs(obj)
   new_fns, new_xs, new_ys, new_ws, new_hs, new_ints, new_lxs, new_lys,new_line_segs,new_dist_from_start = [],[],[],[],[],[],[],[],[],[]
   med_seg = np.median(obj['line_segs'])
   for i in range (0, len(obj['ofns'])-1):
      fn = obj['ofns'][i]
      x = obj['oxs'][i]
      y = obj['oys'][i]
      w = obj['ows'][i]
      h = obj['ohs'][i]
      ints = obj['oint'][i]
      lx = obj['leading_xs'][i]
      ly = obj['leading_ys'][i]
      line_seg = obj['line_segs'][i]
      dist_from_start = obj['dist_from_start'][i]
      if abs(line_seg - med_seg) > 2 or line_seg <= 0:
         bf = 1
      else:
         new_fns.append(fn)
         new_xs.append(x)
         new_ys.append(y)
         new_ws.append(w)
         new_hs.append(h)
         new_ints.append(ints)
         new_lxs.append(lx)
         new_lys.append(ly)
         new_line_segs.append(line_seg)
         new_dist_from_start.append(dist_from_start)
   obj['ofns'] = new_fns
   obj['oxs'] = new_xs 
   obj['oys'] = new_ys
   obj['ows'] = new_ws
   obj['ohs'] = new_hs
   obj['oint'] = new_ints
   obj['leading_xs'] = new_lxs
   obj['leading_ys'] = new_lys
   obj['line_segs'] = new_line_segs
   obj['dist_from_start'] = new_dist_from_start
   obj = analyze_object(obj)
      
   return(obj)
     
      
   

def crop_hd(obj, frame):
   hd_trim = obj['hd_trim']
   min_x, min_y,max_x,max_y = minmax_xy(obj)
   fx = int((min_x + max_x) / 2)
   fy = int((min_y + max_y) / 2)
   if max_x - min_x < 100 or max_y - min_y < 100:
      cx1,cy1,cx2,cy2= bound_cnt(fx,fy,frame.shape[1],frame.shape[0], 100)
   else:
      cx1,cy1,cx2,cy2= bound_cnt(fx,fy,frame.shape[1],frame.shape[0], 200)
   w = cx2 - cx1
   h = cy2 - cy1

   scale_x = 1920 / frame.shape[1]  
   scale_y = 1080 / frame.shape[0]  
   hd_x = int(cx1 * scale_x)
   hd_y = int(cy1 * scale_y)
   w = int(w * scale_x)
   h = int(h * scale_y)
 

   crop = "crop=" + str(w) + ":" + str(h) + ":" + str(hd_x) + ":" + str(hd_y)
   #print("CROP: ", crop)
   crop_out_file = hd_trim.replace(".mp4", "-crop.mp4")
   cmd = "/usr/bin/ffmpeg -y -i " + hd_trim + " -filter:v \"" + crop + "\" " + crop_out_file + " >/dev/null 2>&1"
   print(cmd)
   os.system(cmd)
   return(crop_out_file, (hd_x, hd_y, w, h))

    

def make_trim_clips(meteor_objects, video_file):
   trim_clips = []
   trim_starts = []
   trim_ends = []
   new_objs = []
   for obj in meteor_objects:
      start = obj['ofns'][0] - 25
      if start < 0:
         start = 0
      end = obj['ofns'][-1] + 25
      if end > 1499:
         end = 1499
      #print(obj['ofns'])
      # Run deeper detection on clip
      trim_clip, trim_start, trim_end = make_trim_clip(video_file, start, end)
      obj['trim_clip'] = trim_clip
      obj['trim_start'] = trim_start
      obj['trim_end'] = trim_end
      trim_clips.append(trim_clip)
      trim_starts.append(trim_start)
      trim_ends.append(trim_end)
      new_objs.append(obj)
   return(trim_clips, trim_starts, trim_ends,new_objs)


def make_trim_clip(video_file, start, end):
   outfile = video_file.replace(".mp4", "-trim" + str(start) + ".mp4")
   cmd = "/usr/bin/ffmpeg -y -i " + video_file + " -vf select=\"between(n\," + str(start) + "\," + str(end) + "),setpts=PTS-STARTPTS\" " + outfile + " 2>&1 > /dev/null"
   if cfe(outfile) == 0:   
      print(cmd)
      os.system(cmd)
   return(outfile, start, end)

def scan_queue(cam):
   if cam != "a":
      wild = "*" + cam + ".mp4"
   else:
      wild = "*.mp4"
   queue_dir="/mnt/ams2/CAMS/queue/"
   files = sorted(glob.glob(queue_dir + wild ), reverse=True)
   fc = 0
   for video_file in files:
      stack_file = video_file.replace(".mp4", "-stacked.png")
      if cfe(stack_file) == 0 and "trim" not in video_file:
         quick_scan(video_file)
         #cmd = "./flex-detect.py qs " + video_file
         #print(cmd)
         #os.system(cmd)
         fc = fc + 1
      else:
         print("skipping")
   print("Finished scanning files", len(files))




def scan_old_meteor_dir(dir):
   files = glob.glob(dir + "*trim*.json" )
   print(dir + "*trim*.json" )
   print(files)
   for file in files:
      if "meteor.json" not in file and "fail.json" not in file and "reduced" not in file:
         print(file)
         jd = load_json_file(file)
         video_file = file.replace(".json", ".mp4")
         if cfe(video_file) == 1 and "archive_file" not in jd:
            debug(video_file)
         else:
            if cfe(jd['archive_file']) == 0:
               #quick_scan(video_file)
               debug(video_file)
            else:
               print("Done already.")

def find_clusters(points):

   data = np.array(points)
   data.reshape(-1, 1)
   db = DBSCAN(eps=10, min_samples=1).fit(data)
   labels = db.labels_
   return(labels)


def parse_file_data(input_file):
   el = input_file.split("/")
   fn = el[-1]
   try:
      good, bad = fn.split("-")
      ddd = good.split("_")
   except:
      good = fn.replace(".mp4", "")
      ddd = good.split("_")
   print("DDD", input_file, ddd)
   Y = ddd[0]
   M = ddd[1]
   D = ddd[2]
   H = ddd[3]
   MM = ddd[4]
   S = ddd[5]
   MS = ddd[6]
   CAM = ddd[7]
   extra = CAM.split("-")
   cam_id = extra[0]
   cam_id = cam_id.replace(".mp4", "")
   f_date_str = Y + "-" + M + "-" + D + " " + H + ":" + MM + ":" + S
   f_datetime = datetime.datetime.strptime(f_date_str, "%Y-%m-%d %H:%M:%S")
   return(f_datetime, cam_id, f_date_str,Y,M,D, H, MM, S)


def day_or_night(capture_date):

   device_lat = json_conf['site']['device_lat']
   device_lng = json_conf['site']['device_lng']

   obs = ephem.Observer()

   obs.pressure = 0
   obs.horizon = '-0:34'
   obs.lat = device_lat
   obs.lon = device_lng
   obs.date = capture_date

   sun = ephem.Sun()
   sun.compute(obs)

   (sun_alt, x,y) = str(sun.alt).split(":")

   saz = str(sun.az)
   (sun_az, x,y) = saz.split(":")
   if int(sun_alt) < 10:
      sun_status = "night"
   else:
      sun_status = "day"
   return(sun_status)


def convert_filename_to_date_cam(file):
   el = file.split("/")
   filename = el[-1]
   if "trim" in filename:
      filename, xxx = filename.split("-")[:2]
   filename = filename.replace(".mp4" ,"")

   data = filename.split("_")
   fy,fm,fd,fh,fmin,fs,fms,cam = data[:8]
   f_date_str = fy + "-" + fm + "-" + fd + " " + fh + ":" + fmin + ":" + fs
   f_datetime = datetime.datetime.strptime(f_date_str, "%Y-%m-%d %H:%M:%S")
   return(f_datetime, cam, f_date_str,fy,fm,fd, fh, fmin, fs)

def check_running():
   cmd = "ps -aux |grep \"process_data.py\" | grep -v grep"
   output = subprocess.check_output(cmd, shell=True).decode("utf-8")
   print(output)
   cmd = "ps -aux |grep \"process_data.py\" | grep -v grep | wc -l"
   output = subprocess.check_output(cmd, shell=True).decode("utf-8")
   output = int(output.replace("\n", ""))
   return(output)

def batch_quick():

   sd_video_dir = "/mnt/ams2/test/"

   #files = glob.glob(sd_video_dir + "/*SD.mp4")
   files = glob.glob(sd_video_dir + "/*.mp4")
   cc = 0
   files = sorted(files, reverse=True)
   for file in sorted(files, reverse=True):
      png = file.replace(".mp4", "-stacked.png")
      if cfe(png) == 0:
         (f_datetime, cam_id, f_date_str,fy,fmin,fd,fh, fm, fs) = parse_file_data(file)
         sun_status = day_or_night(f_date_str)
         cur_time = int(time.time())
         st = os.stat(file)
         size = st.st_size
         mtime = st.st_mtime
         tdiff = cur_time - mtime
         tdiff = tdiff / 60
         sun_status = day_or_night(f_date_str)
         print("TDIFF: ", tdiff, sun_status)
         if (tdiff > 3):
            if (sun_status == 'day'):
               print("Running:", file)
               quick_scan(file)
            else:
               print("Running:", file)
               quick_scan(file)
      else:
         print("already done.")


def remaster_arc(video_file):
   if "HD" in video_file: 
      json_file = video_file.replace("-HD.mp4", ".json")
   else:
      json_file = video_file.replace("-SD.mp4", ".json")
   out_file = video_file.replace(".mp4", "-pub.mp4")
   jd = load_json_file(json_file)
   frames,color_frames,subframes,sum_vals,max_vals = load_frames_fast(video_file, json_conf, 0, 0, [], 1,[])
   fds = jd['frames']
   meteor_obj = {}
   meteor_obj['oxs'] = []
   meteor_obj['oys'] = []
   for fd in fds:
      meteor_obj['oxs'].append(fd['x'])
      meteor_obj['oys'].append(fd['y'])
   remaster(color_frames,out_file,json_conf['site']['ams_id'], meteor_obj)

def remaster(frames, marked_video_file, station,meteor_object): 
   new_frames = []
   radiant = False
   fx = meteor_object['oxs'][0]
   fy = meteor_object['oys'][0]
   ax = np.mean(meteor_object['oxs'])
   ay = np.mean(meteor_object['oys'])

   cx1,cy1,cx2,cy2= bound_cnt(ax,ay,frames[0].shape[1],frames[0].shape[0], 100)
   #hdm_x = 1920 / 1280 
   #hdm_y = 1080 / 720
   hdm_x = 1
   hdm_y = 1
   cx1,cy1,cx2,cy2= int(cx1/hdm_x),int(cy1/hdm_y),int(cx2/hdm_x),int(cy2/hdm_y) 
   if "extra_logo" in json_conf['site']:
      logo_file = json_conf['site']['extra_logo']
      extra_logo = cv2.imread(logo_file, cv2.IMREAD_UNCHANGED)
   else:
      extra_logo = False
   #Get Date & time
   (hd_datetime, cam, sd_date, sd_y, sd_m, sd_d, sd_h, sd_M, sd_s) = convert_filename_to_date_cam(video_file)

   # Get Stations id & Cam Id to display
   station_id = station + "-" + cam
   station_id = station_id.upper()

   # Video Dimensions = as the first frame
   ih, iw = frames[0].shape[:2]
   start_sec = 0
   start_frame_time = hd_datetime + datetime.timedelta(0,start_sec)



   ams_logo = cv2.imread(AMS_WATERMARK, cv2.IMREAD_UNCHANGED)
   ams_logo_pos = "tl"
   if "extra_text" in json_conf['site']:
      extra_text = json_conf['site']['extra_text']
   extra_text_pos = "bl"
   date_time_pos = "br"
   extra_logo_pos = "tr"
   fc = 0
   for frame in frames:

      frame_sec = fc / FPS_HD
      frame_time = start_frame_time + datetime.timedelta(0,frame_sec)
      frame_time_str = frame_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
      fn = str(fc)
      hd_img = frame

      # Fading the box
      color = 150 - fc * 3
      if color > 50:
         cv2.rectangle(hd_img, (cx1, cy1), (cx2, cy2), (color,color,color), 1, cv2.LINE_AA)

      # Add AMS Logo
      hd_img = add_overlay_cv(hd_img, ams_logo, ams_logo_pos)

      # Add Eventual Extra Logo
      if(extra_logo is not False and extra_logo is not None):
         print("EXTRA:", extra_logo_pos) 
         hd_img = add_overlay_cv(hd_img,extra_logo,extra_logo_pos)

      # Add Date & Time
      frame_time_str = station_id + ' - ' + frame_time_str + ' UT'
      hd_img,xx,yy,ww,hh = add_text_to_pos(hd_img,frame_time_str,date_time_pos,2) #extra_text_pos => bl?

      # Add Extra_info
      if(extra_text is not False):
         hd_img,xx,yy,ww,hh = add_text_to_pos(hd_img,extra_text,extra_text_pos,2,True)  #extra_text_pos => br?

      # Add Radiant
      if(radiant is not False):
         if hd_img.shape[0] == 720 :
            rad_x = int(rad_x * .66666)
            rad_y = int(rad_y * .66666)
         hd_img = add_radiant_cv(radiant_image,hd_img,rad_x,rad_y,rad_name)

      new_frames.append(hd_img)
      fc = fc + 1

   make_movie_from_frames(new_frames, [0,len(new_frames) - 1], marked_video_file, 1)
   print('OUTPUT ' + marked_video_file )

def find_blob_center(fn, frame,bx,by,size,x_dir_mod,y_dir_mod):
   cx1,cy1,cx2,cy2= bound_cnt(bx,by,frame.shape[1],frame.shape[0],size)
   cnt_img = frame[cy1:cy2,cx1:cx2]
   min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(cnt_img)
   px_diff = max_val - min_val
   if px_diff < 10:
      #thresh_val = np.mean(cnt_img) - 5
      thresh_val = max_val - 10 
   else:
      thresh_val = max_val - int(px_diff /2)
   _ , thresh_img = cv2.threshold(cnt_img.copy(), thresh_val, 255, cv2.THRESH_BINARY)
   cnt_res = cv2.findContours(thresh_img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
   if len(cnt_res) == 3:
      (_, cnts, xx) = cnt_res
   elif len(cnt_res) == 2:
      (cnts, xx) = cnt_res
   pos_cnts = []
   if len(cnts) > 3:
      # Too many cnts be more restrictive!
      thresh_val = max_val - int(px_diff /4)
      _ , thresh_img = cv2.threshold(cnt_img.copy(), thresh_val, 255, cv2.THRESH_BINARY)
      cnt_res = cv2.findContours(thresh_img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
      if len(cnt_res) == 3:
         (_, cnts, xx) = cnt_res
      elif len(cnt_res) == 2:
         (cnts, xx) = cnt_res

   if len(cnts) > 0:
      for (i,c) in enumerate(cnts):
         x,y,w,h = cv2.boundingRect(cnts[i])
         if w > 1 or h > 1:
            size = w + h
            mx = int(x + (w / 2))
            my = int(y + (h / 2))
            cv2.rectangle(thresh_img, (x, y), (x+w, x+h), (255,255,255), 1, cv2.LINE_AA)
            pos_cnts.append((x,y,w,h,size,mx,my))
      if x_dir_mod == 1:
         temp = sorted(pos_cnts, key=lambda x: x[1], reverse=False)
      else:
         temp = sorted(pos_cnts, key=lambda x: x[1], reverse=True)
      if len(temp) > 0:
         (x,y,w,h,size,mx,my) = temp[0]
         min_val, max_val, min_loc, (bmx,bmy)= cv2.minMaxLoc(cnt_img)
         #blob_x = mx + cx1
         #blob_y = my + cy1
         blob_x = int(x + (w/2)) + cx1
         blob_y = int(y + (h/2)) + cy1
         max_px = max_val
         blob_w = w
         blob_h = h
         show_cnt = cnt_img.copy()
         desc = str(fn)
         cv2.putText(thresh_img, desc,  (3,10), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
         cv2.circle(thresh_img,(mx,my), 1, (255,255,255), 1)
         return(int(blob_x), int(blob_y),max_val,int(blob_w),int(blob_h))
      else:
         desc = str(fn) + "NF!"
         cv2.putText(thresh_img, desc,  (3,10), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
         return(int(bx), int(by),max_val,10,10)



# Add text over background
# WARNING: bg is NOT a cv image but a full path (for PIL)
# Position = br, bl, tr, tl (ex: br = bottom right)
# and line_number that corresponds to the # of the line to write
# ex: if line_number = 1 => first line at this position
#                    = 2 => second line at this position
# return updated cv matrix
def add_text_to_pos(background,text,position,line_number=1,bold=False):

    # Convert background to RGB (OpenCV uses BGR)
    cv2_background_rgb = cv2.cvtColor(background,cv2.COLOR_BGR2RGB)

    # Pass the image to PIL
    pil_im = Image.fromarray(cv2_background_rgb)
    draw = ImageDraw.Draw(pil_im)

    # use DEFAULT truetype font
    if(bold==True):
        font = ImageFont.truetype(VIDEO_FONT_BOLD, VIDEO_FONT_SIZE)
    else:
        font = ImageFont.truetype(VIDEO_FONT, VIDEO_FONT_SIZE)

    # Get Text position - see lib.Video_Tools_cv_lib
    y,x,w,h = get_text_position_cv(background,text,position,line_number,font)

    # Draw the text
    draw.text((x, y), text, font=font)

    # Get back the image to OpenCV
    cv2_im_processed = cv2.cvtColor(np.array(pil_im), cv2.COLOR_RGB2BGR)

    # We now return the image AND the box position of the text
    # so we can check if the meteors flies behind the text
    return cv2_im_processed,y,x,w,h


# Add semi-transparent overlay over background on x,y
# return updated cv matrix
def add_overlay_x_y_cv(background, overlay, x, y):

    background_width,background_height  = background.shape[1], background.shape[0]

    if x >= background_width or y >= background_height:
        return background

    h, w = overlay.shape[0], overlay.shape[1]

    if x + w > background_width:
        w = background_width - x
        overlay = overlay[:, :w]

    if y + h > background_height:
        h = background_height - y
        overlay = overlay[:h]

    if overlay.shape[2] < 4:
        overlay = np.concatenate(
            [
                overlay,
                np.ones((overlay.shape[0], overlay.shape[1], 1), dtype = overlay.dtype) * 255
            ],
            axis = 2,
        )

    overlay_image = overlay[..., :3]
    mask = overlay[..., 3:] / 255.0

    background[y:y+h, x:x+w] = (1.0 - mask) * background[y:y+h, x:x+w] + mask * overlay_image

    return background


# Add semi-transparent overlay over background
# Position = br, bl, tr, tl (ex: br = bottom right)
# return updated cv matrix
#def add_overlay_cv(background, overlay, position):
#    background_width,background_height  = background.shape[1], background.shape[0]
#    # Get overlay position - see lib.Video_Tools_cv_lib
#    #x,y = get_overlay_position_cv(background,overlay,position)
#    x = 5
#    y = 5
#    return add_overlay_x_y_cv(background, overlay, x, y)


# Add radiant to a frame
def add_radiant_cv(radiant_image,background,x,y,text):

    # Add Image if possible (inside the main frame)
    try:
        background = add_overlay_x_y_cv(background,radiant_image,x-int(radiant_image.shape[1]/2),y-int(radiant_image.shape[0]/2))
    except:
        background = background

    # Add text (centered bottom)
    background = add_text(background,text,x,y+int(radiant_image.shape[1]/2),True)

    return background




def load_json_conf(station_id):
   try:
      json_conf = load_json_file(ARCHIVE_DIR + station_id + "/CONF/as6.json")
   except:
      json_conf = load_json_file("/home/ams/amscams/conf/as6.json")
   return(json_conf)


def get_cal_params(input_file, station_id):
   if "png" in input_file:
      input_file = input_file.replace(".png", ".mp4")
   if "json" in input_file:
      input_file = input_file.replace(".json", ".mp4")
   (f_datetime, cam_id, f_date_str,Y,M,D, H, MM, S) = better_parse_file_date(input_file)

   # find all cal files from his cam for the same night
   matches = find_matching_cal_files(station_id, cam_id, f_datetime)
   if len(matches) > 0:
      return(matches)
   else:
      return(None)

def find_matching_cal_files(station_id, cam_id, capture_date):
   matches = []
   #cal_dir = ARCHIVE_DIR + station_id + "/CAL/*.json"
   cal_dir = "/mnt/ams2/cal/freecal/*"
   all_files = glob.glob(cal_dir)
   for file in all_files:
      if cam_id in file :
         el = file.split("/")
         fn = el[-1]
         cp = file + "/" + fn + "-stacked-calparams.json"
         if cfe(cp) == 1:
            matches.append(cp)
         else:
            print("CP NOT FOUND!", cp)
            cp = file + "/" + fn + "-calparams.json"
            if cfe(cp) == 1:
               matches.append(cp)

   td_sorted_matches = []

   for match in matches:
      (t_datetime, cam_id, f_date_str,Y,M,D, H, MM, S) = better_parse_file_date(match)
      tdiff = abs((capture_date-t_datetime).total_seconds())
      td_sorted_matches.append((match,f_date_str,tdiff))

   temp = sorted(td_sorted_matches, key=lambda x: x[2], reverse=False)

   return(temp)

def get_station_id(video_file):
   tmp = video_file.split("/")
   for t in tmp:
      if "AMS" in t:
         station_id = t 
         return(station_id)
   else:
      return("AMS1")

def find_contours_in_frame(frame, thresh=25):
   contours = [] 
   result = []
   _, threshold = cv2.threshold(frame.copy(), thresh, 255, cv2.THRESH_BINARY)
   thresh_obj = cv2.dilate(threshold.copy(), None , iterations=4)
   threshold = cv2.convertScaleAbs(thresh_obj)
   cnt_res = cv2.findContours(threshold.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
   if len(cnt_res) == 3:
      (_, cnts, xx) = cnt_res
   elif len(cnt_res) == 2:
      (cnts, xx) = cnt_res
   show_frame = cv2.resize(threshold, (0,0),fx=.5, fy=.5)

   if len(cnts) > 20:
      print("RECT TOO MANY CNTS INCREASE THRESH!", len(cnts))
      thresh = thresh +5 
      _, threshold = cv2.threshold(frame.copy(), thresh, 255, cv2.THRESH_BINARY)
      thresh_obj = cv2.dilate(threshold.copy(), None , iterations=4)
      threshold = cv2.convertScaleAbs(thresh_obj)
      cnt_res = cv2.findContours(threshold.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

      if len(cnt_res) == 3:
         (_, cnts, xx) = cnt_res
      elif len(cnt_res) == 2:
         (cnts, xx) = cnt_res

   # now of these contours, remove any that are too small or don't have a recognizable blob
   # or have a px_diff that is too small

   rects = []
   recs = []
   if len(cnts) < 50:
      for (i,c) in enumerate(cnts):
         px_diff = 0
         x,y,w,h = cv2.boundingRect(cnts[i])
        

         if w > 1 or h > 1:
            cnt_frame = frame[y:y+h, x:x+w]
            min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(cnt_frame)
            avg_val = np.mean(cnt_frame)
            if max_val - avg_val > 5:
               rects.append([x,y,x+w,y+h])
               contours.append([x,y,w,h])

   #rects = np.array(rects)



   if len(rects) > 2:
      #print("RECT TOTAL CNT RECS:", len(rects))
      recs, weights = cv2.groupRectangles(rects, 0, .05)
      rc = 0
      #print("TOTAL RECT GROUPS:", len(recs))
      for res in recs:
         #print("RECT RESULT:", rc, res)
         rc = rc + 1


   return(contours, recs)

def fast_bp_detect(gray_frames, video_file):
   subframes = []
   frame_data = []
   objects = {}
   np_imgs = np.asarray(gray_frames[0:50])
   median_frame = cv2.convertScaleAbs(np.median(np.array(np_imgs), axis=0))
   median_cnts,rects = find_contours_in_frame(median_frame, 100)
   mask_points = []
   for x,y,w,h in median_cnts:
      mask_points.append((x,y))
   #median_frame = mask_frame(median_frame, mask_points, [], 5)
   fc = 0
   last_frame = median_frame

   for frame in gray_frames:
      frame = mask_frame(frame, mask_points, [], 5)
      subframe = cv2.subtract(frame, last_frame)
      sum_val =cv2.sumElems(subframe)[0]

      frame_data.append(sum_val)
      subframes.append(subframe)
      last_frame = frame
      fc = fc + 1
   return(frame_data, subframes) 


def bp_detect( gray_frames, video_file):
   objects = {}
   mean_max = []
   subframes = []
   mean_max_avg = None
   frame_data = {}
   fn = 0
   last_frame = None

   np_imgs = np.asarray(gray_frames[0:50])
   median_frame = cv2.convertScaleAbs(np.median(np.array(np_imgs), axis=0))
   median_cnts,rects = find_contours_in_frame(median_frame, 100)
   mask_points = []
   for x,y,w,h in median_cnts:
      mask_points.append((x,y))
   #median_frame = mask_frame(median_frame, mask_points, [], 5)

   sum_vals = []
   running_sum = 0
   
 
   for frame in gray_frames:
      # Good place to save these frames for final analysis visual
      frame = mask_frame(frame, mask_points, [], 5)

      #if fn > 100 and fn % 50 == 0:
      #   np_imgs = np.asarray(gray_frames[fn-100:fn-50])
      #   running_sum = np.median(sum_vals[:-100])
      #   median_frame = cv2.convertScaleAbs(np.median(np.array(np_imgs), axis=0))

      if last_frame is None:
         last_frame = frame

      #extra_meteor_sec = int(fn) / 25


      frame_data[fn] = {}
      frame_data[fn]['fn'] = fn

      #medless_frame = cv2.subtract(frame, median_frame)

      subframe = cv2.subtract(frame,last_frame)
      #thresh = 10
      #_, threshold = cv2.threshold(subframe.copy(), thresh, 255, cv2.THRESH_BINARY)

      subframes.append(subframe)

      sum_val = np.sum(subframe)
      sum_vals.append(sum_val)

      if False:
         contours,rects = find_contours_in_frame(subframe)     
         if len(contours) > 0:
            for ct in contours:
               object, objects = find_object(objects, fn,ct[0], ct[1], ct[2], ct[3])
            #print("CNTS:", contours, object)
      else:
         contours = []
 
      #min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(subframe)

      frame_data[fn]['sum_val'] = float(sum_val)
      frame_data[fn]['contours'] = contours
      last_frame = frame
      fn = fn + 1


   return(frame_data, subframes, objects) 

def detect_motion_in_frames(subframes, video_file, fn):
   cnt_frames = {} 
   if len(subframes) == 0:
      return(cnt_frames)

   median_subframe = cv2.convertScaleAbs(np.median(np.array(subframes), axis=0))

   
   image_acc = np.empty(np.shape(subframes[0]))
  
   if len(image_acc.shape) > 2:
      image_acc = cv2.cvtColor(image_acc, cv2.COLOR_BGR2GRAY)

   #fn = 0
   for frame in subframes:
      frame = cv2.subtract(frame, median_subframe)
      cnt_frames[fn] = {}
      cnt_frames[fn]['xs'] = []
      cnt_frames[fn]['ys'] = []
      cnt_frames[fn]['ws'] = []
      cnt_frames[fn]['hs'] = []
     # image_acc = cv2.convertScaleAbs(image_acc)
     # frame = cv2.convertScaleAbs(frame)
      image_acc = np.float32(image_acc)
      frame = np.float32(frame)
      blur_frame = cv2.GaussianBlur(frame, (7, 7), 0)

      alpha = .5

      if len(frame.shape) > 2:
         frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

      image_diff = cv2.absdiff(image_acc.astype(frame.dtype), blur_frame,)
      #print(frame.shape, image_acc.shape)
      hello = cv2.accumulateWeighted(blur_frame, image_acc, alpha)
      min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(blur_frame)
      avg_val = np.median(blur_frame)
      thresh = avg_val + (max_val/1.3)
      _, threshold = cv2.threshold(image_diff.copy(), thresh, 255, cv2.THRESH_BINARY)
      thresh_obj = cv2.dilate(threshold.copy(), None , iterations=4)
      thresh_obj = cv2.convertScaleAbs(thresh_obj)
      # save this for final view
      print("THRESH", thresh)

      cnt_res = cv2.findContours(thresh_obj.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
      if len(cnt_res) == 3:
         (_, cnts, xx) = cnt_res
      elif len(cnt_res) == 2:
         (cnts, xx) = cnt_res
      print("CNTS:", len(cnts))


      if len(cnts) < 50:
         for (i,c) in enumerate(cnts):
            px_diff = 0
            x,y,w,h = cv2.boundingRect(cnts[i])
            if w > 2 and h > 2:
               cnt_frames[fn]['xs'].append(x)
               cnt_frames[fn]['ys'].append(y)
               cnt_frames[fn]['ws'].append(w)
               cnt_frames[fn]['hs'].append(h)
      fn = fn + 1
   return(cnt_frames)

def detect_objects_by_motion(frames, fn) :
   image_acc = frames[0]
   for frame in frames:
      blur_frame = cv2.GaussianBlur(frame, (7, 7), 0)

      alpha = .5

      image_diff = cv2.absdiff(image_acc.astype(frame.dtype), blur_frame,)
      hello = cv2.accumulateWeighted(blur_frame, image_acc, alpha)
      thresh = 25
      _, threshold = cv2.threshold(image_diff.copy(), thresh, 255, cv2.THRESH_BINARY)

      thresh_obj = cv2.dilate(threshold.copy(), None , iterations=4)
      thresh_obj = cv2.convertScaleAbs(thresh_obj)
      cnt_res = cv2.findContours(thresh_obj.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
      if len(cnt_res) == 3:
         (_, cnts, xx) = cnt_res
      elif len(cnt_res) == 2:
         (cnts, xx) = cnt_res

      if len(cnts) < 50:
         for (i,c) in enumerate(cnts):
            px_diff = 0
            x,y,w,h = cv2.boundingRect(cnts[i])
            if w > 2 and h > 2:
               cnt_frames[fn]['xs'].append(x)
               cnt_frames[fn]['ys'].append(y)
               cnt_frames[fn]['ws'].append(w)
               cnt_frames[fn]['hs'].append(h)
      fn = fn + 1
   return(cnt_frames)

  
def find_cnt_objects(cnt_frame_data, objects):
   #objects = {}
   for fn in cnt_frame_data: 
      cnt_xs = cnt_frame_data[fn]['xs']
      cnt_ys = cnt_frame_data[fn]['ys']
      cnt_ws = cnt_frame_data[fn]['ws']
      cnt_hs = cnt_frame_data[fn]['hs']
      for i in  range(0, len(cnt_xs)):
         object, objects = find_object(objects, fn,cnt_xs[i], cnt_ys[i], cnt_ws[i], cnt_hs[i])
   return(objects)

def cnt_size_test(object):
   big = 0
   for i in range(0,len(object['ofns'])):
      w = object['ows'][i]
      h = object['ohs'][i]
      if w > 75 and h > 75:
         big = big + 1
   big_perc = big / len(object['ofns'])
   return(big_perc)



def analyze_object_final(object, hd=0, sd_multi=1):
   #return(object)
   id = object['obj_id']

   # make sure all of the frames belong to the same cluster
   points = []
   frames = []
   for i in range(0, len(object['oxs'])):
      frames.append((object['ofns'][i], object['ofns'][i]))

   frame_labels = find_clusters(frames)
   objects_by_label = {}
   i = 0
   for label in frame_labels:
      if label not in objects_by_label:
         objects_by_label[label] = {}
         objects_by_label[label]['ofns'] = []
         objects_by_label[label]['oxs'] = []
         objects_by_label[label]['oys'] = []
         objects_by_label[label]['ows'] = []
         objects_by_label[label]['ohs'] = []
      objects_by_label[label]['obj_id'] = id
      objects_by_label[label]['ofns'].append(object['ofns'][i])
      objects_by_label[label]['oxs'].append(object['oxs'][i])
      objects_by_label[label]['oys'].append(object['oys'][i])
      objects_by_label[label]['ows'].append(object['ows'][i])
      objects_by_label[label]['ohs'].append(object['ohs'][i])
      i = i + 1     


   if len(objects_by_label) == 1:
      # there is only one cluster of frames so we are good. 
      object = analyze_object(object, hd, sd_multi)
      return(object)
   else:
      # there is more than one cluster of frames, so we need to remove the erroneous frames 
      most_frames = 0
      for label in objects_by_label :
         if len(objects_by_label[label]['ofns']) > most_frames:
            most_frames = len(objects_by_label[label]['ofns'])
            best_label = label
   
   # update the object to include only data items from the best label (cluster)
   object['obj_id'] = objects_by_label[best_label]['obj_id'] 
   object['ofns'] = objects_by_label[best_label]['ofns']
   object['oxs'] = objects_by_label[best_label]['oxs']
   object['oys'] = objects_by_label[best_label]['oys']
   object['ows'] = objects_by_label[best_label]['ows']
   object['ohs'] = objects_by_label[best_label]['ohs']



   object = analyze_object(object, hd, sd_multi, 1)
   return(object)

def remove_bad_frames_from_object(object,frames,subframes ):
   stacked_frame = stack_frames_fast(frames)
   stacked_frame = cv2.cvtColor(stacked_frame,cv2.COLOR_GRAY2RGB)

   line_segs = []
   x_segs = []
   y_segs = []
   dist_from_start = []
   ms = []
   bs = []

   ff = object['ofns'][0] 
   lf = object['ofns'][-1] 
   fx = object['oxs'][0] 
   fy = object['oys'][0] 
   m,b = best_fit_slope_and_intercept(object['oxs'],object['oys'])

   x_dir_mod,y_dir_mod = meteor_dir(object['oxs'][0], object['oys'][0], object['oxs'][-1], object['oys'][-1])

  
   #est_x = int(fx + x_dir_mod * (med_seg_len*fcc))
 

   # find distance from start point for each frame
   # turn that into seg_dist for each frame
   for i in range(0, len(object['ofns'])):
      tx = object['oxs'][i]
      ty = object['oys'][i]
      dist = calc_dist((fx,fy),(tx,ty))
      dist_from_start.append(dist)
      if i > 0 and i < len(object['ofns']):
         tm,tb = best_fit_slope_and_intercept([fx,tx],[fy,ty])
         seg_len = dist_from_start[i] - dist_from_start[i-1] 
         line_segs.append(seg_len)
         x_segs.append(object['oxs'][i-1] - tx)
         ms.append(tm)
         bs.append(tb)
      
      else:
         line_segs.append(9999)
         ms.append(9999)
         bs.append(9999)
        

   #print("DIST FROM START:", dist_from_start)
   #print("LINE SEGS:", np.median(line_segs), line_segs)
   #print("XSEGS :", np.median(line_segs), line_segs)
   #print("MS:", np.median(ms),ms)
   #print("BS:", np.median(bs),bs)
   med_seg_len = np.median(line_segs)
   med_x_seg_len = np.median(x_segs)
   acl_poly = 0
   med_m = np.median(ms)
   med_b = np.median(bs)

   #print("BS:", np.median(bs),bs)
   est_xs = []
   est_ys = []

   for i in range(0, len(object['ofns'])):
      tx = object['oxs'][i]
      ty = object['oys'][i]
      if i > 0: 
         est_x = int((fx + (x_dir_mod) * (med_x_seg_len*i)) + acl_poly * i)
         est_y = int((m*est_x)+b)
         print("EST:", est_x,est_y)
         est_xs.append(est_x)
         est_ys.append(est_y)
      else:
         est_x = tx
         est_y = ty
         est_xs.append(est_x)
         est_ys.append(est_y)

   print("XS:", object['oxs'])
   print("YS:", object['oys'])
   print("EXS:", est_xs)
   print("EYS:", est_ys)
   object['est_xs'] = est_xs
   object['est_ys'] = est_ys
   show_frame = stacked_frame.copy()
   scx = 2
   scy = 2
   show_frame = cv2.resize(show_frame, (0,0),fx=scx, fy=scy)
   new_oxs = []
   new_oys = []
   res_xs = []
   res_ys = []
   res_tot = []
   cl = 255
   for i in range(0, len(object['oxs'])):
      res_x = abs(object['oxs'][i] - object['est_xs'][i])
      res_y = abs(object['oys'][i] - object['est_ys'][i])
      res_xs.append(res_x)
      res_ys.append(res_y)
      res_tot.append(res_x + res_y)
      if res_x + res_y >= 4:
         show_frame[object['oys'][i]*scy,object['oxs'][i]*scx] = (0,0,cl)
         show_frame[object['est_ys'][i]*scy,object['est_xs'][i]*scx] = (cl,cl,0)
         cv2.line(show_frame, ((object['oxs'][i]*scx)-1,(object['oys'][i]*scy)-1), ((object['est_xs'][i]*scx)-1,(object['est_ys'][i]*scy)-1), (128,128,128), 1) 
         #cv2.circle(show_frame,(object['oxs'][i],object['oys'][i]), 5, (0,0,cl), 1)
         new_oxs.append(object['est_xs'][i])
         new_oys.append(object['est_ys'][i])
      else:
         show_frame[object['oys'][i]*scy,object['oxs'][i]*scx] = (0,cl,0)
         show_frame[object['est_ys'][i]*scy,object['est_xs'][i]*scx] = (0,cl,cl)
         new_oxs.append(object['oxs'][i])
         new_oys.append(object['oys'][i])
         #cv2.circle(show_frame,(object['oxs'][i],object['oys'][i]), 5, (0,cl,0), 1)
         #cv2.circle(show_frame,(object['est_xs'][i],object['est_ys'][i]), 5, (0,cl,cl), 1)
      #cv2.line(show_frame, (object['est_xs'][i], object['est_ys'][i]), (object['est_xs'][i]-10,object['est_ys'][i]), (128,128,128), 1) 
      #cv2.line(show_frame, (object['oxs'][i], object['oys'][i]), (object['oxs'][i]+10,object['oys'][i]), (128,128,128), 1) 
      cl = cl - 10
   print("RES X:", res_xs)
   print("RES Y:", res_ys)
   print("RES TOTAL:", res_tot)
   show_frame = stacked_frame.copy()
   show_frame = cv2.resize(show_frame, (0,0),fx=scx, fy=scy)
   for i in range(0, len(new_oxs) -1):
      x = new_oxs[i]
      y = new_oys[i]
      fn = object['ofns'][i]
      show_frame = frames[fn].copy()
      show_frame = cv2.resize(show_frame, (0,0),fx=scx, fy=scy)
      show_frame = cv2.cvtColor(show_frame,cv2.COLOR_GRAY2RGB)
      show_frame[y*scy,x*scx] = (0,cl,0)

   test_object = object
   test_object['oxs'] = new_oxs
   test_object['oys'] = new_oys
     
   calc_point_res(test_object,frames) 
   return(object)
   
def calc_point_res(object, frames):
   scx = 2
   scy = 2
   line_segs = []
   x_segs = []
   y_segs = []
   dist_from_start = []
   ms = []
   bs = []

   ff = object['ofns'][0]
   lf = object['ofns'][-1]
   fx = object['oxs'][0]
   fy = object['oys'][0]
   m,b = best_fit_slope_and_intercept(object['oxs'],object['oys'])

   x_dir_mod,y_dir_mod = meteor_dir(object['oxs'][0], object['oys'][0], object['oxs'][-1], object['oys'][-1])

 
   #est_x = int(fx + x_dir_mod * (med_seg_len*fcc))


   # find distance from start point for each frame
   # turn that into seg_dist for each frame
   for i in range(0, len(object['ofns'])):
      tx = object['oxs'][i]
      ty = object['oys'][i]
      dist = calc_dist((fx,fy),(tx,ty))
      dist_from_start.append(dist)
      if i > 0 and i < len(object['ofns']):
         tm,tb = best_fit_slope_and_intercept([fx,tx],[fy,ty])
         seg_len = dist_from_start[i] - dist_from_start[i-1]
         line_segs.append(seg_len)
         x_segs.append(object['oxs'][i-1] -tx)
         ms.append(tm)
         bs.append(tb)

      else:
         line_segs.append(9999)
         ms.append(9999)
         bs.append(9999)

   med_seg_len = np.median(line_segs)
   med_x_seg_len = np.median(x_segs)
   if med_x_seg_len == 0:
      med_x_seg_len = np.mean(x_segs)
   print("XSEGS:", x_segs)

   acl_poly = 0
   med_m = np.median(ms)
   med_b = np.median(bs)
   est_xs = []
   est_ys = []
   res_xs = []
   res_ys = []
   res_tot = []
   cl = 255

   for i in range(0, len(object['ofns'])):
      tx = object['oxs'][i]
      ty = object['oys'][i]
      fn = object['ofns'][i]
      if i > 0:
         est_x = int((fx + (x_dir_mod) * (med_x_seg_len*i)) + acl_poly * i)
         est_y = int((m*est_x)+b)
         print("M,B,EST_X:", m, b, est_x, i )
         print("EST INFO:", fx, x_dir_mod, med_x_seg_len, i )
         print("EST:", est_x,est_y)
         est_xs.append(est_x)
         est_ys.append(est_y)
      else:
         est_x = tx
         est_y = ty
         est_xs.append(est_x)
         est_ys.append(est_y)

      show_frame = frames[fn].copy()
      show_frame = cv2.resize(show_frame, (0,0),fx=scx, fy=scy)
      show_frame = cv2.cvtColor(show_frame,cv2.COLOR_GRAY2RGB)
      print(show_frame.shape)
      show_frame[ty*scy,tx*scx] = (0,cl,0)

      esx,esy = bound_point(est_x, est_y, show_frame)
      show_frame[esy,esx] = (0,cl,cl)


   for i in range(0, len(object['oxs'])):
      res_x = abs(object['oxs'][i] - object['est_xs'][i])
      res_y = abs(object['oys'][i] - object['est_ys'][i])
      res_xs.append(res_x)
      res_ys.append(res_y)
      res_tot.append(res_x + res_y)


   print("XS:", object['oxs'])
   print("YS:", object['oys'])
   print("EXS:", est_xs)
   print("EYS:", est_ys)
   print("XRES :", res_xs)
   print("YRES :", res_ys)
   print("RES TOT:", res_tot)
   print("LINE SEGS:", line_segs)
   object['est_xs'] = est_xs
   object['est_ys'] = est_ys

   print(object)

   print("POLYFIT")
   import matplotlib
   import matplotlib.pyplot as plt

   poly_x = np.array(object['oxs'])
   poly_y = np.array(object['oys'])
   poly_est_x = np.array(object['est_xs'])

   print("POLY X:", poly_x)
   print("POLY Y:", poly_y)

   z = np.polyfit(poly_x,poly_y,1)
   f = np.poly1d(z)
   plt.axis('equal')

   #range(min(poly_x), max(poly_x)):
   new_ys = []

   #show_frame = frames[0] 
   show_frame = stack_frames_fast(frames)
   show_frame = cv2.cvtColor(show_frame,cv2.COLOR_GRAY2RGB)
   cc = 0
   for i in range(poly_x[0],poly_x[-1]):
      x = i
      y = int(f(i))
      #ox = x
      #oy = poly_y[cc]
      show_frame[y,x] = [0,0,255]
      new_ys.append(int(f(i)))
      cc = cc + 1
   for ox,oy in zip(poly_x, poly_y):
      show_frame[oy,ox] = [255,0,0]
   print("NEW YS:", new_ys)
   print("NEW XS:", new_xs)
   plt.plot(poly_x, poly_y, 'x')
   plt.plot(new_xs, new_ys, 'x')
   ax = plt.gca()
   ax.invert_yaxis()
   plt.show()


def poly_fit(object):
   #print("POLY FIT:", object['report'])
   import matplotlib
   matplotlib.use('Agg')
   import matplotlib.pyplot as plt

   poly_x = np.array(object['oxs'])
   poly_y = np.array(object['oys'])

   if len(poly_x) > 5:
      try:
         z = np.polyfit(poly_x,poly_y,1)
         f = np.poly1d(z)
      except:
         return(0)
        
   else:
      return(0)


   new_ys = []
   new_xs = []

   cc = 0
   for i in range(poly_x[0],poly_x[-1]):
      #plt.plot(i, f(i), 'go')
      x = i
      y = int(f(i))
      new_ys.append(int(f(i)))
      new_xs.append(i)
      cc = cc + 1
   plt.plot(poly_x, poly_y, 'x')
   plt.plot(new_xs, new_ys, 'go')
   plt.axis('equal')
   #plt.xlim(0,704)
   #plt.ylim(0,576)
   trendpoly = np.poly1d(z) 
   plt.plot(poly_x,trendpoly(poly_x))
   ax = plt.gca()
   ax.invert_yaxis()
   #plt.show()
   line_res = []
   for i in range(0,len(poly_x)-1):
      px = poly_x[i]
      py = poly_y[i]
      dist_to_line = distance((px,py),z)
      line_res.append(dist_to_line)
   avg_line_res = np.mean(line_res)
   return(avg_line_res)
      

def distance(point,coef):
    return abs((coef[0]*point[0])-point[1]+coef[1])/math.sqrt((coef[0]*coef[0])+1)



def bound_point(est_y, est_x, image):
   if True:
      if est_y < 0:
         est_y = 0
      else:
         est_y = est_y  
      if est_x < 0:
         esx = 0
      else:
         esx = est_x  
      if est_x > image.shape[1]:
         est_x = image.shape[1]
      if est_y > image.shape[0]:
         est_0 = image.shape[0]
   return(est_x, est_y)

def unq_points(object):
   points = {}
   tot = 0
   for i in range(0, len(object['oxs'])):
      x = object['oxs'][i]
      y = object['oys'][i]
      key = str(x) + "." + str(y)
      points[key] = 1
      tot = tot + 1

   unq_tot = len(points)
   perc = unq_tot / tot
   return(perc)

def analyze_object(object, hd = 0, sd_multi = 1, final=0):
   if hd == 1:
      deg_multi = .042
   else:
      deg_multi = .042 * sd_multi

   if "ofns" not in object:
      if "report" not in object:
         object['report'] = {}
         object['report']['meteor_yn'] = "no"
      else:
         object['report']['meteor_yn'] = "no"
      return(object)
   if len(object['ofns']) == 0:
      if "report" not in object:
         object['report'] = {}
         object['report']['meteor_yn'] = "no"
      else:
         object['report']['meteor_yn'] = "no"
      return(object)

   object = calc_leg_segs(object)
   unq_perc = unq_points(object)
   #print("UNQ POINTS PER:", unq_perc, object['oxs'], object['oys'])

   if len(object['ofns']) > 2:
      dir_test_perc = meteor_dir_test(object['oxs'],object['oys'])
      big_perc = cnt_size_test(object)
   else:
      dir_test_perc = 0
      big_perc = 0


   id = object['obj_id']
   meteor_yn = "Y"
   obj_class = "undefined"
   ff = object['ofns'][0] 
   lf = object['ofns'][-1] 
   elp = lf - ff 
   min_x = min(object['oxs'])
   max_x = max(object['oxs'])
   min_y = min(object['oys'])
   max_y = max(object['oys'])
   max_int = max(object['oint'])
   min_int = min(object['oint'])
   max_h = max(object['ohs'])
   max_w = max(object['ows'])
   #max_x = max_x + max_w
   #max_h = max_y + max_h

   med_int = float(np.median(object['oint']))
   intense_neg = 0
   for intense in object['oint']:
      if intense < 0:
         intense_neg = intense_neg + 1
   min_max_dist = calc_dist((min_x, min_y), (max_x,max_y))
   if len(object['ofns']) > 0:
      if final == 0:
          
         dist_per_elp = min_max_dist / len(object['ofns']) 
      else:
         if elp > 0:
            dist_per_elp = min_max_dist / elp
         else:
            dist_per_elp = 0
   else:
      dist_per_elp = 0

   if elp > 5 and dist_per_elp < .1 or dist_per_elp < .11:
      moving = "not moving"
      meteor_yn = "no"
      obj_class = "star"
   else:
      moving = "moving"
   if min_max_dist > 12 and dist_per_elp < .1:
      moving = "slow moving"
      meteor_yn = "no"
      obj_class = "plane"
   if min_max_dist > 12 and dist_per_elp < .1:
      moving = "slow moving"
      meteor_yn = "no"
      obj_class = "plane"
   if dist_per_elp < .8 and dist_per_elp > .1:
      moving = "slow moving"
      meteor_yn = "no"
      obj_class = "plane"

   #cm
   fc = 0
   cm = 1
   max_cm = 1
   last_fn = None
   for fn in object['ofns']:
      if last_fn is not None:
         if last_fn + 1 == fn or last_fn + 2 == fn: 
            cm = cm + 1
            if cm > max_cm :
               max_cm = cm
      
      fc = fc + 1
      last_fn = fn
   if len(object['ofns']) > 1:
      x_dir_mod,y_dir_mod = meteor_dir(object['oxs'][0], object['oys'][0], object['oxs'][-1], object['oys'][-1])
   else:
      x_dir_mod = 0
      y_dir_mod = 0
   
   if len(object['ofns'])> 0:
      cm_to_len = max_cm / len(object['ofns'])
   else: 
      meteor_yn = "no"
      obj_class = "plane"
   if cm_to_len < .4:
      meteor_yn = "no"
      obj_class = "plane"

   if len(object['ofns']) >= 300:
      # if cm_to_len is acceptable then skip this. 
      if cm_to_len < .6:
         meteor_yn = "no"
         obj_class = "plane"



   # classify the object
   bad_items = []
 
   if max_cm <= 3 and elp > 5 and min_max_dist < 8 and dist_per_elp < .01:
      obj_class = "star"
   if elp > 5 and min_max_dist > 8 and dist_per_elp >= .01 and dist_per_elp < 1:
      obj_class = "plane"
   if elp > 300:
      meteor_yn = "no"
      bad_items.append("more than 300 frames in event.")
   if max_cm > 0:
      neg_perc = intense_neg / max_cm 
      if intense_neg / max_cm > .5:
         meteor_yn = "no" 
         bad_items.append("too much negative intensity." + str(intense_neg))
   else:
      neg_perc = 0
   if elp < 2:
      meteor_yn = "no" 
      bad_items.append("less than 2 frames in event.")
   if big_perc > .3:
      meteor_yn = "no"
      bad_items.append("too many big cnts." + str(big_perc))
   if max_cm < 3:
      meteor_yn = "no"
      bad_items.append("less than 2 consecutive motion.")
   if dist_per_elp > 5:
      meteor_yn = "Y"
   if med_int < 5 and med_int != 0:
      meteor_yn = "no"
      obj_class = "bird"
      bad_items.append("low or negative median intensity.")
   if dir_test_perc < .5 :
      meteor_yn = "no"
      obj_class = "noise"
      bad_items.append("direction test failed." + str(dir_test_perc))
   if unq_perc < .65:
      meteor_yn = "no"
      obj_class = "star or plane"
      bad_items.append("unique points test failed." + str(unq_perc))

   if max_cm > 0:
      elp_max_cm = elp / max_cm
      if elp / max_cm >3:
         obj_class = "plane"
         meteor_yn = "no"
         bad_items.append("elp to cm to high." + str(elp / max_cm))
   else:
      elp_max_cm = 0

   if min_max_dist < 5:
      obj_class = "star"
      meteor_yn = "no"
      bad_items.append("not enough distance.")
   if (min_max_dist * deg_multi) < .3:
      meteor_yn = "no"
      bad_items.append("bad angular distance below .3.")
   if (dist_per_elp * deg_multi) * 25 < .9:
      meteor_yn = "no"
      bad_items.append("bad angular velocity below .9")
   ang_vel = (dist_per_elp * deg_multi) * 25

   #YOYO
   if dir_test_perc < 1 and max_cm < 5:
      meteor_yn = "no"
      obj_class = "star"
      bad_items.append("dir test perc to low for this cm")

   if max_cm < 5 and elp_max_cm > 1.5 and neg_perc > 0:
      meteor_yn = "no"
      obj_class = "plane"
      bad_items.append("low max cm, high neg_perc, high elp_max_cm")

   if ang_vel < 1.5 and elp_max_cm > 2:
      meteor_yn = "no"
      bad_items.append("short distance, many gaps, low cm")
      obj_class = "plane"


   if elp > 0:
      if min_max_dist * deg_multi < 1 and max_cm <= 5 and cm / elp < .75 :
         meteor_yn = "no"
         bad_items.append("short distance, many gaps, low cm")

   if meteor_yn == "Y" and final == 1:
      gap_result = gap_test(object)
      if gap_result == 0:
         meteor_yn = "no"
         obj_class = "plane"
         bad_items.append("gap test failed.")
      if max_cm - elp < -30:
         meteor_yn = "no"
         obj_class = "plane"
         bad_items.append("to many elp frames compared to cm.")
      object['report']['gap_result'] = gap_result



   if len(bad_items) >= 1:
      meteor_yn = "no"
      if obj_class == 'meteor':
         obj_class = "not sure"

   if meteor_yn == "no":
      meteory_yn = "no"
   else: 
      meteory_yn = "Y"
      obj_class = "meteor"


   # create meteor 'like' score 
   score = 0
   if meteor_yn == "Y":
      avg_line_res = poly_fit(object) 
   else:
      avg_line_res = 0

   if avg_line_res > 2.5:
      meteor_yn = "no"
      obj_class = "noise"
      bad_items.append("bad average line res " + str(avg_line_res))

   if max_cm == elp == len(object['ofns']):
      score = score + 1
   if dir_test_perc == 2:
      score = score + 1
   if max_cm >= 5:
      score = score + 1
   if avg_line_res <= 1:
      score = score + 1
   if ang_vel > 2:
      score = score + 1
   if obj_class == "meteor":
      score = score + 5
   else:
      score = score - 3
   

  
   object['report'] = {}
   object['report']['angular_sep'] = min_max_dist * deg_multi 
   object['report']['angular_vel'] = (dist_per_elp * deg_multi) * 25
   object['report']['elp'] = elp
   object['report']['min_max_dist'] = min_max_dist
   object['report']['dist_per_elp'] = dist_per_elp
   object['report']['moving'] = moving
   object['report']['dir_test_perc'] = dir_test_perc
   object['report']['max_cm'] = max_cm
   object['report']['elp_max_cm'] = elp_max_cm
   object['report']['max_fns'] = len(object['ofns']) - 1
   object['report']['neg_perc'] = neg_perc
   object['report']['avg_line_res'] = avg_line_res 
   object['report']['obj_class'] = obj_class 
   object['report']['meteor_yn'] = meteor_yn
   object['report']['bad_items'] = bad_items 
   object['report']['x_dir_mod'] = x_dir_mod
   object['report']['y_dir_mod'] = y_dir_mod
   object['report']['score'] = score 

   return(object)

def calc_obj_dist(obj1, obj2):
   x1,y1,w1,h1 = obj1
   x2,y2,w2,h2 = obj2
   pts1 = []
   pts2 = []
   pts1.append((x1,y1))
   pts1.append((x1+w1,y1))
   pts1.append((x1,y1+h1))
   pts1.append((x1+w1,y1+h1))
   pts1.append((x1+int(w1/2),y1+int(h1/2)))

   pts2.append((x2,y2))
   pts2.append((x2+w2,y2))
   pts2.append((x2,y2+h2))
   pts2.append((x2+w2,y2+h2))
   pts2.append((x2+int(w2/2),y2+int(h2/2)))
   all_dist = []
   for a,b in pts1:
      for d,e in pts2:

         dist = calc_dist((a,b),(d,e))
         all_dist.append(dist)

   min_dist = min(all_dist)
   return(min_dist) 

def find_object(objects, fn, cnt_x, cnt_y, cnt_w, cnt_h, intensity=0, hd=0, sd_multi=1, cnt_img=None):
   #if fn < 5:
   #   return(0, objects)
   if hd == 1:
      obj_dist_thresh = 20 
   else:
      obj_dist_thresh = 10

   center_x = cnt_x 
   center_y = cnt_y  

   found = 0
   max_obj = 0
   for obj in objects:
      if 'oxs' in objects[obj]:
         oxs = objects[obj]['oxs']
         oys = objects[obj]['oys']
         ows = objects[obj]['ows']
         ohs = objects[obj]['ohs']
         for oi in range(0, len(oxs)):
            hm = int(ohs[oi] / 2)
            wm = int(ows[oi] / 2)
            dist = calc_obj_dist((cnt_x,cnt_y,cnt_w,cnt_h),(oxs[oi], oys[oi], ows[oi], ohs[oi]))
            if dist < obj_dist_thresh:
               found = 1
               found_obj = obj
      if obj > max_obj:
         max_obj = obj
   if found == 0:
      obj_id = max_obj + 1
      objects[obj_id] = {}
      objects[obj_id]['obj_id'] = obj_id
      objects[obj_id]['ofns'] = []
      objects[obj_id]['oxs'] = []
      objects[obj_id]['oys'] = []
      objects[obj_id]['ows'] = []
      objects[obj_id]['ohs'] = []
      objects[obj_id]['oint'] = []
      objects[obj_id]['ofns'].append(fn)
      objects[obj_id]['oxs'].append(center_x)
      objects[obj_id]['oys'].append(center_y)
      objects[obj_id]['ows'].append(cnt_w)
      objects[obj_id]['ohs'].append(cnt_h)
      objects[obj_id]['oint'].append(intensity)
      found_obj = obj_id
   if found == 1:
      if objects[found_obj]['report']['obj_class'] == "meteor":
         # only add if the intensity is positive and the forward motion compared to the last highest FM is greater. 
         fm_last = calc_dist((objects[found_obj]['oxs'][0],objects[found_obj]['oys'][0]), (objects[found_obj]['oxs'][-1],objects[found_obj]['oys'][-1]))
         fm_this = calc_dist((objects[found_obj]['oxs'][0],objects[found_obj]['oys'][0]), (center_x, center_y))
         fm = fm_this - fm_last
         if intensity > 10 and fm > 0:
            objects[found_obj]['ofns'].append(fn)
            objects[found_obj]['oxs'].append(center_x)
            objects[found_obj]['oys'].append(center_y)
            objects[found_obj]['ows'].append(cnt_w)
            objects[found_obj]['ohs'].append(cnt_h)
            objects[found_obj]['oint'].append(intensity)

      else:
         objects[found_obj]['ofns'].append(fn)
         objects[found_obj]['oxs'].append(center_x)
         objects[found_obj]['oys'].append(center_y)
         objects[found_obj]['ows'].append(cnt_w)
         objects[found_obj]['ohs'].append(cnt_h)
         objects[found_obj]['oint'].append(intensity)

   #objects[found_obj] = clean_object(objects[found_obj])
   objects[found_obj] = analyze_object(objects[found_obj], hd, sd_multi, 1)
   if objects[found_obj]['report']['meteor_yn'] == 'Y':
      max_int = max(objects[found_obj]['oint'])
      if max_int > 25000:
         objects[found_obj]['report']['obj_class'] = "fireball"

   return(found_obj, objects)

def clean_object(obj):
   # Remove erroneous frames from end of object if they exist. 
   print("clean")

def meteor_dir_test(fxs,fys):
   fx = fxs[0]
   fy = fys[0]
   lx = fxs[-1]
   ly = fys[-1]
   fdir_x = lx - fx 
   fdir_y = ly - fy

   if fdir_x < 0:
      fx_dir_mod = 1
   else:
      fx_dir_mod = -1
   if fdir_y < 0:
      fy_dir_mod = 1
   else:
      fy_dir_mod = -1


   match = 0
   nomatch = 0

   for i in range(0,len(fxs)):
      x = fxs[i]
      y = fys[i]
      dir_x = x - fx 
      dir_y = y - fy
      if dir_x < 0:
         x_dir_mod = 1
      else:
         x_dir_mod = -1
      if dir_y < 0:
         y_dir_mod = 1
      else:
         y_dir_mod = -1

      if x_dir_mod == fx_dir_mod :
         match = match + 1
      else:
         nomatch = nomatch + 1

      if y_dir_mod == fy_dir_mod :
         match = match + 1
      else:
         nomatch = nomatch + 1

 
   if len(fxs) > 0: 
      perc = match / len(fxs)
   else:
      perc = 0
   #print("DIR TEST PERC:", nomatch, match, perc)
   return(perc)

def meteor_dir(fx,fy,lx,ly):
   # positive x means right to left (leading edge = lowest x value)
   # negative x means left to right (leading edge = greatest x value)
   # positive y means down to up (leading edge = greatest y value)
   # negative y means left to right (leading edge = lowest y value)
   dir_x = lx - fx 
   dir_y = ly - fy
   if dir_x < 0:
      x_dir_mod = 1
   else:
      x_dir_mod = -1
   if dir_y < 0:
      y_dir_mod = 1
   else:
      y_dir_mod = -1
   return(x_dir_mod, y_dir_mod)


def one_dir_test(object):
   last_x = None
   last_x_dir_mod = None
   first_x = object['oxs'][0]
   first_y = object['oys'][0]
   xerrs = 0
   yerrs = 0
   for i in range(0,len(object['oxs'])):
      fn = object['ofns'][i]
      x = object['oxs'][i]
      y = object['oys'][i]
      if last_x is not None:
         dir_x = first_x - x 
         dir_y = first_y - y
         if dir_x < 0:
            x_dir_mod = 1
         else:
            x_dir_mod = -1
         if dir_y < 0:
            y_dir_mod = 1
         else:
            y_dir_mod = -1
         if last_x_dir_mod is not None:
            if x_dir_mod != last_x_dir_mod:
               xerrs = xerrs + 1
            if y_dir_mod != last_y_dir_mod:
               yerrs = yerrs + 1

         last_x_dir_mod = x_dir_mod
         last_y_dir_mod = y_dir_mod
      last_x = x 
      last_y = y
   dir_mod_errs = xerrs + yerrs
   dir_mod_err_perc = dir_mod_errs / len(object['oxs'])
   if dir_mod_errs == 0:
      return(1)
   if dir_mod_err_perc > .2:
      return(0)
   else:
      return(1)

def dist_test(object):
   mn_x = min(object['oxs'])
   mn_y = min(object['oys'])
   mx_x = max(object['oxs'])
   mx_y = max(object['oys'])
   dist = calc_dist((mn_x, mn_y), (mx_x,mx_y))
   if dist < 5:
      return(0)
   else:
      return(1)

def gap_test(object):
   ofns = object['ofns']
   if "oid" in object:
      oid = object[oid]
   else:
      oid = "no object id"
   last_fn = None
   cons = 0
   gaps = 0
   gap_events = 0
   for fn in ofns:
      fn = int(fn)
      if last_fn is not None:

         if last_fn == fn:
            extra = 1
         elif last_fn + 1 == fn or last_fn + 2 == fn or last_fn + 3 == fn:
            cons = cons + 1
         else:
            gaps = gaps + (fn - last_fn)
            gap_events = gap_events + 1
      last_fn = fn
   elp_frames = int(ofns[-1]) - int(ofns[0])
   if cons > 0:
      gap_to_cm_ratio = gaps / cons
   else:
      gap_to_cm_ratio = 1


   if elp_frames > 0:
      gap_to_elp_ratio = gaps / elp_frames
   else:
      gap_to_elp_ratio = 1


   if cons < 3:
      #print("CONS MONTION TOO LOW!")
      return(0)

   #print("GAP TEST:", oid, ofns)
   #print("GAP TEST:", gap_events, gaps, cons, elp_frames, gap_to_cm_ratio, gap_to_elp_ratio)

   if gap_to_cm_ratio > .2 and gap_to_elp_ratio > .2 or (gaps == 0 and gap_events == 0):
      #print("GAP TEST GOOD!")
      return(1)
   else:
      print("GAP TEST FAILED!", gap_to_cm_ratio, gap_to_elp_ratio)
      return(0)


def make_metframes(meteor_objects):
   ofns = meteor_objects[0]['ofns']
   oxs = meteor_objects[0]['oxs']
   oys = meteor_objects[0]['oys']
   metframes = {}
   i = 0
   for fn in ofns:
      ifn = int(fn)
      if fn not in metframes and ifn not in metframes:
         metframes[ifn] = {}
         metframes[ifn]['xs'] = []
         metframes[ifn]['ys'] = []
         metframes[ifn]['ws'] = []
         metframes[ifn]['hs'] = []
      metframes[ifn]['xs'].append(oxs[i])
      metframes[ifn]['ys'].append(oys[i])

      i = i + 1
   return(metframes)

def show_video(frames, meteor_objects, metframes):
   # SHOW FRAMES
   fn = 0


   fn = 0
   crop_size = 100
   show_frames = []
   show_spot = "tr"
   for frame in frames:
      if show_spot == "tl":
         show_y1 = 5
         show_y2 = 5 + crop_size * 2
         show_x1 = 5
         show_x2 = 5 + crop_size * 2
      if show_spot == "tr":
         show_y1 = 5
         show_y2 = 5 + crop_size * 2
         show_x1 = 1280 - (crop_size * 2) - 5
         show_x2 = 1280 -5

      show_frame = frame.copy()
      cnt_img = np.zeros((crop_size*2,crop_size*2,3),dtype=np.uint8)
      if fn in metframes:
         mx = int(np.mean(metframes[fn]['xs']))
         my = int(np.mean(metframes[fn]['ys']))
         if "blob_x" in metframes[fn]:
            blob_x = metframes[fn]['blob_x']
            blob_y = metframes[fn]['blob_y']
         else:
            blob_x = mx 
            blob_y = my 
         cx1,cy1,cx2,cy2= bound_cnt(blob_x,blob_y,frame.shape[1],frame.shape[0], 100)
         #print(cx1, cx2, cy1, cy2)
         cnt_img = frame[cy1:cy2,cx1:cx2]
         cnt_h, cnt_w = cnt_img.shape[:2]
         if show_spot == "tl":
            show_y1 = 5
            show_y2 = 5 + cnt_h
            show_x1 = 5
            show_x2 = 5 + cnt_w
         if show_spot == "tr":
            show_y1 = 5
            show_y2 = 5 + cnt_h
            show_x1 = 1280 - (cnt_w ) - 5
            show_x2 = 1280 -5
         #cv2.circle(show_frame,(blob_x,blob_y), 1, (0,0,255), 1)
         cv2.rectangle(show_frame, (blob_x-crop_size, blob_y-crop_size), (blob_x+ crop_size, blob_y + crop_size), (255, 255, 255), 1)
         show_frame = cv2.resize(show_frame, (1280,720))

      else:
         show_frame = cv2.resize(show_frame, (1280,720))

      show_frame[show_y1:show_y2,show_x1:show_x2] = cnt_img
      show_frames.append(show_frame)
      desc = str(fn)
      fn = fn + 1
   return(show_frames)

def sort_metframes(metframes):
   new_metframes = {}
   fns = []
   for fn in metframes:
      fns.append(int(fn))
   for fn in sorted(fns):
      fn = int(fn)
      if fn in metframes:
         new_metframes[fn] = metframes[fn]
   return(new_metframes)


def smooth_metframes(metframes, gray_frames):
   # first fill in any missing frames
   first_fn = None
   for fn in metframes:
      if first_fn is None:
         first_fn = fn
         first_ax = np.mean(metframes[fn]['xs'])
         first_ay = np.mean(metframes[fn]['ys'])
      last_fn = fn
      last_ax = np.mean(metframes[fn]['xs'])
      last_ay = np.mean(metframes[fn]['ys'])

   x_dir_mod, y_dir_mod = meteor_dir(first_ax, first_ay, last_ax, last_ay)
   print("X DIR, Y DIR", x_dir_mod, y_dir_mod)

   # determine seg lens
   xsegs = []
   ysegs = []
   last_ax = None
   for i in range (first_fn, last_fn):
      if i in metframes:
         ax = np.mean(metframes[i]['xs'])
         ay = np.mean(metframes[i]['ys'])
         if last_ax is not None:
            xsegs.append(ax-last_ax)
            ysegs.append(ay-last_ay)
         last_ax = ax
         last_ay = ay

   print(xsegs)
   print(ysegs)
   avg_x_seg = int(np.median(xsegs))
   avg_y_seg = int(np.median(ysegs))
   print("FIRST/LAST:", first_fn, last_fn)
   print("AVG SEGS:", avg_x_seg, avg_y_seg)

   for i in range (first_fn, last_fn):
      if i in metframes:
         if x_dir_mod == 1:
            ax = np.min(metframes[i]['xs'])
         else:
            ax = np.max(metframes[i]['xs'])
         ay = np.mean(metframes[i]['ys'])

      if i not in metframes:
         print("ADD NEW METFRMAE FOPR FN:", i)
         metframes[i] = {}
         print(i, last_ax, avg_x_seg)
         est_x = int(last_ax + avg_x_seg)
         est_y = int(last_ay + avg_y_seg)
         ax = est_x
         ay = est_y

         metframes[i]['xs'] = [] 
         metframes[i]['ys'] = []
         #metframes[i]['xs'].append(est_x)
         #metframes[i]['ys'].append(est_y)
         metframes[i]['xs'].append(blob_x)
         metframes[i]['ys'].append(blob_y)
      else:
         print("METFRAMES FOR FN already exists:", i)
      blob_x, blob_y, max_val, blob_w, blob_h = find_blob_center(i, gray_frames[i],ax,ay,20, x_dir_mod, y_dir_mod)
      metframes[i]['blob_x'] = blob_x
      metframes[i]['blob_y'] = blob_y
      last_ax = ax
      last_ay = ay
   metframes = sort_metframes(metframes)
   metframes,seg_diff,xs,ys = comp_seg_dist(metframes, frames)

   cap = int(len(metframes) / 3) 
   med_seg_len = np.median(seg_diff[0:cap])
   m,b = best_fit_slope_and_intercept(xs,ys)

   first_frame = frames[0].copy()

   metconf = {}
   metconf['first_frame'] = first_frame
   metconf['fx'] = xs[0] 
   metconf['fy'] = ys[0] 
   metconf['med_seg_len'] = med_seg_len 
   metconf['m'] = m
   metconf['b'] = b
   metconf['x_dir_mod'] = x_dir_mod
   metconf['y_dir_mod'] = y_dir_mod

   # ACL POLY
   #this_poly = np.zeros(shape=(2,), dtype=np.float64)
   #this_poly[0] = -.05
   #this_poly[1] = -.01
   #mode = 0
   #res = scipy.optimize.minimize(reduce_acl, this_poly, args=( metframes, metconf,frames,mode,show), method='Nelder-Mead')
   #poly = res['x']
   #metconf['med_seg_len'] = float(metconf['med_seg_len'] + poly[0])
   #metconf['acl_poly'] = poly[1]
   #metconf['acl_poly'] = 0


   fcc = 0
   for fn in metframes:
      frame = frames[fn].copy()
      subframe = cv2.subtract(frame,first_frame)
      if "blob_x" in metframes:
         blob_x = metframes[fn]['blob_x']
         blob_y = metframes[fn]['blob_y']
         cv2.circle(subframe,(blob_x,blob_y), 10, (255,255,255), 1)
         fcc = fcc + 1


   return(metframes)

def comp_seg_dist(metframes, frames):
   last_x = None
   first_x = None
   dist_from_start = 0 
   last_dist_from_start = 0 
   segs = []
   dist_from_start_segs = []
   seg_diff = []
   xs = []
   ys = []

   for fn in metframes:
      if "blob_x" in metframes[fn]:
         blob_x = metframes[fn]['blob_x']
         blob_y = metframes[fn]['blob_y']
      else:
         blob_x = np.median(metframes[fn]['xs'])
         blob_y = np.median(metframes[fn]['ys'])
      if first_x is None:
         first_x = metframes[fn]['blob_x']
         first_y = metframes[fn]['blob_y']

      if last_x is not None:
         seg_dist = calc_dist((blob_x, blob_y), (last_x,last_y)) 
         dist_from_start = calc_dist((first_x, first_y), (blob_x,blob_y)) 
         segs.append(seg_dist)
         dist_from_start_segs.append(dist_from_start)
         dist_from_start_seg = dist_from_start - last_dist_from_start
         seg_diff.append(dist_from_start_seg)
         metframes[fn]['dist_from_start'] = dist_from_start
         metframes[fn]['seg_dist'] = seg_dist
         metframes[fn]['seg_diff'] = dist_from_start_seg 
      xs.append(blob_x)
      ys.append(blob_y)
      last_x = blob_x
      last_y = blob_y
      last_dist_from_start = dist_from_start 

   return(metframes, seg_diff , xs, ys)

def est_frame_pos():
   # now make estimate of frames based on seg len and m,b variables
   fcc = 0
   acl_poly = 0

   for fn in metframes:
      if fcc < first_cap:
         med_seg_len = first_seg_len
         m = first_m
         b = first_b
      #else:
      #   med_seg_len = np.median(seg_diff[fcc-10:fcc])
         #m,b = best_fit_slope_and_intercept(xs[fcc-10:fcc],ys[fcc-10:fcc])

      est_x = int((first_x + (-1*x_dir_mod) * (med_seg_len*fcc)) + acl_poly * fcc)
      est_y = int((m*est_x)+b)
      metframes[fn]['est_x'] = est_x
      metframes[fn]['est_y'] = est_y

      fcc = fcc + 1
      show_img = frames[fn].copy()
      if "blob_x" in metframes[fn]:
         blob_x = metframes[fn]['blob_x']
         blob_y = metframes[fn]['blob_y']
         cv2.circle(show_img,(blob_x,blob_y), 1, (0,0,255), 1)
         cv2.circle(show_img,(est_x,est_y), 1, (0,255,255), 1)

         print(fn, metframes[fn]['est_x'], metframes[fn]['est_y'], metframes[fn]['blob_x'], metframes[fn]['blob_y'])
   exit()

def reduce_acl(this_poly, metframes,metconf,frames,mode=0,show=0,key_field = ""):
   xs = []
   ys = []
   err = []
   fcc = 0
   m_10 = metconf['m']
   b_10 = metconf['b']
   acl_poly = this_poly[1]

   key_x = key_field + "blob_x"
   key_y = key_field + "blob_y"

   if "acl_med_seg_len" in metconf:
      med_seg = (this_poly[0] + np.float64(metconf['acl_med_seg_len']))
   else:
      med_seg = (this_poly[0] + np.float64(metconf['med_seg_len']))

   for fn in metframes:
      est_res = 0
      ifn = int(fn) -1
      img = frames[ifn].copy()
      img = cv2.resize(img, (1920,1080))
      if len(img.shape) == 2:
         img_gray = img
         img = cv2.cvtColor(img,cv2.COLOR_GRAY2RGB)
      else:
         img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

      est_x = int( metconf['fx'] + (-1*metconf['x_dir_mod'] * (med_seg*fcc)) + (acl_poly * (fcc*fcc)) )
      est_y = int((m_10*est_x)+b_10)

      cv2.circle(img,(est_x,est_y), 4, (0,255,255), 1)
      print(metframes[fn])
      if "key_x" in metframes[fn]:
         bp_x = metframes[fn][key_x]
         bp_y = metframes[fn][key_y]
         cv2.circle(img,(bp_x,bp_y), 4, (0,0,255), 1)
         xs.append(bp_x)
         ys.append(bp_y)
      else:
         bp_x = int(np.median(metframes[fn]['xs']))
         bp_y = int(np.median(metframes[fn]['ys']))
         

      bp_est_res = calc_dist((bp_x,bp_y), (est_x,est_y))
      hd_est_res = bp_est_res

      if mode == 1:
         metframes[fn]['est_x'] = est_x
         metframes[fn]['est_y'] = est_y
         metframes[fn]['acl_res'] = hd_est_res

      err.append(hd_est_res)

      cv2.putText(img, str(med_seg) + " " + str(acl_poly),  (10,10), cv2.FONT_HERSHEY_SIMPLEX, .4, (0,0,255), 1)

      last_bp_x = bp_x
      last_bp_y = bp_y
      fcc = fcc + 1

      if len(xs) > 10:
         n_m_10,n_b_10 = best_fit_slope_and_intercept(xs[-10:],ys[-10:])
         if abs(n_b_10 - b_10) < 200:
            m_10 = n_m_10
            b_10 = n_b_10
   #print("ACL RES:", np.mean(err))
   if mode == 0:
      return(np.mean(err))
   else:
      return(np.mean(err), metframes)

# Notes:
# Pass in video file to get a detection and reduction

def flex_detect(video_file):
   hd_datetime, hd_cam, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(video_file)
   motion_objects, motion_frames = detect_meteor_in_clip(video_file, None, 0)
   print(motion_objects)

def flex_detect_old(video_file):
   station_id = get_station_id(video_file)
   hd_datetime, hd_cam, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(video_file)
   possible_cal_files = get_cal_params(video_file, station_id)
   #json_conf = load_json_conf(station_id)
   frames = load_video_frames(video_file, json_conf, 0, 0, [], 0)
   gray_frames = make_gray_frames(frames)
   detect_info = {}
   objects = {}

   json_file = video_file.replace(".mp4", ".json")
   manual_file = json_file.replace(".json", "-man.json")
   if cfe(manual_file) == 1:
      manual_fixes = load_json_file(manual_file)
   else:
      manual_fixes = {}
      manual_fixes['fixes'] = []

   if cfe(json_file) == 0:
      bp_frame_data, subframes = bp_detect(gray_frames,video_file)
      cnt_frame_data = detect_motion_in_frames(gray_frames, video_file)

      detect_info['bp_frame_data'] = bp_frame_data
      detect_info['cnt_frame_data'] = cnt_frame_data
      save_json_file(json_file, detect_info)
   else:
      detect_info = load_json_file(json_file)
      bp_frame_data = detect_info['bp_frame_data']
      cnt_frame_data = detect_info['cnt_frame_data']


   objects = find_cnt_objects(cnt_frame_data, objects)

   meteor_objects = []

   for obj in objects:
      if len(objects[obj]['oxs']) > 3:
         one_dir_test_result = one_dir_test(objects[obj])
         dist_test_result = dist_test(objects[obj])
         gap_test_result = gap_test(objects[obj])
         if one_dir_test_result == 1 and dist_test_result == 1 and gap_test_result == 1:
            print(obj, objects[obj])
            meteor_objects.append(objects[obj])

      if len(meteor_objects) == 0:
         print("No meteor objects.")
         for obj in objects:
            print(obj, objects[obj])


   metframes = make_metframes(meteor_objects )
   metframes = smooth_metframes(metframes, gray_frames)

   hdm_x = 1920 / 1280 
   hdm_y = 1080 / 720
   # apply manual corects
   for fix in manual_fixes['fixes']:
      fix_fn = fix['fn']  
      fix_x = int(fix['x'] * hdm_x)
      fix_y = int(fix['y'] * hdm_y)
 

      metframes[fix_fn]['blob_x'] = fix_x
      metframes[fix_fn]['blob_y'] = fix_y
      print("Fixing ", fix_fn)


   print("START METFRAMES", len(metframes))
   for fn in metframes:
      print(fn, metframes[fn])
   print("END METFRAMES")
   show_frames = show_video(frames, meteor_objects, metframes)
   marked_video_file = video_file.replace(".mp4", "-pub.mp4")
   remaster(show_frames, marked_video_file, station_id,meteor_objects[0])

def fast_check_events(sum_vals, max_vals, subframes):
   events = []
   event = []
   event_info = []
   events_info = []
   cm = 0
   nomo = 0
   i = 0
   #med_sum = np.median(sum_vals[0:10])
   #med_max = np.median(max_vals[0:10])
   med_sum = np.median(sum_vals)
   med_max = np.median(max_vals)
   median_frame = cv2.convertScaleAbs(np.median(np.array(subframes), axis=0))
   if subframes[0].shape[1] == 1920:
      hd = 1
      sd_multi = 1
   else:
      hd = 0
      sd_multi = 1920 / subframes[0].shape[1]

   for sum_val in sum_vals:
      
      #max_val = max_vals[i]
      subframe = subframes[i]
      subframe = cv2.subtract(subframe, median_frame)
      min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(subframe)
      print(i, med_sum, med_max, sum_val , max_val)
      if sum_val > med_sum * 2 or max_val > med_max * 2:
         min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(subframe)
         desc = str(i)
        
         if max_val > 10:
            #cv2.putText(subframe, str(desc),  (10,10), cv2.FONT_HERSHEY_SIMPLEX, .3, (255, 255, 255), 1)
            event_info.append((sum_val, max_val, mx, my))
            event.append(i)
            cm = cm + 1
            nomo = 0
         else:
            nomo = nomo + 1
      else:
         nomo = nomo + 1
      if cm > 2 and nomo > 5:
         events.append(event)
         events_info.append(event_info)
         event = []
         event_info = []
         cm = 0
      elif nomo > 5:
         event = []
         event_info = []
         cm = 0

      if show == 1:
         cv2.circle(subframe,(mx,my), 10, (255,0,0), 1)
         cv2.imshow('pepe', subframe)
         cv2.waitKey(70)

      i = i + 1

   if show == 1:
      cv2.destroyWindow('pepe')

   if len(event) >= 3:
      events.append(event)
      events_info.append(event_info)

   print("TOTAL EVENTS:", len(events))
   filtered_events = []
   filtered_info = []
   i = 0
   for ev in events:
      max_cm = calc_cm_for_event(ev)
      if max_cm >= 2:
         print("GOOD EVENT:", max_cm, ev)
         filtered_events.append(ev)
         filtered_info.append(events_info[i])
      else:
         print("FILTERED:", max_cm, ev)
         print("FILTERED:", events_info[i])
      i = i + 1
   print("FILTERED EVENTS:", len(filtered_events))
   events = filtered_events
   events_info = filtered_info

   i = 0
   objects = {}
   for event in events:
      ev_z = event[0]
      object = None
      fc = 0
      for evi in events_info[i]:
         sv, mv, mx, my = evi
         fn = event[fc]
         object, objects = find_object(objects, fn,mx, my, 5, 5, mv, hd, sd_multi)
         #print("OBJECT:", fn, object, objects[object])
         #if 500 <= ev_z <= 700:
         fc = fc + 1
      i = i + 1

   for obj in objects:
      object = objects[obj] 
      objects[obj] = analyze_object_final(object, hd=0, sd_multi=1)

   pos_meteors = {}
   mc = 1
   for object in objects:
      if objects[object]['report']['meteor_yn'] == "Y":
         pos_meteors[mc] = objects[object]
         mc = mc + 1
      else:
         print("NON METEOR FN:", object, objects[object]['ofns'])
         print("NON METEOR XS:", object, objects[object]['oxs'])
         print("NON METEOR YS:", object, objects[object]['oys'])
         print("NON METEOR REPT:", object, objects[object]['report'])

   return(events, pos_meteors)

def calc_cm_for_event(event):
   cm = 0
   max_cm = 0
   last_fn = None
   for fn in event:
      if last_fn is not None:
         if last_fn + 1 == fn :
            cm = cm + 1
         else:
            if cm > max_cm :
               max_cm = cm + 1
            else:
               cm = 0
      last_fn = fn
   if cm > max_cm:
      max_cm = cm + 1
   return(max_cm)
   

def quick_scan(video_file, old_meteor = 0):
   # 3 main parts
   # 1st scan entire clip for 'bright events' evaluating just the sub pixels in the subtracted frame
   # 2nd any bright events that match a meteor profile are sliced out and contours are found and logged for each frame
   # contours are turned into objects and evaluated
   # 3rd for any objects that might be meteors, create a longer clip around the event (+/-50 frames)
   # and run motion detection on those frames locating the objects. 

   debug = 0
   if "mp4" not in video_file or cfe(video_file) == 0:
      print("BAD INPUT FILE:", video_file)
      return([])

   if "/mnt/ams2/meteors" in video_file:
      rescan = 1
   else:
      rescan = 0
   if rescan == 1:
      # Make sure this file is not already in the archive.
      jsf = video_file.replace(".mp4", ".json")
      ojs = load_json_file(jsf)
      if "archive_file" in ojs:
         if cfe(ojs['archive_file']) == 1:
            print("File has been archived already!")
            #return()
 
   #PREP WORK

   # start performance timer
   start_time = time.time()

   # set stack file and skip if it alread exists. 
   stack_file = video_file.replace(".mp4", "-stacked.png")
   if cfe(stack_file) == 1 and old_meteor == 0:
      print("Already done this.")
      #return([])

   # setup variables
   cm = 0
   no_mo = 0
   event = []
   bright_events = []
   valid_events = []

   station_id = get_station_id(video_file)
   #json_conf = load_json_conf(station_id)
   hd_datetime, hd_cam, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(video_file)
   meteor_date = hd_y + "_" + hd_m + "_" + hd_d
   print("STATION:", station_id, video_file, start_time)

   # load the frames
   frames,color_frames,subframes,sum_vals,max_vals = load_frames_fast(video_file, json_conf, 0, 0, [], 0,[])
   elapsed_time = time.time() - start_time
   print("Total Frames:", len(frames))
   print("Loaded frames.", elapsed_time)
   # check to make sure frames were loaded
   if len(frames) < 5:
      print("bad input file.")
      return([])

   events,pos_meteors = fast_check_events(sum_vals, max_vals, subframes)
   for event in events:
      print("EVENT:", event)
   mc = 1
   print("POS METEORS:", len(pos_meteors))
   meteors = {}
   for meteor in pos_meteors:
      pos_meteors[meteor] = analyze_object_final(pos_meteors[meteor])
      pos_meteors[meteor] = analyze_object(pos_meteors[meteor], 1, 1)
      if pos_meteors[meteor]['report']['meteor_yn'] == 'Y':
         print("POS METEOR:", pos_meteors[meteor])
         meteors[mc] = pos_meteors[meteor]
         mc = mc + 1
      else:
         print("NON METEOR:", pos_meteors[meteor])
         
   pos_meteors = meteors
   print("POS:", len(pos_meteors))

   # Stack the frames and report the run time
   stacked_frame = stack_frames_fast(frames)
   cv2.imwrite(stack_file, stacked_frame) 
   elapsed_time = time.time() - start_time
   print("Stacked frames.", elapsed_time)
   
   # check time after frame load
   elapsed_time = time.time() - start_time
   print("Ending fast detection.", elapsed_time)

   if len(pos_meteors) == 0:
      elapsed_time = time.time() - start_time
      print("ELAPSED TIME:", elapsed_time)
      print("NO METEORS:", elapsed_time)
        
      if rescan == 1:
         log_import_errors(video_file, "No meteors detected in 1st scan.")
      return([])
   if len(pos_meteors) > 1:
      # we may have more than 1 possible meteor.
      if rescan == 1:
         print("more than 1 pos meteor.", rescan)
         log_import_errors(video_file, "More than 1 possible meteor detected.")
         return([])

   meteor_file = video_file.replace(".mp4", "-meteor.json")
   # Only continue if we made it past the easy / fast detection
   all_motion_objects = []
   for object in pos_meteors:
      pos_meteors[object] = merge_obj_frames(pos_meteors[object])
      start, end = buffered_start_end(pos_meteors[object]['ofns'][0],pos_meteors[object]['ofns'][-1], len(frames), 50)
      print("BUFFERED START:", start, end)
      if rescan == 0:
         trim_clip, trim_start, trim_end = make_trim_clip(video_file, start, end)
         t_start = start
         t_end = end
      else:
         trim_clip = video_file
         trim_start = start
         t_start = 0
         t_end = -1
      motion_objects, motion_frames = detect_meteor_in_clip(trim_clip, frames[t_start:t_end], t_start)
      for obj in motion_objects:
         all_motion_objects.append(motion_objects[obj])

   objects = []
   print("Ending detecting SD in clip.", len(all_motion_objects))
   for mo in all_motion_objects:
      mo = analyze_object_final(mo)
      
      if mo['report']['meteor_yn'] == "Y" or len(mo['ofns']) > 25:
         print("CONFIRMED OBJECTS:", mo)
         objects.append(mo)
      else:
         print("NON CONFIRMED OBJECTS:", mo)


   #objects = all_motion_objects

   elapsed_time = time.time() - start_time
   print("ELPASED TIME:", elapsed_time)
   print("OBJECTS IN PLAY:", len(objects))
   # Find the meteor like objects 
   meteors = []
   non_meteors = []

   for obj in objects:
      if len(obj['ofns']) > 2:
         print("merge obj frames:", obj)
         print("merge obj frames:", obj['ofns'])
         #obj = analyze_object_final(obj)
         #print("analyze final obj frames:", obj)
      if obj['report']['meteor_yn'] == "Y":
         print ("********************* METEOR *********************")
         print(obj['ofns'])
         meteors.append(obj)
      else:
         print("NON METEOR:", obj)
         non_meteors.append(obj)


   if len(meteors) == 0:
      print("No meteors found." )
      for non in non_meteors:
         print("NON:", non )
      detect_file = video_file.replace(".mp4", "-detect.json")
 
      if rescan == 0:
         save_json_file(detect_file, non_meteors)
      elapsed_time = time.time() - start_time
      print("ELPASED TIME:", elapsed_time)
      return([])
   if len(meteors) > 10:
      print("ERROR! Something like a bird.")
      non_meteors = meteors + non_meteors
      detect_file = video_file.replace(".mp4", "-detect.json")
      if rescan == 0:
         save_json_file(detect_file, non_meteors)
      return([])


   meteor_file = video_file.replace(".mp4", "-meteor.json")
   if rescan == 0:
      save_json_file(meteor_file, meteors)
   print("METEORS FOUND!", meteor_file)
   elapsed_time = time.time() - start_time
   print("ELPASED TIME:", elapsed_time)

   mjf = video_file.replace(".mp4", "-meteor.json")
   print("Process meteor.", mjf)

   old_meteor_dir = "/mnt/ams2/meteors/" + meteor_date + "/"
   if rescan == 1:
      for obj in meteors:
         mf = trim_clip.split("/")[-1]
         mf = mf.replace(".mp4", ".json")
         old_meteor_json_file = old_meteor_dir + mf
         md = load_json_file(old_meteor_json_file)
         obj['hd_trim'] = md['hd_trim']
         if "hd_video_file" in md:
            obj['hd_video_file'] = md['hd_video_file']
         if "hd_file" in md:
            obj['hd_video_file'] = md['hd_file']


         #if "hd_video_file" in md:
         #   obj['hd_video_file'] = md['hd_video_file']
         #   obj['hd_crop_file'] = md['hd_crop_file']
         #elif "hd_trim" in md:
         #   obj['hd_video_file'] = md['hd_trim']
         #   obj['hd_trim'] = md['hd_trim']
         #if obj['hd_trim'] != 0 :
         #   if "/mnt/ams2/HD" in obj['hd_video_file'] or "/mnt/ams2/HD" in obj['hd_trim']:
         #      new_dir = "/mnt/ams2/meteors/" + meteor_date + "/" 
         #      obj['hd_video_file'] = obj['hd_video_file'].replace("/mnt/ams2/HD/", new_dir)
         #      obj['hd_trim'] = obj['hd_trim'].replace("/mnt/ams2/HD/", new_dir)
             

         #obj['hd_crop_file'] = md['hd_crop_file']
         calib,cal_params = apply_calib(obj)
         obj['calib'] = calib
         obj['cal_params'] = cal_params 
         if obj['hd_trim'] == 0:
            print("Crap no hd_trim for this file.", obj['trim_clip'])
            fp = open("/mnt/ams2/meteors/import_errors.txt", "a")
            fp.write(str(obj['trim_clip']) + "," + str(obj['hd_trim'])+ "," + "SD & HD objects don't match\n")
            fp.close()


            return()
         else:
            new_json_file = sync_hd_sd_frames(obj)
         if new_json_file == 0:
            return(0)
        
         obj['new_json_file'] = new_json_file 
         save_old_style_meteor_json(old_meteor_json_file, obj, trim_clip )
         process_meteor_files(obj, meteor_date, video_file, rescan)
         print("VIDEO FILE:", video_file)
         print("OBJ:", obj)
      return(meteors)

   final_meteors = []

   for obj in meteors:
      old_scan = 0
      start = obj['ofns'][0]
      end = obj['ofns'][-1]
      # sync HD
      df = int ((end - start) / 25)
      hd_file, hd_trim,time_diff_sec, dur = find_hd_file_new(video_file, start, df, 1)
      print("START END:", start, end, df)
      print("HD TRIM:", hd_trim)
      if hd_trim is not None and rescan == 0:
         print("HD SYNC:", hd_file, hd_trim, time_diff_sec, dur, df)
         # Make the HD stack file too.  And then sync the HD to SD video file.
         obj['hd_trim'] = hd_trim
         obj['hd_video_file'] = hd_file
         if hd_trim != 0 and cfe(hd_trim) == 1:
            #hd_crop, crop_box = crop_hd(obj, frames[0])
            #hd_crop_objects,hd_crop_frames = detect_meteor_in_clip(hd_crop, None, start, crop_box[0], crop_box[1])
            #refine_points(hd_crop, hd_crop_frames )
            #obj['hd_crop_file'] = hd_crop
            #obj['crop_box'] = crop_box
            #obj['hd_crop_objects'] = hd_crop_objects
            if rescan == 0:
               restack(obj['hd_trim'])
               print("mv " + hd_trim + " " + old_meteor_dir)
               os.system("mv " + hd_trim + " " + old_meteor_dir)
               #print("mv " + hd_crop + " " + old_meteor_dir)
               #os.system("mv " + hd_crop + " " + old_meteor_dir)
         else:
            obj['hd_trim'] = 0
            obj['hd_video_file'] = 0

      
      # restack the SD file
      restack(obj['trim_clip'])
      process_meteor_files(obj, meteor_date, video_file, rescan)
      print("VIDEO FILE:", video_file)
      print("OBJ:", obj)
      final_meteors.append(obj)

   # do this as a separate process.
   #confirm_meteor(mjf)

   for obj in final_meteors:
      print(obj)

   return([])

def restack(file):

   if cfe(file) == 1:
      frames,color_frames,subframes,sum_vals,max_vals = load_frames_fast(file, json_conf, 0, 0, [], 0,[])
      print("RESTACK: ", file, len(frames))
      stack = stack_frames_fast(frames, 1)
      stack_file = file.replace(".mp4", "-stacked.png")
      print(stack.shape)
      cv2.imwrite(stack_file, stack)

def log_import_errors(video_file, message):
   fn = video_file.split("/")[-1]
   day = fn[0:10]
   log_file = "/mnt/ams2/meteors/" + day + "/import_errors.json"
   if cfe(log_file) == 1:
      log = load_json_file(log_file)
      if "import_errors.json" in log:
         log = {}
   else:
      log = {}
   log[video_file] = message
   save_json_file(log_file, log)

def only_meteors(objects):
   meteors = []
   for obj in objects:
      if objects[obj]['report']['meteor_yn'] == "Y":
         meteors.append(objects[obj])
   return(meteors)

def refine_sync(sync_diff, sd_object, hd_object, hd_frame, sd_frame):
   max_err_x = 9999
   max_err_y = 9999
   sync_obj = {}

   print("SD FNS:", sd_object['ofns'])
   print("HD FNS:", hd_object['ofns'])
   hdm_x = hd_frame.shape[1] / sd_frame.shape[1]
   hdm_y = hd_frame.shape[0] / sd_frame.shape[0]

   # for the first SD frame, figure out which HD frame has the least error.

   for i in range(0,len(sd_object['ofns'])):
      sd_fn = sd_object['ofns'][i]
      sync_obj[sd_fn] = {}
      sync_obj[sd_fn]['err'] = 9999
      sd_x = sd_object['oxs'][i]
      sd_y = sd_object['oys'][i]
      up_sd_x = int(sd_x * hdm_x)
      up_sd_y = int(sd_y * hdm_y)
      for j in range(0,len(hd_object['ofns'])):

         hd_x = hd_object['oxs'][j]
         hd_fn = hd_object['ofns'][j]
         hd_y = hd_object['oys'][j]
         err_x = abs(up_sd_x - hd_x)
         err_y = abs(up_sd_y - hd_y)
         err = err_x + err_y
         if err < sync_obj[sd_fn]['err']:
            sync_obj[sd_fn]['hd_fn'] = hd_fn
            sync_obj[sd_fn]['err'] = err 
         
       
         print(sd_fn, hd_fn, up_sd_x, hd_x, up_sd_y, up_sd_x, err_x, err_y)

   i = 0
   for sync in sorted(sync_obj.keys()):
      if i == 0:
         hd_sd_sync = sync_obj[sync]['hd_fn'] - sync
      print(sync, sync_obj[sync])
      i = i + 1

   return(hd_sd_sync)

def sync_hd_sd_frames(obj):
   orig_obj = obj
   print("SYNC FRAMES!")
   print("HD TRIM:", obj['hd_trim'])
   print("SD TRIM:", obj['trim_clip'])
   sd_trim_num = get_trim_num(obj['trim_clip'])
   first_sd_frame = obj['ofns'][0]
   sd_frames,sd_color_frames,sd_subframes,sd_sum_vals,sd_max_vals = load_frames_fast(obj['trim_clip'], json_conf, 0, 0, [], 1,[])
   hd_frames,hd_color_frames,hd_subframes,hd_sum_vals,hd_max_vals = load_frames_fast(obj['hd_trim'], json_conf, 0, 0, [], 1,[])

   hd_objects,trash = detect_meteor_in_clip(obj['hd_trim'], hd_frames, 0, 0, 0)
   sd_objects,trash = detect_meteor_in_clip(obj['trim_clip'], sd_frames, 0, 0,0)
   all = hd_objects
   hdm_x = hd_frames[0].shape[1] / sd_frames[0].shape[1] 
   hdm_y = hd_frames[0].shape[0] / sd_frames[0].shape[0] 
   #sd_objects,hd_objects= pair_hd_sd_meteors(sd_objects, hd_objects, hdm_x, hdm_y)

   hd_objects = only_meteors(hd_objects)
   sd_objects = only_meteors(sd_objects)
   print("SD:", sd_objects)
   print("HD:", hd_objects )


   if len(hd_objects) == 0:
      for hdo in all:
         print(all[hdo])


   if len(hd_objects) == len(sd_objects) and len(sd_objects) > 0:
      print("We have a match!") 
      sd_ind = sd_objects[0]['ofns'][0]
      hd_ind = hd_objects[0]['ofns'][0]
      sync_diff = hd_ind - sd_ind
      sync_diff = refine_sync(sync_diff, sd_objects[0], hd_objects[0], hd_frames[0], sd_frames[0])

      sdf = []
      hdf = []
      for i in range(0, len(hd_objects[0]['ofns'])):
         hd_fn = hd_objects[0]['ofns'][i]
         sd_fn = hd_fn - sync_diff 
         print("SD,HD SYNC:", sd_fn, hd_fn)
         sd_frame = sd_frames[sd_fn]
         hd_frame = hd_frames[hd_fn]
         sdf.append(sd_fn)
         hdf.append(hd_fn)
         hd_frame = cv2.resize(hd_frame, (0,0),fx=.25, fy=.25)
   else:
      print("Problem sd and hd events don't match up perfectly...", len(sd_objects), len(hd_objects))
      #fp = open("/mnt/ams2/meteors/import_errors.txt", "a")
      #fp.write(orig_obj['trim_clip'] + "," + obj['hd_trim']+ "," + "SD & HD objects don't match\n")
      #fp.close()
      log_import_errors(orig_obj['trim_clip'], "Problem with sd and hd events don't match perfectly.")
      show_objects(sd_objects, "SD")
      show_objects(hd_objects, "HD")
      print("SD AND HD EVENTS DON'T LINE UP PERFECT! need to fix!", len(sd_objects), len(hd_objects))
      return(0)

   buf_size = 20
   sd_bs,sd_be = buffered_start_end(sdf[0],sdf[-1], len(hd_frames), buf_size)
   if sd_bs == 0:
      buf_size = sdf[0]
   hd_bs,hd_be = buffered_start_end(hdf[0],hdf[-1], len(hd_frames), buf_size)

   (f_datetime, cam, f_date_str,fy,fm,fd, fh, fmin, fs) = convert_filename_to_date_cam(obj['trim_clip'])
   new_sd_trim_num = sdf[0] - buf_size + sd_trim_num
   extra_sec = new_sd_trim_num / 25

   start_trim_frame_time = f_datetime + datetime.timedelta(0,extra_sec)




   print("SD TRIM NUM OLD/NEW:", sd_trim_num, new_sd_trim_num)
   xxx = obj['trim_clip'].split("/")[-1]
   fnw = xxx.split("-trim")[0]
   #new_trim = '{0:04d}'.format(int(new_sd_trim_num)) 
   new_trim = new_sd_trim_num
   new_hd_file_name = "/mnt/ams2/matmp/" + fnw + "-trim" + str(new_trim) + "-HD.mp4"
   new_sd_file_name = "/mnt/ams2/matmp/" + fnw + "-trim" + str(new_trim) + "-SD.mp4"
   new_json_file_name = "/mnt/ams2/matmp/" + fnw + "-trim" + str(new_trim) + ".json"


   new_hd_frames = hd_frames[hd_bs:hd_be]
   new_sd_frames = sd_frames[sd_bs:sd_be]
   new_hd_color_frames = hd_color_frames[hd_bs:hd_be]
   new_sd_color_frames = sd_color_frames[sd_bs:sd_be]

   hd_objects,trash = detect_meteor_in_clip(new_hd_file_name, new_hd_frames, 0, 0)
   sd_objects,trash = detect_meteor_in_clip(new_sd_file_name, new_sd_frames, 0, 0)
   
  
   hd_meteors = []
   ftimes = []
   for obj in hd_objects:
      hd_objects[obj] = analyze_object_final(hd_objects[obj])
      hd_objects[obj] = analyze_object(hd_objects[obj], 1, 1)
      
      if hd_objects[obj]['report']['meteor_yn'] == 'Y':
         print(hd_objects[obj]['ofns'])
         print(hd_objects[obj]['report'])
         hd_meteors.append(hd_objects[obj])

   hdm_x = new_hd_frames[0].shape[1] / new_sd_frames[0].shape[1] 
   hdm_y = new_hd_frames[0].shape[0] / new_sd_frames[0].shape[0] 
   if len(hd_meteors) > 1:
      print("PAIR!")
      hd_meteors = pair_sd_hd_meteors(sd_objects, hd_objects, hdm_x, hdm_y)
   
   if len(hd_meteors) == 0:

      print("NO HD METEORS FOUND. FAIL OVER TO SD METEORS?")
      exit()
   elif len(hd_meteors) == 1:
      meteor_obj = hd_meteors[0]
      make_movie_from_frames(new_hd_color_frames, [0,len(new_hd_frames) - 1], new_hd_file_name, 0)
      make_movie_from_frames(new_sd_color_frames, [0,len(new_hd_frames) - 1], new_sd_file_name, 0)

      meteor_obj['calib'] = orig_obj['calib']
      meteor_obj['hd_trim'] = orig_obj['hd_trim']
      meteor_obj['trim_clip'] = orig_obj['trim_clip']
      meteor_obj['hd_file'] = new_hd_file_name 
      meteor_obj['sd_file'] = new_sd_file_name 
      meteor_obj['dt'] = start_trim_frame_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

      hdm_x = new_hd_frames[0].shape[1] / new_sd_frames[0].shape[1] 
      hdm_y = new_hd_frames[0].shape[0] / new_sd_frames[0].shape[0] 
      for i in range(0,len(meteor_obj['ofns'])):
         if "ftimes" not in meteor_obj:
            meteor_obj['ftimes'] = []
         fn = meteor_obj['ofns'][i]
         hd_x = meteor_obj['oxs'][i]
         hd_y = meteor_obj['oys'][i]

         extra_meteor_sec = fn /  25
         meteor_frame_time = start_trim_frame_time + datetime.timedelta(0,extra_meteor_sec)
         meteor_frame_time_str = meteor_frame_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
         meteor_obj['ftimes'].append(meteor_frame_time_str)
         ftimes.append(meteor_frame_time)
         print("METEOR FRAME TIME:", meteor_frame_time_str)

         print("HD FN", fn)
         hd_frame = new_hd_frames[fn]
         print("DEBUG:", len(new_sd_frames), fn)
         cx1,cy1,cx2,cy2= bound_cnt(hd_x,hd_y,new_hd_frames[0].shape[1],new_hd_frames[0].shape[0], 20)
         hd_cnt = new_hd_frames[fn][cy1:cy2,cx1:cx2]

         sd_x = int(hd_x / hdm_x)
         sd_y = int(hd_y / hdm_y)
         cx1,cy1,cx2,cy2= bound_cnt(sd_x,sd_y,new_sd_frames[0].shape[1],new_sd_frames[0].shape[0], 20)
         #sd_frame = new_sd_frames[fn]
         #sd_cnt = new_sd_frames[fn][cy1:cy2,cx1:cx2]

         #show_img = sd_frame 
         #cv2.rectangle(show_img, (cx1, cy1), (cx2, cy2), (255,255,255), 1, cv2.LINE_AA)


   else:
      print("MORE THAN ONE METEOR OBJECT! NOT COOL!")
      #fp = open("/mnt/ams2/meteors/import_errors.txt", "a")
      #fp.write(str(orig_obj['trim_clip']) + "," + str(orig_obj['hd_trim'])+ "," + "MORE THAN ONE METEOR OBJECT\n")
      #fp.close()
      log_import_errors(orig_obj['trim_clip'], "More than one meteor object.")
      return(0)
   meteor_obj['dur'] = (ftimes[-1] - ftimes[0]).total_seconds()
   meteor_obj['cal_params'] = orig_obj['cal_params'] 
   print("METEOR OBJ:", meteor_obj)
   new_json = save_new_style_meteor_json(meteor_obj, new_hd_file_name)
   save_json_file(new_json_file_name, new_json)
   move_to_archive(new_json_file_name)
   write_archive_index(fy,fm) 
   print(new_json_file_name)
   return(new_json_file_name)

def pair_hd_sd_meteors(sd_objects, hd_objects, hdm_x,hdm_y):
   matched_sd_meteor = []
   matched_hd_meteor = []
   last_x_err = 9999
   for hobj in hd_objects:
      if hd_objects[hobj]['report']['meteor_yn'] == 'Y':
         matched_hd_meteor = hd_objects[hobj]
         for sobj in sd_objects:
            if sd_objects[sobj]['report']['meteor_yn'] == 'Y':
               x_diff = int(sd_objects[sobj]['oxs'][0] * hdm_x) - hd_objects[hobj]['oxs'][0]
               print("XDIF:", x_diff)
               if x_diff < last_x_err:
                  matched_sd_meteor = sd_objects[sobj]
                  last_x_err = x_diff
   matches = []
   hd_matches = []
   matches.append(matched_sd_meteor)
   hd_matches.append(matched_hd_meteor)
   return([matches], [hd_matches] )

def pair_sd_hd_meteors(sd_objects, hd_objects, hdm_x,hdm_y):
   matched_hd_meteor = []
   last_x_err = 9999
   for sobj in sd_objects:
      if sd_objects[sobj]['report']['meteor_yn'] == 'Y':
         print("SD METEOR OBJECT:", sd_objects[sobj])
         for hobj in hd_objects:
            if hd_objects[hobj]['report']['meteor_yn'] == 'Y':
               print("HD METEOR OBJECT:", hd_objects[hobj])
               x_diff = int(sd_objects[sobj]['oxs'][0] * hdm_x) - hd_objects[hobj]['oxs'][0]
               print("XDIF:", x_diff)
               if x_diff < last_x_err:
                  matched_hd_meteor = hd_objects[hobj]
                  last_x_err = x_diff
 
   matches = []
   matches.append(matched_hd_meteor)
   return(matches)
               
      
   

def show_objects(objects, desc):
   for obj in objects:
      print(desc, "Object: ", obj)
      print(desc, "FNS:", obj['ofns'])   
      print(desc, "XS:", obj['oxs'])   
      print(desc, "YS:", obj['oys'])   
      print(desc, "WS:", obj['ows'])   
      print(desc, "HS:", obj['ohs'])   
      print(desc, "INTS:", obj['oint'])   
      for key in obj['report']:
         print("   ", desc, key, obj['report'][key])   

def old_detection_codes():
   exit()
   ############################################################################
   # DETECTION PHASE 2
   # For each meteor like object run motion detection on the frames containing the event

   # Loop over each possible meteor
   for object in meteors:   
      print("METEOR", object)
      # Determine start and end frames and then add 50 frames to either end (if they exist)
      start_fn = object['ofns'][0] - 50
      end_fn = object['ofns'][-1] + 50
      if start_fn < 0:
         start_fn = 0
      if end_fn > len(frames) - 1:
         end_fn = len(frames) - 1  

      # Detect motion contours in the frame set
      print("DETECTING MOTION CNTS", video_file)
      cnt_frames = detect_motion_in_frames(subframes[start_fn:end_fn], video_file, start_fn) 

      #for cnt in cnt_frames:
      #   print("CONTOUR:", cnt, cnt_frames[cnt])

      # DETECTION FINAL - PHASE 3
      print("DETECT PHASE 3!")
      # Determine the first and last frames that contain motion objects
      first_fn = None
      last_fn = 0
      for fn in cnt_frames:
         if len(cnt_frames[fn]['xs']) > 0:
            if first_fn is None:
               first_fn = fn 
            last_fn = fn 


      # Find the objects from the motion contours to make sure all of the contours belong to the meteor 
      
      final_objects = {} 
      print(cnt_frames)
      for xxx in cnt_frames:
         print(xxx, cnt_frames[xxx]) 


      final_objects = find_cnt_objects(cnt_frames, final_objects)
      real_meteors = {}

      for ooo in final_objects:
         print(ooo, final_objects[ooo])

      meteor_id = 1
      print("FIND MOTION CONTOURS!", final_objects)
      for obj in final_objects:

         final_objects[obj] = merge_obj_frames(final_objects[obj])

         if final_objects[obj]['report']['meteor_yn'] == 'Y':
            print("FINAL:", obj, final_objects[obj])
            
            real_meteors[meteor_id] = final_objects[obj]
            meteor_id = meteor_id + 1

      # check for missing frames inside the meteor start and end
      real_meteors = check_fix_missing_frames(real_meteors)

      meteor_crop_frames = {}
      # determine the brightest pixel point value and x,y position for each frame and save it in the object

      # determine the blob center x,y position and sum bg subtracted inensity value for each frame and save it in the object

      # determine the meteor's 'leading edge' x,y position and sum bg subtracted crop inensity value (based on bounded original CNT w,h) for each pixel and save it in the object

      # if there is just 1 meteor finish the job

      print("FINISH THE JOB!", real_meteors)

      for meteor_obj in real_meteors:
         bad_frames = []
         print("REAL METEOR:", meteor_obj, real_meteors[meteor_obj])
         # find the meteor movement direction:
         x_dir_mod,y_dir_mod = meteor_dir(real_meteors[meteor_obj]['oxs'][0], real_meteors[meteor_obj]['oys'][0], real_meteors[meteor_obj]['oxs'][-1], real_meteors[meteor_obj]['oys'][-1])

         meteor_crop_frames[meteor_obj] = []
         lc = 0
         if len(real_meteors[meteor_obj]['ofns']) != len(real_meteors[meteor_obj]['oxs']):
            print("BAD OBJECT: ", real_meteors[meteor_obj])
            return(0, "BAD OBJECT")
         print("RANGE:", 0, len(real_meteors[meteor_obj]['ofns'])-1)
         for jjj in range(0, len(real_meteors[meteor_obj]['ofns'])-1):
            bad = 0
            fn = real_meteors[meteor_obj]['ofns'][jjj]
            x = real_meteors[meteor_obj]['oxs'][jjj]
            y = real_meteors[meteor_obj]['oys'][jjj]
            w = real_meteors[meteor_obj]['ows'][jjj]
            h = real_meteors[meteor_obj]['ohs'][jjj]

            if w > h : 
               sz = int(w / 2)
            else:
               sz = int(h / 2)
            print("MAX SIZE IS:", sz ) 
            cx1,cy1,cx2,cy2= bound_cnt(x,y,frames[0].shape[1],frames[0].shape[0], sz)
            #print ("CONTOUR AREA:", cx1, cy1, cx2, cy2)
            show_frame = frames[fn]
           
            cnt_frame = frames[fn][cy1:cy2, cx1:cx2]
            cnt_bg = frames[fn-1][cy1:cy2, cx1:cx2]

            sub_cnt_frame = cv2.subtract(cnt_frame, cnt_bg)
            sum_val =cv2.sumElems(sub_cnt_frame)[0]
            cnt_val =cv2.sumElems(cnt_frame)[0]
            bg_val =cv2.sumElems(cnt_bg)[0]
            #print("INTESITY (BG, CNT, DIFF):", bg_val, cnt_val, sum_val)

            #print("SHAPE:", sub_cnt_frame.shape)

            sub_cnt_frame = cv2.resize(sub_cnt_frame, (0,0),fx=20, fy=20)
            min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(sub_cnt_frame)
            contours, rects= find_contours_in_frame(sub_cnt_frame, int(max_val/2))
            if len(contours) == 0:
               bad_frames.append(jjj)
               bad = 1
            if len(contours) > 0:
               contours = merge_contours(contours)

            cnt_rgb = cv2.cvtColor(sub_cnt_frame.copy(),cv2.COLOR_GRAY2RGB)
            desc = str(x_dir_mod) + "," + str(y_dir_mod)

            # x dir mod / y dir mod
            # -1 x is left to right, leading edge is right side of obj (x+w)
            # -1 y is top to down, leading edge is bottom side of obj (y+h)
            # +1 x is left to right, leading edge is right side of obj (x)
            # +1 y is top to down, leading edge is bottom side of obj (y)

            cv2.putText(cnt_rgb, str(desc),  (10,10), cv2.FONT_HERSHEY_SIMPLEX, .3, (255, 255, 255), 1)
            for x,y,w,h in contours:
               if x_dir_mod == 1:
                  leading_x = x 
               else:
                  leading_x = x + w 
               if y_dir_mod == 1:
                  leading_y = y 
               else:
                  leading_y =  y + h

               leading_edge_x_size = int(w / 2.5) 
               leading_edge_y_size = int(h / 2.5) 

               le_x1 = leading_x
               le_x2 = leading_x + (x_dir_mod*leading_edge_x_size)
               le_y1 = leading_y
               le_y2 = leading_y + (y_dir_mod*leading_edge_y_size)
               tm_y = sorted([le_y1,le_y2])
               tm_x = sorted([le_x1,le_x2])
               le_x1 = tm_x[0]
               le_x2 = tm_x[1]
               le_y1 = tm_y[0]
               le_y2 = tm_y[1]
               le_cnt = sub_cnt_frame[le_y1:le_y2,le_x1:le_x2]
               min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(le_cnt)
               #if le_cnt.shape[0] > 0 and le_cnt.shape[1] > 0:
               le_x = mx + (le_x1) 
               le_y = my + (le_y1) 
               cv2.circle(cnt_rgb,(le_x,le_y), 5, (255,0,0), 1)

               cv2.rectangle(cnt_rgb, (x, y), (x+w, y+h), (255,255,255), 1, cv2.LINE_AA) 
               cv2.rectangle(cnt_rgb, (leading_x, leading_y), (leading_x+(x_dir_mod*leading_edge_x_size), leading_y+(y_dir_mod*leading_edge_y_size)), (255,255,255), 1, cv2.LINE_AA) 

               if "leading_x" not in real_meteors[meteor_obj]:
                  real_meteors[meteor_obj]['leading_x'] = []
                  real_meteors[meteor_obj]['leading_y'] = []

               #print("LEADING X INFO: ", cx1, cy1, le_x, le_y)
               real_meteors[meteor_obj]['leading_x'].append(int((le_x / 20) + cx1))
               real_meteors[meteor_obj]['leading_y'].append(int((le_y / 20) + cy1))


            cv2.circle(cnt_rgb,(mx,my), 5, (255,255,255), 1)
            if bad == 1:
               cv2.putText(cnt_rgb, "bad frame",  (25,25), cv2.FONT_HERSHEY_SIMPLEX, .3, (255, 255, 255), 1)
           
            lc = lc + 1
      data_x = []
      data_y = []
      gdata_x = []
      gdata_y = []


      for id in real_meteors:
         meteor_obj = real_meteors[id]
         max_x = len(meteor_obj['ofns'])
         max_y = 0
         all_lx = []
         all_ly = []
         all_fn = []
         for i in range(0,len(meteor_obj['ofns'])-1):
            fn = meteor_obj['ofns'][i]
            if "leading_x" in meteor_obj:
               try:
                  lx = meteor_obj['leading_x'][i]
                  ly = meteor_obj['leading_y'][i]       
                  meteor_obj['no_leading_xy'] = 1
               except:
                  lx = meteor_obj['oxs'][i]
                  ly = meteor_obj['oys'][i]
               all_lx.append(lx)
               all_ly.append(ly)
               all_fn.append(fn)
            else:
               print("NO LEADING X FOUND FOR ", id, fn)


         for i in range(0,len(meteor_obj['ofns'])-1):
            fn = meteor_obj['ofns'][i]
            try:
               lx = meteor_obj['leading_x'][i]
               ly = meteor_obj['leading_y'][i]
            except:
               lx = meteor_obj['oxs'][i]
               ly = meteor_obj['oys'][i]
            gdata_x.append(lx)
            gdata_y.append(ly)
            lx1,ly1,lx2,ly2= bound_cnt(lx,ly,frames[0].shape[1],frames[0].shape[0], 30)
            tracker_cnt = color_frames[fn][ly1:ly2,lx1:lx2]
            tracker_bg = frames[0][ly1:ly2,lx1:lx2]

            tracker_cnt_gray = cv2.cvtColor(tracker_cnt, cv2.COLOR_BGR2GRAY)
            subtracker = cv2.subtract(tracker_cnt_gray, tracker_bg)
            sum_val =cv2.sumElems(subtracker)[0]
            data_y.append(sum_val)
            data_x.append(i)

            tracker_cnt = cv2.resize(tracker_cnt, (180,180))
            graph_x = 500 
            graph_y = 200 
            graph = custom_graph(data_x,data_y,max_x,max_y,graph_x,graph_y,"line")

            graph_xy = custom_graph(gdata_x,gdata_y,max(all_lx) + 10,max(all_ly)+10,300,300,"scatter")
            info = {}
            cf = color_frames[fn].copy()
            cv2.circle(cf,(lx,ly), 10, (255,255,255), 1) 
 
            custom_frame = make_custom_frame(cf,subframes[fn],tracker_cnt,graph, graph_xy, info)

            #graph = cv2.resize(graph, (150,500))
            cv2.line(tracker_cnt, (74,0), (74,149), (128,128,128), 1) 
            cv2.line(tracker_cnt, (0,74), (149,74), (128,128,128), 1) 

            #print("TRACKER SHAPE:", tracker_cnt.shape)
            show_frame = color_frames[fn]

            tr_y1 = color_frames[0].shape[0] - 5 - graph_y
            tr_y2 = tr_y1 + graph_y
            tr_x1 = 5
            tr_x2 = tr_x1 + graph_y

            gr_y1 = color_frames[0].shape[0] - 5 - graph_y
            gr_y2 = gr_y1 + graph_y

            gr_x1 = tr_x2 + 10 
            gr_x2 = gr_x1 + graph_x 


            #print("PLACEMENT:", tr_y1,tr_y2, tr_x1, tr_x2)

            #show_frame[tr_y1:tr_y2,tr_x1:tr_x2] = tracker_cnt 
            #show_frame[gr_y1:gr_y2,gr_x1:gr_x2] = graph 

            #print("LEAD:", fn,lx,ly)

            cv2.circle(show_frame,(lx,ly), 10, (255,255,255), 1)
            cv2.rectangle(show_frame, (tr_x1, tr_y1), (tr_x2, tr_y2), (255,255,255), 1, cv2.LINE_AA)

   # End of processing and meteor detection. 
   # Save data file, make trim clips
   # Apply calibration 
   # Upload / Register Meteor

      data_file = video_file.replace(".mp4", "-meteor.json")
      save_json_file(data_file, real_meteors)

   elapsed_time = time.time() - start_time
   print("Detected BP.", elapsed_time)
   bin_days = []
   bin_events = []
   bin_avgs = []
   bin_sums = []

   #for object in objects:
   #   for key in objects[object]['report']:
   #      print(object, key, objects[object]['report'][key])

   elapsed_time = time.time() - start_time
   print("Elapsed time:", elapsed_time)


   # Nothing matters after this????
   return(1, "Meteor Detected.")


   # Check for frames with 2x running sum brightness of the subtracted / frame. for frames with cm>= 3 create an event. there are trackable events with at least 3 frames of consecutive motion

   for fn in bp_frame_data:
      bin_days.append(fn)
      bin_avgs.append(bp_frame_data[fn]['avg_val'])
      bin_sums.append(bp_frame_data[fn]['sum_val'])
      bin_events.append(bp_frame_data[fn]['max_val'])
      if len(bin_sums) < 100:
         running_sum = np.median(bin_sums)
      else:
         running_sum = np.median(bin_sums[-99:])

      if bp_frame_data[fn]['sum_val'] > running_sum * 2:
         event.append(fn)
         cm = cm + 1
         no_mo = 0
      else:
         no_mo = no_mo + 1
      if cm >= 3 and no_mo >= 5:
         bright_events.append(event)
         cm = 0
         event = []
      if no_mo >= 5:
         cm = 0
         event = []

   # Review the events
   ec = 0
   for event in bright_events:
      if len(event) > 3:
         #for fn in event:
            #show_frame = frames[fn].copy()
            #cv2.circle(show_frame,(bp_frame_data[fn]['max_loc'][0],bp_frame_data[fn]['max_loc'][1]), 10, (255,255,255), 1)
            #desc = "EVENT: " + str(ec) + " FRAME: " + str(fn)
            #cv2.putText(show_frame, desc,  (10,10), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
         ec = ec + 1


     
   if False:
      import matplotlib
      matplotlib.use('Agg')
      import matplotlib.pyplot as plt
      #fig = plt.figure()
      #plt.plot(bin_days,bin_events, bin_avgs, bin_sums)
      plt.plot(bin_days,bin_sums)
      #plt.show()
      curve_file = "figs/detect.png"
      plt.savefig(curve_file)

   if len(bright_events) > 0:
      for event in bright_events:
         ts_stat = []
         fail = 0
         for fn in range(event[0], event[-1]):
            thresh_val = 20
            _ , thresh_img = cv2.threshold(subframes[fn].copy(), thresh_val, 255, cv2.THRESH_BINARY)
            thresh_sub_sum = np.sum(thresh_img)
            if thresh_sub_sum > 0:
               #print("THRESH SUM:", fn, thresh_sub_sum)
               ts_stat.append(fn)
         if len(ts_stat) < 3:
            #print("Not a valid event, just noise.")
            fail = 1
         else:
            print("Possible event, Frames above thresh.", len(ts_stat))
            elp = ts_stat[-1] - ts_stat[0]
            
            ratio = len(ts_stat) / elp
            if ratio < .6:
               print("Thresh hit to elp frame ratio to low. Not valid event. ", elp, len(ts_stat), ratio)
               fail = 1

         if fail == 0: 
         
            print("EVENT:", event)
            objects = {}
            motion_events,objects = check_event_for_motion(subframes[event[0]-10:event[-1]+10], objects, event[0]-10)
            meteor_objects = meteor_tests(objects)
            print("METEOR?:", meteor_objects)
            if len(meteor_objects) > 0:
               valid_events.append(event)

               meteor_file = video_file.replace(".mp4", "-meteor.json")
               meteor_json = {}
               meteor_json['meteor'] = meteor_objects
               save_json_file(meteor_file, meteor_json)

               event_file = video_file.replace(".mp4", "-trim-" + str(event[0]) + ".mp4")
               subframe_event_file = video_file.replace(".mp4", "subframes-trim-" + str(event[0]) + ".mp4")
               make_movie_from_frames(frames, [event[0]-10,event[-1] - 1+10], event_file , 1)
               make_movie_from_frames(subframes, [event[0]-10,event[-1] - 1+10], subframe_event_file , 1)


   else:
      print("No bright events found.")

   if len(valid_events) > 0:
      data_file = video_file.replace(".mp4", "-events.json")
      event_json = {}
      event_json['events'] = valid_events




      save_json_file(data_file, event_json)
   elapsed_time = time.time() - start_time
   print("Total Run Time.", elapsed_time)

def buffered_start_end(start,end, total_frames, buf_size):
   print("BUF: ", total_frames)
   bs = start - buf_size
   if buf_size < 20:
      buf_size = 20
   be = end + buf_size
   if bs < 0:
      bs = 0
   if be >= total_frames:
      be = total_frames - 1

   return(bs,be)
    

def make_custom_frame(frame, subframe, tracker, graph, graph2, info):
   subframe = cv2.cvtColor(subframe,cv2.COLOR_GRAY2RGB)
   custom_frame = np.zeros((720,1280,3),dtype=np.uint8)
   small_frame = cv2.resize(frame, (900,506))
   small_subframe = cv2.resize(subframe, (320,180))

   tracker = cv2.resize(tracker, (200,200))
   # main frame location
   fx1 = 0 
   fy1 = 0 
   fx2 = 0 + small_frame.shape[1]
   fy2 = 0 + small_frame.shape[0]

   sfx1 = fx2
   sfy1 = 0
   sfx2 = sfx1 + small_subframe.shape[1]
   sfy2 = 0 + small_subframe.shape[0]

   xygx1 = sfx1
   xygx2 = sfx1 + graph2.shape[1]
   xygy1 = sfy2
   xygy2 = sfy2 + graph2.shape[0]

   #tracker location
   trx1 = 0
   try1 = small_frame.shape[0] 
   trx2 = trx1 + tracker.shape[1] 
   try2 = try1 + tracker.shape[0] 

   # graph location
   grx1 = trx2 
   gry1 = small_frame.shape[0] 
   grx2 = grx1 + graph.shape[1] 
   gry2 = gry1 + graph.shape[0] 

   custom_frame[fy1:fy2,fx1:fx2] = small_frame
   custom_frame[sfy1:sfy2,sfx1:sfx2] = small_subframe
   custom_frame[try1:try2,trx1:trx2] = tracker
   custom_frame[gry1:gry2,grx1:grx2] = graph
   custom_frame[xygy1:xygy2,xygx1:xygx2] = graph2 

   cv2.rectangle(custom_frame, (fx1, fy1), (fx2, fy2), (255,255,255), 1, cv2.LINE_AA)
   cv2.rectangle(custom_frame, (sfx1, sfy1), (sfx2, sfy2), (255,255,255), 1, cv2.LINE_AA)
   cv2.rectangle(custom_frame, (trx1, try1), (trx2, try2), (255,255,255), 1, cv2.LINE_AA)


def custom_graph(data_x,data_y,max_x,max_y,graph_x,graph_y,type):

   fig_x = graph_x / 100
   fig_y = graph_y / 100
   import matplotlib
   matplotlib.use('Agg')
   import matplotlib.pyplot as plt

   fig = plt.figure(figsize=(fig_x,fig_y), dpi=100)
   plt.xlim(0,max_x)
   if type == 'line':
      plt.plot(data_x,data_y)
   if type == 'scatter':
      plt.scatter(data_x, data_y)
      ax = plt.gca()
      #ax.invert_xaxis()
      ax.invert_yaxis()

   curve_file = "figs/curve.png"
   fig.savefig(curve_file, dpi=100)
   plt.close()

   graph = cv2.imread(curve_file)
   return(graph)




def merge_contours(contours):
   cx = []
   cy = []
   cw = []
   ch = []
   new_contours = []
   for x,y,w,h in contours:
      cx.append(x)
      cy.append(y)
      cx.append(x+w)
      cy.append(y+h)
   nx = min(cx)
   ny = min(cy)
   nw = max(cx) - nx
   nh = max(cy) - ny

   new_contours.append((nx,ny,nw,nh))
   return(new_contours)

def merge_obj_frames(obj):
   merged = {}
   new_fns = []
   new_xs = []
   new_ys = []
   new_ws = []
   new_hs = []

   fns = obj['ofns']
   xs  = obj['oxs']
   ys  = obj['oys']
   ws  = obj['ows']
   hs  = obj['ohs']
   #for i in range(0, len(fns) - 1):
   for i in range (0,len(fns) -1):
      fn = fns[i]
      if fn not in merged: 
         merged[fn] = {}
         merged[fn]['xs'] = []
         merged[fn]['ys'] = []
         merged[fn]['ws'] = []
         merged[fn]['hs'] = []
      merged[fn]['xs'].append(xs[i])
      merged[fn]['ys'].append(ys[i])
      merged[fn]['ws'].append(ws[i])
      merged[fn]['hs'].append(hs[i])

   for fn in merged:
      merged[fn]['fx'] = int(np.mean(merged[fn]['xs']))
      merged[fn]['fy'] = int(np.mean(merged[fn]['ys']))
      merged[fn]['fw'] = int(max(merged[fn]['ws']))
      merged[fn]['fh'] = int(max(merged[fn]['hs']))
      new_fns.append(fn)
      new_xs.append(merged[fn]['fx'])
      new_ys.append(merged[fn]['fy'])
      new_ws.append(merged[fn]['fw'])
      new_hs.append(merged[fn]['fh'])

   obj['ofns'] = new_fns
   obj['oxs'] = new_xs
   obj['oys'] = new_ys
   obj['ows'] = new_ws
   obj['ohs'] = new_hs

   print(obj)

   return(obj)      

def check_fix_missing_frames(objects):
   for object in objects:
      fns = objects[object]['ofns']
      elp_fns = fns[-1] - fns[0]
      total_fns = len(fns) - 1
      if elp_fns == total_fns:
         print("NO MISSING FRAMES HERE! ", elp_fns, len(fns)-1)
      else:
         print("MISSING FRAMES FOUND IN METEOR FRAME SET FIXING! ", elp_fns, len(fns)-1)

   return(objects)

def object_report(objects):
   report = ""
   for object in meteors: 
      report = report + "FNs: " +str(object['ofns'] + "\n")
      report = report + "Xs: " +str(object['oxs'] + "\n")
      report = report + "Ys: " +str(object['oys'] + "\n")

      for key in object['report']:
         report = report + "   " + str(key) + str(object['report'][key])
      start_fn = object['ofns'][0] - 50
      end_fn = object['ofns'][-1] + 50
      print("START END:", start_fn, end_fn)
      if start_fn < 0:
         start_fn = 0
      if end_fn > len(frames) - 1:
         end_fn = len(frames) - 1
      report = report + "START END: " + str(start_fn) + " " + str(end_fn)
   return(report)


def find_events_from_bp_data(bp_data,subframes):
   events = []
   event = []
   objects = {}
   avg_sum = np.median(bp_data)
   for i in range(0,len(bp_data)):
      if i > 0 and i < len(bp_data) - 1:
         if i > 50 and i < len(bp_data) - 50:
            avg_sum = np.median(bp_data[i-50:i])
         prev_sum_val = bp_data[i-1]
         sum_val = bp_data[i]
         next_sum_val = bp_data[i+1]
         if sum_val > avg_sum * 2 and prev_sum_val > avg_sum * 2:
            event.append(i)
         elif sum_val > avg_sum * 2 and prev_sum_val > avg_sum * 2 and next_sum_val > avg_sum * 2:
            event.append(i)
         elif sum_val > avg_sum * 2 and next_sum_val > avg_sum * 2:
            event.append(i)
         else:
            if len(event) > 2:
               events.append(event)
               event = []
            else:
               event = []

   for event in events:
      for fn in event:
         contours, rects= find_contours_in_frame(subframes[fn])
         for ct in contours:
            object, objects = find_object(objects, fn,ct[0], ct[1], ct[2], ct[3])

   print("EVENTS:",events)
   print("OBJECTS:",objects)

   return(events, objects) 

def meteor_tests(objects):
   meteor_objects = []
   for obj in objects:
      if len(objects[obj]['oxs']) > 3:
         one_dir_test_result = one_dir_test(objects[obj])
         dist_test_result = dist_test(objects[obj])
         gap_test_result = gap_test(objects[obj])

         if one_dir_test_result == 1 and dist_test_result == 1 and gap_test_result == 1:
            print(obj, objects[obj])
            meteor_objects.append(objects[obj])

      if len(meteor_objects) == 0:
         print("No meteor objects.")
         for obj in objects:
            print(obj, objects[obj])
   return(meteor_objects)

def check_event_for_motion(subframes, objects, fn):
   thresh_val = 20 
   motion_events = []
   cnt_frames = {} 
   #fn = 0
   for frame in subframes:
      cnt_frames[fn] = {}
      cnt_frames[fn]['xs'] = [] 
      cnt_frames[fn]['ys'] = [] 
      cnt_frames[fn]['ws'] = [] 
      cnt_frames[fn]['hs'] = [] 

      _ , thresh_img = cv2.threshold(frame.copy(), thresh_val, 255, cv2.THRESH_BINARY)
      cnt_res = cv2.findContours(thresh_img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
      if len(cnt_res) == 3:
         (_, cnts, xx) = cnt_res
      elif len(cnt_res) == 2:
         (cnts, xx) = cnt_res
      pos_cnts = []
      if len(cnts) > 3:
         # Too many cnts be more restrictive!
         thresh_val = thresh_val + 5
         _ , thresh_img = cv2.threshold(thresh_img.copy(), thresh_val, 255, cv2.THRESH_BINARY)
         cnt_res = cv2.findContours(thresh_img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
         if len(cnt_res) == 3:
            (_, cnts, xx) = cnt_res
         elif len(cnt_res) == 2:
            (cnts, xx) = cnt_res

      if len(cnts) > 0:
         for (i,c) in enumerate(cnts):
            x,y,w,h = cv2.boundingRect(cnts[i])
            print("CNT:", fn, x,y,w,h)
            cnt_frames[fn]['xs'].append(x)
            cnt_frames[fn]['ys'].append(y)
            cnt_frames[fn]['ws'].append(w)
            cnt_frames[fn]['hs'].append(h)
      fn = fn + 1

   objects = find_cnt_objects(cnt_frames, objects)


   return(motion_events, objects)      


def stack_frames_fast(frames, skip = 2):
   stacked_image = None
   fc = 0
   for frame in frames:
      if fc % skip == 0:
         frame_pil = Image.fromarray(frame)
         if stacked_image is None:
            stacked_image = stack_stack(frame_pil, frame_pil)
         else:
            stacked_image = stack_stack(stacked_image, frame_pil)

      fc = fc + 1
   return(np.asarray(stacked_image))

def stack_stack(pic1, pic2):
   stacked_image=ImageChops.lighter(pic1,pic2)
   return(stacked_image)

def load_frames_fast(trim_file, json_conf, limit=0, mask=0,crop=(),color=0,resize=[]):
   print("TRIM FILE:", trim_file)
   (f_datetime, cam, f_date_str,fy,fm,fd, fh, fmin, fs) = convert_filename_to_date_cam(trim_file)
   cap = cv2.VideoCapture(trim_file)
   masks = None
   last_frame = None
   last_last_frame = None

   if "HD" in trim_file:
      masks = get_masks(cam, json_conf,1)
   else:
      masks = get_masks(cam, json_conf,1)
   if "crop" in trim_file:
      masks = None
   print("MASKS:", cam, masks)

   color_frames = []
   frames = []
   subframes = []
   sum_vals = []
   max_vals = []
   frame_count = 0
   go = 1
   while go == 1:
      if True :
         _ , frame = cap.read()
         if frame is None:
            if frame_count <= 5 :
               cap.release()
               return(frames,color_frames,subframes,sum_vals,max_vals)
            else:
               go = 0
         else:
            if color == 1:
               color_frames.append(frame)
            if limit != 0 and frame_count > limit:
               cap.release()
               return(frames)
            if len(frame.shape) == 3 :
               frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if mask == 1 and frame is not None:
               if frame.shape[0] == 1080:
                  hd = 1
               else:
                  hd = 0
               masks = get_masks(cam, json_conf,hd)
               frame = mask_frame(frame, [], masks, 5)

            if last_frame is not None:
               subframe = cv2.subtract(frame, last_frame)
               #subframe = mask_frame(subframe, [], masks, 5)
               sum_val =cv2.sumElems(subframe)[0]
               if sum_val > 200 and last_last_frame is not None:
                  subframe = cv2.subtract(subframe, last_last_frame)
                  sum_val =cv2.sumElems(subframe)[0]
               subframes.append(subframe)


               if sum_val > 100:
                  min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(subframe)
               else:
                  max_val = 0
               sum_vals.append(sum_val)
               max_vals.append(max_val)

            if len(crop) == 4:
               ih,iw = frame.shape
               x1,y1,x2,y2 = crop
               x1 = x1 - 25
               y1 = y1 - 25
               x2 = x2 + 25
               y2 = y2 + 25
               if x1 < 0:
                  x1 = 0
               if y1 < 0:
                  y1 = 0
               if x1 > iw -1:
                  x1 = iw -1
               if y1 > ih -1:
                  y1 = ih -1
               #print("MIKE:", x1,y2,x2,y2)
               crop_frame = frame[y1:y2,x1:x2]
               frame = crop_frame
            if len(resize) == 2:
               frame = cv2.resize(frame, (resize[0],resize[1]))
       
            frames.append(frame)
            if last_frame is not None:
               last_last_frame = last_frame
            last_frame = frame
      frame_count = frame_count + 1
   cap.release()
   if len(crop) == 4:
      return(frames,x1,y1)
   else:
      return(frames, color_frames, subframes, sum_vals, max_vals)


def update_hd_path(file):
   (hd_datetime, cam, sd_date, sd_y, sd_m, sd_d, sd_h, sd_M, sd_s) = convert_filename_to_date_cam(file)
   if "/mnt/ams2/HD/" in file:
      ff = file.split("/")[-1]
      new_file = "/mnt/ams2/meteors/" + sd_y + "_" + sd_m + "_" + sd_d + "/" + ff
      return(new_file)
   else:
      return(file)
     

def make_frame_crop_summary(frames, obj, trim_num_start):
   crops = []
   frame_data = {}
   print(obj)
   for i in range(obj['ofns'][0]-trim_num_start, obj['ofns'][-1]-trim_num_start+1):
      frame_data[i] = {}

   for i in range(0, len(obj['ofns'])):
      fn = obj['ofns'][i] - trim_num_start
      x = obj['oxs'][i]
      y = obj['oys'][i]
      w = obj['ows'][i]
      h = obj['ohs'][i]
      oint  = obj['oint'][i]

      frame_data[fn]['x'] = x
      frame_data[fn]['y'] = y
      frame_data[fn]['w'] = w
      frame_data[fn]['h'] = h
      frame_data[fn]['oint'] = oint

      oint = obj['oint'][i]
      print("FRAMES:", len(frames), fn)
      cx1,cy1,cx2,cy2 = bound_cnt(x,y,frames[0].shape[1], frames[0].shape[0],25)
      frame_data[fn]['frame_crop'] = [cx1,cy1,cx2,cy2]
      frame = frames[fn].copy()
     
      cv2.circle(frame,(x,y), 5, (255,255,255), 1)
  
 

   for fn in frame_data:
      if "x" not in frame_data[fn]:
         frame_data[fn]['x'] = last_x
         frame_data[fn]['y'] = last_y
         frame_data[fn]['w'] = last_w
         frame_data[fn]['h'] = last_h
         frame_data[fn]['fixed'] = 1
         cx1,cy1,cx2,cy2 = bound_cnt(x,y,frames[0].shape[1], frames[0].shape[0],10)
         frame_data[fn]['frame_crop'] = [cx1,cy1,cx2,cy2]
      else:
         x = frame_data[fn]['x']
         y = frame_data[fn]['y']
         w = frame_data[fn]['w']
         h = frame_data[fn]['h']

      last_x = x
      last_y = y
      last_w = w
      last_h = h


   # each crop is 50 x 50 so
   # so we can fit a max of 38 frames across an HD image
   # determine rows as total_frames / 38
   rows = math.ceil(len(frame_data) / 18)
   crop_sum_x = 1920
   crop_sum_y = rows * 100
   crop_sum_img = np.zeros((crop_sum_y,crop_sum_x,3),dtype=np.uint8)
  
   fc = 0 
   cc = 0 
   row_y = 0
   for fn in frame_data:
      cx1,cy1,cx2,cy2 = frame_data[fn]['frame_crop']
      x =  frame_data[fn]['x']
      y =  frame_data[fn]['y']
    
      if show == 1: 
         cv2.circle(frames[fn],(x,y), 2, (0,255,0), 1)   
         cv2.imshow("frame crop summary", frames[fn])
         cv2.waitKey(70)
      crop_img = frames[fn][cy1:cy2,cx1:cx2]

      nx1 = cc * 100
      nx2 = nx1 + 100
      ny1 = row_y 
      ny2 = row_y + 100
      crop_img = cv2.resize(crop_img,(100,100)) 
      crop_img = cv2.cvtColor(crop_img,cv2.COLOR_GRAY2RGB)
      if crop_img.shape[0] == 100 and crop_img.shape[1] == 100:
         crop_sum_img[ny1:ny2,nx1:nx2] = crop_img 
      if show == 1:
         cv2.imshow("frame crop summary", crop_img)
         cv2.waitKey(70)


      fc = fc + 1
      cc = cc + 1
      if fc % 18 == 0 and fc > 0 :
         row_y = row_y + 100
         cc  = 0
   if show == 1:
      cv2.imshow('frame crop summary', crop_sum_img)
      cv2.waitKey(70)

   if show == 1:
      cv2.destroyWindow('frame crop summary')


   return(crop_sum_img,frame_data)

def get_trim_num(file):
   xxx = file.split("trim")[-1]
   xxx = xxx.replace(".mp4", "")
   return(int(xxx))

def flex_sync_hd_frames(video_file, hd_frames, hd_crop_frames, sd_frames,obj):
   print("Sync HD Frames:")    
   crop_x = obj['crop_box'][0]
   crop_y = obj['crop_box'][1]

   #len(obj['ofns'])):  
   for i in range(0, 5):
       
      sd_fn = obj['ofns'][i]
      first_x = obj['oxs'][i]
      first_y = obj['oys'][i]
      first_w = obj['ows'][i]
      first_h = obj['ohs'][i]

      hdm_x =  hd_frames[0].shape[1] / sd_frames[0].shape[1] 
      hdm_y =  hd_frames[0].shape[0] / sd_frames[0].shape[0]

      hd_x1 = int(first_x * hdm_x) 
      hd_y1 = int(first_y * hdm_y) 
      hd_x2 = (int(first_x * hdm_x) ) + int(hdm_x * first_w)
      hd_y2 = (int(first_y * hdm_y) ) + int(hdm_y * first_h)

      

      cx1,cy1,cx2,cy2 = bound_cnt(hd_x1-crop_x,hd_y1-crop_y,hd_crop_frames[0].shape[1],hd_crop_frames[0].shape[0], 40)
      #cx1, cy1,cx2,cy2 = hd_x1,hd_y1, hd_x2, hd_y2 

      #find_hd_frame(hd_frames, cx1,cy1,cx2,cy2)
      find_hd_frame(hd_crop_frames, cx1,cy1,cx2,cy2)

def find_hd_frame(hd_crop_frames, cx1,cy1,cx2,cy2):
   last_frame = hd_crop_frames[0]
   max_int = 0
   max_px = 0
   max_fn = 0

   fc = 0
   for frame in hd_crop_frames:
      sub_frame = cv2.subtract(frame,last_frame)
      crop_hd_crop = sub_frame[cy1:cy2,cx1:cx2]
      min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(crop_hd_crop)
      intense = np.sum(crop_hd_crop)
      if intense >  max_int:
         max_int = intense
         best_fn_int = fc
      if max_val >  max_px:
         max_px = max_val
         best_fn_px = fc
       
      
      last_frame = frame
      fc = fc + 1
   print("Best matching frame: ", best_fn_int, best_fn_px)


def refine_points(frames, frame_data):
   last_frame = frames[0]
   max_vals = []
   seg_dists = []
   last_max_x = None
   last_max_y = None
   med_seg_dist = 0
   for fn in frame_data:
      frame = frames[fn].copy()
      subframe = cv2.subtract(frame,frames[0])
      cx1,cy1,cx2,cy2 = bound_cnt(frame_data[fn]['x'],frame_data[fn]['y'],frames[0].shape[1],frames[0].shape[0], 20)
      crop = subframe[cy1:cy2,cx1:cx2]
      min_val, max_val, min_loc, (mx,my)= cv2.minMaxLoc(crop)
      max_vals.append(max_val)
      med_max_val = np.median(max_vals)
      max_x = mx + cx1
      max_y = mx + cy1
      frame_data[fn]['max_x'] = max_x
      frame_data[fn]['max_y'] = max_y
      frame_data[fn]['max_val'] = max_val
      if last_max_x is not None:
         frame_data[fn]['seg_dist'] = calc_dist((max_x, max_y) , (last_max_x, last_max_y))
         seg_dists.append(frame_data[fn]['seg_dist'])
         med_seg_dist = np.median(seg_dists)

      print("MED:", med_max_val, med_seg_dist)
      if max_val < med_max_val:
         frame_data[fn]['max_val_bad'] = max_val - med_max_val
      cx1,cy1,cx2,cy2 = bound_cnt(max_x,max_y,frames[0].shape[1],frames[0].shape[0], 20)
      crop = frame[cy1:cy2,cx1:cx2]
      last_max_x = max_x
      last_max_y = max_y
 
def review_meteor(video_file):
   custom_frame = np.zeros((1080,1920,3),dtype=np.uint8)
   json_file= video_file.replace(".mp4", ".json")
   stack_file = video_file.replace(".mp4", "-stacked.png")
   trim_num = get_trim_num(video_file)

   frames,color_frames,subframes,sum_vals,max_vals = load_frames_fast(video_file, json_conf, 0, 0, [], 0,[])


   if cfe(stack_file) == 1:
      stack_img = cv2.imread(stack_file)
   else:
      stack_file, stack_img = stack_frames(frames,video_file,0)
      stack_img = cv2.cvtColor(stack_img,cv2.COLOR_GRAY2RGB)

   data = load_json_file(json_file)  
   fd = data['flex_detect'] 

   sd_crop_sum_img,frame_data = make_frame_crop_summary(frames, fd, trim_num)

   #refine_points(frames, frame_data)

   hd_trim = update_hd_path(fd['hd_trim'])
   fd['hd_trim'] = hd_trim
   hd_crop_file = update_hd_path(fd['hd_crop_file'])
   if hd_trim != 0:
      hd_stack_file = hd_trim.replace(".mp4", "-stacked.png")
      half_stack_file = hd_trim.replace(".mp4", "half-stack.png")
      if cfe(hd_stack_file) == 0:
         print("HD STACK NOT EXIST")
         hd_frames,hd_color_frames,hd_subframes,sum_vals,max_vals = load_frames_fast(hd_trim, json_conf, 0, 0, [], 0,[])
         if cfe(hd_crop_file) == 1:
            hd_crop_frames,hd_crop_color_frames,hd_crop_subframes,sum_vals,max_vals = load_frames_fast(hd_crop_file, json_conf, 0, 0, [], 0,[])
         else:
            # make hd crop file and then load it in
            hd_crop_file, crop_box = crop_hd(fd, meteor_frames[0])
            fd['hd_crop_file'] = hd_crop_file
            hd_crop_frames,hd_crop_color_frames,hd_crop_subframes,sum_vals,max_vals = load_frames_fast(hd_crop_file, json_conf, 0, 0, [], 0,[])

         print("HDTRIM: ", hd_trim)
         print("HDCROP: ", hd_crop_file)
         print("FRAMES:", len(hd_frames))
         hd_stack_file, hd_stack_img = stack_frames(hd_frames,hd_trim,0)
         if show == 1:
            cv2.imshow('HD', hd_stack_img)
            cv2.waitKey(70)
         half_stack_img = cv2.resize(hd_stack_img, (0,0),fx=.5, fy=.5)
         cv2.imwrite(hd_stack_file, hd_stack_img) 
         cv2.imwrite(half_stack_file, half_stack_img) 
      else:
         print("HD STACK EXISTS")
         hd_frames,hd_color_frames,hd_subframes,sum_vals,max_vals = load_frames_fast(hd_trim, json_conf, 0, 0, [], 0,[])
         print("HD CROP ", hd_crop_file)

         if cfe(hd_crop_file) == 1:
            hd_crop_frames,hd_crop_color_frames,hd_crop_subframes,sum_vals,max_vals = load_frames_fast(hd_crop_file, json_conf, 0, 0, [], 0,[])
         else:
            # make hd crop file and then load it in
            hd_crop_file, crop_box = crop_hd(fd, frames[0])
            fd['hd_crop_file'] = hd_crop_file
            hd_crop_frames,hd_crop_color_frames,hd_crop_subframes,sum_vals,max_vals = load_frames_fast(hd_crop_file, json_conf, 0, 0, [], 0,[])
         hd_stack_img = cv2.imread(hd_stack_file)
         if cfe(half_stack_file) == 1:
            half_stack_img = cv2.imread(half_stack_file)
         else:
            half_stack_img = cv2.resize(hd_stack_img, (0,0),fx=.5, fy=.5)
            cv2.imwrite(half_stack_file, half_stack_img) 
          
   else:
      print("HD TRIM IS 0!")
      print("MUST DO REVIEW IN SD ONLY! :(")
   if show == 1:
      cv2.destroyAllWindows("HD")
 

   #flex_sync_hd_frames(video_file, hd_frames, hd_crop_frames, frames,fd)


   print("Review Meteor Object:")
   x1,y1,x2,y2 = fd['crop_box']
   cv2.rectangle(stack_img, (x1, y1), (x2, y2), (255,255,255), 1, cv2.LINE_AA)
   for i in range(0, len(fd['ofns'])):
      x = fd['oxs'][i]
      y = fd['oys'][i]
      cv2.circle(stack_img,(x,y), 10, (255,255,255), 1)

   for key in fd:
      if key != 'hd_crop_objects' and key != 'report':
         print(key, fd[key])
      elif key == 'report':
         print("REPORT")
         for rk in fd['report']:
            print("   ", rk, fd['report'][rk])
   ih, iw = stack_img.shape[:2]
   hsih, hsiw = half_stack_img.shape[:2]


   for obj_id in fd['hd_crop_objects']:
      obj = fd['hd_crop_objects'][obj_id]
      print(obj)
      stack_img = draw_obj_on_frame(stack_img, obj)
      #x1,y1,x2,y2 = obj['crop_box']
      #cv2.rectangle(stack_img, (x1, y1), (x2, y2), (255,255,255), 1, cv2.LINE_AA)

   #custom_frame[0:ih,0:iw] = stack_img
   custom_frame[0:hsih,0:hsiw] = half_stack_img
   print("HSI:", half_stack_img.shape)
   print("HSI:", custom_frame.shape)
   print(ih, ih+hsih,0,hsiw)
   if show == 1:
      cv2.imshow('Review Meteor', custom_frame)
      cv2.waitKey(70)
       
def draw_obj_on_frame(frame, obj):
   for i in range(0, len(obj['ofns'])):
      x = obj['oxs'][i]
      y = obj['oys'][i]
      cv2.circle(frame,(x,y), 10, (0,255,0), 1)
   return(frame)

def write_archive_index(year,month):
   from lib.Archive_Listing import write_month_index, write_year_index
   print("Create json index month:", year, month)
   write_month_index(month,year)
   write_year_index(year)

   #write_index(year)

def move_to_archive(json_file):

   (hd_datetime, cam, sd_date, sd_y, sd_m, sd_d, sd_h, sd_M, sd_s) = convert_filename_to_date_cam(json_file)
   hd_vid = json_file.replace(".json", "-HD.mp4")
   sd_vid = json_file.replace(".json", "-SD.mp4")
   station_id = json_conf['site']['ams_id'].upper()
   meteor_dir = METEOR_ARCHIVE + station_id + "/" + METEOR + sd_y + "/" + sd_m + "/" + sd_d + "/"

   # If the new_folder doesn't exist, we create it
   if not os.path.exists(meteor_dir):
      os.makedirs(meteor_dir)

   # MOVE the files into the archive (All these files are prepped and named and ready to go.
   cmd = "cp /mnt/ams2/matmp/" + json_file + " " + meteor_dir
   print(cmd)
   os.system(cmd)
   cmd = "cp /mnt/ams2/matmp/" + hd_vid + " " + meteor_dir
   print(cmd)
   os.system(cmd)
   cmd = "cp /mnt/ams2/matmp/" + sd_vid + " " + meteor_dir
   print(cmd)
   os.system(cmd)
   cmd = "./MakeCache.py " + meteor_dir + json_file
   print(cmd)
   os.system(cmd)
   return(meteor_dir)

def spectra(hd_stack):
   img = cv2.imread(hd_stack, 0)
   thresh_val = 100
   cnts,rects = find_contours_in_frame(img, thresh_val)
   for cnt in cnts:
      x,y,w,h = cnt
      if w > 20 or h > 20:
         cv2.rectangle(img, (x, y), (x+w, y+h), (255,255,255), 1, cv2.LINE_AA)

def rerun(video_file):
   day_dir = video_file[0:10]
   cmd = "cp /mnt/ams2/SD/proc2/" + day_dir + "/" + video_file + " /mnt/ams2/CAMS/queue/"
   print(cmd)
   os.system(cmd)
   cmd = "./flex-detect.py debug /mnt/ams2/CAMS/queue/" + video_file
   print(cmd)
   os.system(cmd)

def meteor_objects(objects):
   meteors = {}
   nonmeteors = {}
   mc = 1
   nc = 1
   for obj in objects:
      objects[obj] = analyze_object_final(objects[obj] )
      if objects[obj]['report']['meteor_yn'] == "Y":
         meteors[mc] = objects[obj]
         mc = mc + 1
      else:
         nonmeteors[nc] = objects[obj]
         nc = nc + 1
   return(meteors,nonmeteors)

def debug(video_file):
   orig_sd_trim_num = get_trim_num(video_file)

   start_time = time.time() 

   hd_datetime, hd_cam, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(video_file)
   meteor_date = hd_y + "_" + hd_m + "_" + hd_d
   old_meteor_dir = "/mnt/ams2/meteors/" + hd_y + "_" + hd_m + "_" + hd_d + "/"
   mf = video_file.split("/")[-1]
   mf = mf.replace(".mp4", ".json")
   old_meteor_json_file = old_meteor_dir + mf 
   print(old_meteor_json_file)
   md = load_json_file(old_meteor_json_file)
   hd_trim = md['hd_trim']
   org_sd_vid = video_file 


   # load SD & HD frames
   frames,color_frames,subframes,sum_vals,max_vals = load_frames_fast(video_file, json_conf, 0, 0, [], 1,[])
   if "/mnt/ams2/HD" in hd_trim:
      mfn = hd_trim.split("/")[-1]
      mday = mfn[0:10]
      hd_trim = "/mnt/ams2/meteors/" + mday + "/" + mfn

   if cfe(hd_trim) == 1:
      hd_frames,hd_color_frames,hd_subframes,hd_sum_vals,hd_max_vals = load_frames_fast(hd_trim, json_conf, 0, 0, [], 1,[])
      org_hd_vid = hd_trim 
   else:
      org_hd_vid = None 
      print("HD TRIM FILE NOT FOUND!")
      md['arc_fail'] = "HD TRIM FILE NOT FOUND"
      save_json_file(old_meteor_json_file, md)
      return()


   events,pos_meteors = fast_check_events(sum_vals, max_vals, subframes)
   
   hd_events,hd_pos_meteors = fast_check_events(hd_sum_vals, hd_max_vals, hd_subframes)

   fast_meteors,fast_non_meteors = meteor_objects(pos_meteors)
   hd_fast_meteors,hd_fast_non_meteors = meteor_objects(hd_pos_meteors)

   print("FAST METEORS:", fast_meteors)
   print("FAST HD METEORS:", hd_fast_meteors)

   print("NO SD METEOR FOUND.", fast_non_meteors)

   motion_objects,meteor_frames = detect_meteor_in_clip(video_file, frames, 0)
   motion_found = 0
   for obj in motion_objects:
      if motion_objects[obj]['report']['meteor_yn'] == 'Y':
         fast_meteors[obj] = motion_objects[obj]
         motion_found = 1
         print("MOTION METEOR OBJECTS!", motion_objects[obj])
   if motion_found == 0 and len(fast_meteors) == 0:
      md['arc_fail'] = "NO FAST METEORS AND NO MOTION FOUND IN SD."
      save_json_file(old_meteor_json_file, md)
      print("MOTION NOT FOUND!")
      return()

   motion_objects,meteor_frames = detect_meteor_in_clip(video_file, hd_frames, 0)
   motion_found = 0
   for obj in motion_objects:
      if motion_objects[obj]['report']['meteor_yn'] == 'Y':
         hd_fast_meteors[obj] = motion_objects[obj]
         motion_found = 1
         print("MOTION METEOR OBJECTS!", motion_objects[obj])
   if motion_found == 0 or len(hd_fast_meteors) == 0:
      print("MOTION NOT FOUND IN HD CLIP!")
      print("NO HD METEOR FOUND.", fast_non_meteors)
      md['arc_fail'] = "NO HD METEOR FOUND"
      save_json_file(old_meteor_json_file, md)
      return()




   for key in fast_meteors:
      sd_meteor = fast_meteors[key] 
   for key in hd_fast_meteors:
      hd_meteor = hd_fast_meteors[key] 


   sync_diff = refine_sync(0, sd_meteor, hd_meteor, hd_frames[0], frames[0])

   buf_size = 20

   print(sd_meteor)
   print(hd_meteor)

   sd_bs,sd_be = buffered_start_end(sd_meteor['ofns'][0],sd_meteor['ofns'][-1], len(frames), buf_size)
   if sd_bs == 0:
      buf_size = sd_meteor['ofns'][0]
   hd_bs,hd_be = buffered_start_end(hd_meteor['ofns'][0],hd_meteor['ofns'][-1], len(hd_frames), buf_size)

   new_trim_num = orig_sd_trim_num + sd_bs
   new_sd_clip_file = video_file.replace("trim-" + str(orig_sd_trim_num), "trim-" + str(new_trim_num))
   new_sd_clip_file = new_sd_clip_file.replace(".mp4", "-SD.mp4")
 
   new_hd_clip_file = new_sd_clip_file.replace("-SD", "-HD")
   new_json_file = new_sd_clip_file.replace("-SD.mp4", ".json")

   new_sd_gframes = frames[sd_bs:sd_be]
   new_hd_gframes = hd_frames[hd_bs:hd_be]

   new_sd_frames = color_frames[sd_bs:sd_be]
   new_hd_frames = hd_color_frames[hd_bs:hd_be]

   new_sd_sum_vals = sum_vals[sd_bs:sd_be]
   new_hd_sum_vals = hd_sum_vals[hd_bs:hd_be]
   new_sd_max_vals = max_vals[sd_bs:sd_be]
   new_hd_max_vals = hd_max_vals[hd_bs:hd_be]
   new_sd_subframes = subframes[sd_bs:sd_be]
   new_hd_subframes = hd_subframes[hd_bs:hd_be]

   print("FRAMES:", len(hd_frames), len(new_hd_frames)) 


   print("LEN NEW FRAMES: ", len(new_sd_frames), len(new_hd_frames))

   elapsed_time = time.time() - start_time
   print("SYNC_DIFF:", sync_diff)
   print("ELAPSED:", elapsed_time)

   # remaster the sync'd SD and HD frames
   temp_hd = new_hd_clip_file.split("/")[-1] 
   temp_sd = new_sd_clip_file.split("/")[-1] 
   temp_js = new_json_file.split("/")[-1] 


   (f_datetime, cam, f_date_str,fy,fm,fd, fh, fmin, fs) = convert_filename_to_date_cam(video_file)
   extra_sec = new_trim_num / 25
   start_trim_frame_time = f_datetime + datetime.timedelta(0,extra_sec)


   make_movie_from_frames(new_hd_frames, [0,len(new_hd_frames) - 1], "/mnt/ams2/matmp/" + temp_hd , 0)
   make_movie_from_frames(new_sd_frames, [0,len(new_sd_frames) - 1], "/mnt/ams2/matmp/" + temp_sd , 0)

   events,pos_meteors = fast_check_events(new_sd_sum_vals, new_sd_max_vals, new_sd_subframes)
   hd_events,hd_pos_meteors = fast_check_events(new_hd_sum_vals, new_hd_max_vals, new_hd_subframes)
   fast_meteors,fast_non_meteors = meteor_objects(pos_meteors)
   hd_fast_meteors,hd_fast_non_meteors = meteor_objects(hd_pos_meteors)

   if len(hd_fast_meteors) == 0:
      motion_objects,meteor_frames = detect_meteor_in_clip(video_file, new_hd_gframes, 0)
      motion_found = 0
      for obj in motion_objects:
         if motion_objects[obj]['report']['meteor_yn'] == 'Y':
            hd_fast_meteors[obj] = motion_objects[obj]
            motion_found = 1
            print("MOTION METEOR OBJECTS!", motion_objects[obj])
      if motion_found == 0:
         print("MOTION NOT FOUND IN HD CLIP!")
         print("NO HD METEOR FOUND.", fast_non_meteors)
         return()




   print("SD FAST:", fast_meteors)
   print("HD FAST:", hd_fast_meteors)
   if len(fast_meteors) == 0 and len(hd_fast_meteors) == 0:
      print("No fast meteors found!")
      return()

   if len(fast_meteors) == len(hd_fast_meteors) and len(fast_meteors) > 0:
      print("SD & HD METEOR DETECTED AND SYNC'D!")
   

   restack("/mnt/ams2/matmp/" + temp_hd)
   restack("/mnt/ams2/matmp/" + temp_sd)

   for key in hd_fast_meteors:
      hd_fast_meteor = hd_fast_meteors[key] 

   hd_fast_meteor['trim_clip'] = "/mnt/ams2/matmp/" + temp_sd
   hd_fast_meteor['hd_trim'] = "/mnt/ams2/matmp/" + temp_hd
   hd_fast_meteor['dt'] = start_trim_frame_time.strftime('%Y-%m-%d %H:%M:%S.%f')
   hd_fast_meteor['hd_file'] = temp_hd 
   hd_fast_meteor['sd_file'] = temp_sd 
   #hd_fast_meteor['report']['dur'] = hd_fast_meteor['ofns'][-1] - hd_fast_meteor['ofns'][0] / 25 
   hd_fast_meteor['dur'] = hd_fast_meteor['ofns'][-1] - hd_fast_meteor['ofns'][0] / 25 
   for i in range(0,len(hd_fast_meteor['ofns'])):
      if "ftimes" not in hd_fast_meteor:
         hd_fast_meteor['ftimes'] = []
      fn = hd_fast_meteor['ofns'][i]

      extra_meteor_sec = fn /  25
      meteor_frame_time = start_trim_frame_time + datetime.timedelta(0,extra_meteor_sec)
      meteor_frame_time_str = meteor_frame_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
      hd_fast_meteor['ftimes'].append(meteor_frame_time_str)



   #process_meteor_files(hd_fast_meteor, meteor_date, video_file, 1)

   calib,cal_params = apply_calib(hd_fast_meteor)
   hd_fast_meteor['calib'] = calib
   hd_fast_meteor['cal_params'] = cal_params
   new_json = save_new_style_meteor_json(hd_fast_meteor, temp_js)
   new_json['info']['org_sd_vid'] = org_sd_vid
   new_json['info']['org_hd_vid'] = org_hd_vid
   save_json_file("/mnt/ams2/matmp/" + temp_js, new_json)
   arc_dir = move_to_archive(temp_js)
   md['archive_file'] = arc_dir + temp_js
   save_json_file(old_meteor_json_file, md)


   write_archive_index(fy,fm)
   print(temp_js)
   #return(new_json_file_name)





def check_archive(day, run):
   old_meteor_files = glob.glob("/mnt/ams2/meteors/" + day + "/*trim*.json")
   mdir = "/mnt/ams2/meteors/" + day
   if cfe(mdir, 1) == 0:
      print("No meteors for this day.")
      return()
   print("/mnt/ams2/meteors/" + day + "/*trim*.json")

   omf = []
   good = 0
   bad = 0
   for mf in old_meteor_files:
      if "reduced" not in mf and "archive_report" not in old_meteor_files:
         jd = load_json_file(mf)
         if "archive_file" in jd:
            if cfe(jd['archive_file']) == 1:
               archive_data = {}
               archive_data['orig_file'] = mf
               archive_data['archive_file'] = jd['archive_file']
               archive_data['status'] = 1
               good = good + 1
            else:
               archive_data = {}
               archive_data['orig_file'] = mf
               archive_data['status'] = 0
               bad = bad + 1
               if "arc_fail" in jd:
                  print("ALREADY TRIED AND FAILED:", jd['arc_fail'])
         else:
            archive_data = {}
            archive_data['status'] = 0
         if archive_data['status'] != 1:
            archive_data['orig_file'] = mf
            archive_data['status'] = 0
            bad = bad + 1
            mp4_file = mf.replace(".json", ".mp4")
            if "arc_fail" in jd:
               print("ALREADY TRIED AND FAILED:", jd['arc_fail'])
            cmd = "./flex-detect.py debug " + mp4_file
            print(cmd) 
            if run == 1: 
               os.system(cmd)
         # check HD
         #if cfe(jd['hd_trim']) == 0:
         #   print("HD TRIM MISSING!", jd['hd_trim'])
         if "hd_trim" in jd:
            hd_stack = jd['hd_trim'].replace(".mp4", "-stacked.png")
         else:
            print("HD TRIM MISSING FROM ORIG JS:", mp4_file)
         #if cfe(hd_stack) == 0:
         #   print("HD STACK NOT FOUND:", hd_stack)


         omf.append(archive_data)
   save_json_file("/mnt/ams2/meteors/" + day + "/archive_report.json", omf)
   print("ARCHIVE REPORT FOR " + day)
   print("SUCCESS:", good)
   print("FAILED:", bad)
   print("/mnt/ams2/meteors/" + day + "/archive_report.json" )
      
 

cmd = sys.argv[1]
video_file = sys.argv[2]

if cmd == "fd" or cmd == "flex_detect":
   flex_detect(video_file)

if cmd == "qs" or cmd == "quick_scan":
   quick_scan(video_file)

if cmd == "qb" or cmd == "batch":
   batch_quick()

if cmd == "som" or cmd == "scan_old_meteor_dir":
   scan_old_meteor_dir(video_file)
if cmd == "sq" or cmd == "scan_queue":
   scan_queue(video_file)
if cmd == "cm" or cmd == "confirm_meteor":
   confirm_meteor(video_file)
if cmd == "bc" or cmd == "batch_confirm":
   batch_confirm()
if cmd == "mfs" or cmd == "move_files":
   batch_move()
if cmd == "rp" or cmd == "refine_points":
   refine_points(video_file)
if cmd == "snm" or cmd == "stack_non_meteors":
   stack_non_meteors()
if cmd == "fmhd" or cmd == "fix_missing_hd":
   fix_missing_hd(video_file)
if cmd == "rm" or cmd == "review_meteor":
   review_meteor(video_file)
if cmd == "sp" or cmd == "spectra":
   spectra(video_file)
if cmd == "rr" or cmd == "rerun":
   rerun(video_file)
if cmd == "remaster":
   remaster_arc(video_file)
if cmd == "wi":
   write_archive_index(sys.argv[2], sys.argv[3])
if cmd == "debug" :
   debug(video_file)
if cmd == "ca" :
   if len(sys.argv) > 3:
      check_archive(video_file, 1)
   else:
      check_archive(video_file, 0)
if cmd == "ram" :
   refit_arc_meteor(video_file)
if cmd == "faf" :
   fit_arc_file(video_file)

if cmd == "bfaf" :
   batch_fit_arc_file(video_file)

