import os
import glob
import sys

from lib.Old_JSON_converter import move_old_detection_to_archive
from lib.CGI_Tools import redirect_to


# Convert an old detection by updating the JSON and moving the file to /meteor_archive/
#json_file = sys.argv[1]
#video_file = sys.argv[2]
#move_old_detection_to_archive(json_file,video_file,True)



# CONVERT JSON ONLY
#python3 ./pythonv2/old_json_inline_converter.py /mnt/ams2/meteors/2019_10_25/2019_10_25_07_56_03_000_010041-trim1298.json /mnt/ams2/meteors/2019_10_25/2019_10_25_07_56_03_000_010041-trim1298.mp4 /mnt/ams2/meteors/2019_10_25/2019_10_25_07_56_01_000_010041-trim-1298-HD-meteor.mp4
#move_old_detection_to_archive('/mnt/ams2/meteors/2019_10_23/2019_10_23_04_33_17_000_010041-trim0594.json','/mnt/ams2/meteors/2019_10_23/2019_10_23_04_33_17_000_010041-trim0594.mp4','/mnt/ams2/meteors/2019_10_23/2019_10_23_04_33_14_000_010041-trim-594-HD-meteor.mp4')
move_old_detection_to_archive(sys.argv[1],sys.argv[2],sys.argv[3])
