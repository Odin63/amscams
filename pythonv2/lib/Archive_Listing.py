# coding: utf-8
import sys  
import cgitb
import datetime
import os

from Get_Station_Id import get_station_id
from REDUCE_VARS import METEOR

def archive_listing(form):
   limit_day = form.getvalue('limit_day')
   cur_page  = form.getvalue('p')
   meteor_per_page = form.getvalue('meteor_per_page')

   if (cur_page is None) or (cur_page==0):
      cur_page = 1
   else:
      cur_page = int(cur_page)

   if (limit_day is None):
      now = datetime.datetime.now()
      year = now.year
  
   # MAIN DIR:METEOR
   #/mnt/ams2/meteor_archive/[STATION_ID]/METEOR/[YEAR]
   main_dir = METEOR + get_station_id() + METEOR + str(year)
   
   # Get the available month for the current year 
   [os.path.join(main_dir, o) for o in os.listdir(main_dir) 
      if os.path.isdir(os.path.join(main_dir,o))]