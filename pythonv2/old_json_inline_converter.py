import os
import glob
import sys

from lib.Old_JSON_converter import move_old_detection_to_archive


# Convert an old detection by updating the JSON and moving the file to /meteor_archive/
#json_file = sys.argv[1]
#video_file = sys.argv[2]
#move_old_detection_to_archive(json_file,video_file,True)


# CONVERT JSON ONLY
move_old_detection_to_archive('/mnt/ams2/meteors/2019_10_23/2019_10_23_04_33_17_000_010041-trim0594.json','/mnt/ams2/meteors/2019_10_23/2019_10_23_04_33_17_000_010041-trim0594.mp4','/mnt/ams2/meteors/2019_10_23/2019_10_23_04_33_14_000_010041-trim-594-HD-meteor.mp4')