#!/usr/bin/python3

from sympy import Point3D, Line3D, Segment3D, Plane
import sys
import numpy as np
import matplotlib as mpl
#mpl.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from lib.UtilLib import convert_filename_to_date_cam
from lib.FileIO import cfe
import simplekml

from mpl_toolkits import mplot3d
import math
from lib.FileIO import load_json_file, save_json_file

def make_kmz(meteor):
   kml = simplekml.Kml()

   for key in meteor:
      if "obs" in key:
         obs_lon = meteor[key]['x2_lat'] 
         obs_lat = meteor[key]['y2_lon'] 
         point = kml.newpoint(name=key,coords=[(obs_lon,obs_lat)])

   for key in meteor['meteor_points_lat_lon']:
      for lon,lat,alt in meteor['meteor_points_lat_lon'][key]:
         alt = alt * 1000
         print(lat,lon,alt)
         point = kml.newpoint(coords=[(lon,lat,alt)])
         point.altitudemode = simplekml.AltitudeMode.relativetoground
   kml.save("test.kml")

def plot_meteor_ms(meteor):
   fig_file = meteor_file.replace(".json", "-fig2.png")
   fig = plt.figure()
   ax = Axes3D(fig)
   xs = []
   ys = []
   zs = []
  
   for key in meteor:
      if "obs" in key:

      #nmx = (mx / (111.32 * math.cos(meteor['obs1']['ObsY']*math.pi/180))) + meteor['obs1']['lat']
      #nmy = (my / (111.14)) + meteor['obs1']['lon']

         #ox = (float(meteor[key]['ObsX'])/ (111.32 * math.cos(meteor['obs1']['ObsY']*math.pi/180))) + meteor['obs1']['lat']
         #oy = (float(meteor[key]['ObsY']) / 111.14) + meteor['obs1']['lon']

         ox = meteor['obs1']['lon'] + meteor[key]['ObsX'] / (111.32 * math.cos(meteor['obs1']['lat']*math.pi/180))
         oy = meteor['obs1']['lat'] + (meteor[key]['ObsY'] / 111.14) 

         xs.append(ox)
         ys.append(oy)
         zs.append(float(meteor[key]['ObsZ']))
         ax.text(ox, oy,meteor[key]['ObsZ'],meteor[key]['station_name'],fontsize=10)
         meteor[key]['x2_lat'] = ox
         meteor[key]['y2_lon'] = oy
       

   #ax.text(Obs1Lon, Obs1Lat,Obs1Alt,Obs1Station,fontsize=10)
   ax.scatter3D(xs,ys,zs,c='r',marker='o')

   xs = []
   ys = []
   zs = []
   plane_colors = {}
   plane_colors['obs1'] = 'b'
   plane_colors['obs2'] = 'g'
   plane_colors['obs3'] = 'y'
   cc = 0
   meteor_points_lat_lon = {}
   #long = long1 + BolideX / (111.32 * math.cos(lat1*math.pi/180));
   #lat = lat1 + (BolideY / 111.14);
   for key in meteor['meteor_points']:
      plane_key,line_key = key.split("-")
      meteor_points_lat_lon[key] = []
      ox = meteor['obs1']['lon'] + meteor[line_key]['ObsX'] / (111.32 * math.cos(meteor['obs1']['lat']*math.pi/180))
      oy = meteor['obs1']['lat'] + (meteor[line_key]['ObsY'] / 111.14) 

      oz = meteor[line_key]['ObsZ']
      for x,y,z in meteor['meteor_points'][key]:
         x = meteor['obs1']['lon'] + x / (111.32 * math.cos(meteor['obs1']['lat']*math.pi/180))
         y = (y / 111.14) + meteor['obs1']['lat']


         xs.append(x)
         ys.append(y)
         zs.append(z)
         meteor_points_lat_lon[key].append((x,y,z))
         color = plane_colors[line_key]
         ax.plot([ox,x],[oy,y],[oz,z],c=color) 
   ax.scatter3D(xs,ys,zs,c='r',marker='x')
   meteor['meteor_points_lat_lon'] = meteor_points_lat_lon


   plt.show()
   return(meteor)


def plot_meteor_obs(meteor, meteor_file):
   fig_file = meteor_file.replace(".json", "-fig2.png")
   fig = plt.figure()
   ax = Axes3D(fig)
   #lat = lat1 + (BolideY / 111.14);
   #long = long1 + BolideX / (111.32 * math.cos(lat1*math.pi/180));

   Obs1Station = meteor['obs1']['station_name']
   Obs1Lon = (meteor['obs1']['ObsX'] / (111.32 * math.cos(meteor['obs1']['ObsY']*math.pi/180))) + meteor['obs1']['lat']
   Obs1Lat = (meteor['obs1']['ObsY'] / (111.14)) + meteor['obs1']['lon']
   Obs1Alt = meteor['obs1']['ObsZ'] 
   ax.text(Obs1Lon, Obs1Lat,Obs1Alt,Obs1Station,fontsize=10)

   Obs2Station = meteor['obs2']['station_name']
   Obs2Lon = (meteor['obs2']['ObsX'] / (111.32 * math.cos(meteor['obs2']['ObsY']*math.pi/180))) + meteor['obs2']['lat']
   Obs2Lat = (meteor['obs2']['ObsY'] / (111.14)) + meteor['obs2']['lon']
   Obs2Alt = meteor['obs2']['ObsZ'] 
   ax.text(Obs2Lon, Obs2Lat,Obs2Alt,Obs2Station,fontsize=10)

   print("OBS1:", Obs1Lon, Obs1Lat, Obs1Alt)
   print("OBS2:", Obs2Lon, Obs2Lat, Obs2Alt)

   #x = [meteor['obs1']['ObsX'], meteor['obs2']['ObsX']]
   #y = [meteor['obs1']['ObsY'], meteor['obs2']['ObsY']]
   #z = [meteor['obs1']['ObsZ'], meteor['obs2']['ObsZ']]

   x = [Obs1Lon, Obs2Lon]
   y = [Obs1Lat, Obs2Lat]
   z = [Obs1Alt, Obs2Alt]
   ax.scatter3D(x,y,z,c='r',marker='o')
 
   meteor_points1 = meteor['meteor_points1']
   meteor_points2 = meteor['meteor_points2']

   for mx,my,mz in meteor_points1:
      nmx = (mx / (111.32 * math.cos(meteor['obs1']['ObsY']*math.pi/180))) + meteor['obs1']['lat']
      nmy = (my / (111.14)) + meteor['obs1']['lon']
      ax.plot([Obs1Lon,nmx],[Obs1Lat,nmy],[Obs1Alt,mz],c='g')
   for mx,my,mz in meteor_points1:
      nmx = (mx / (111.32 * math.cos(meteor['obs1']['ObsY']*math.pi/180))) + meteor['obs1']['lat']
      nmy = (my / (111.14)) + meteor['obs1']['lon']
      ax.plot([Obs2Lon,nmx],[Obs2Lat,nmy],[Obs2Alt,mz],c='b')
   ax.set_xlabel('Longitude')
   ax.set_ylabel('Latitude')
   ax.set_zlabel('Altitude')

   plt.savefig(fig_file)

def plot_meteor(meteor, meteor_file):
   fig_file = meteor_file.replace(".json", "-fig1.png")
   fig = plt.figure()
   ax = Axes3D(fig)
   #print(meteor)

   # plot observers
   #ax.scatter3D(x,y,z,c='r',marker='o')

   meteor_points1 = meteor['meteor_points1']
   meteor_points2 = meteor['meteor_points2']

   xs = []
   ys = []
   zs = []
   for mx,my,mz in meteor_points1:
      if mz > 10:
         xs.append(mx)
         ys.append(my)
         zs.append(mz)
   ax.scatter3D(xs,ys,zs,marker='x')

   for mx,my,mz in meteor_points2:
      if mz > 10:
         xs.append(mx)
         ys.append(my)
         zs.append(mz)
   ax.scatter3D(xs,ys,zs,marker='o')

   plt.show()
   plt.savefig(fig_file)

def compute_ms_solution(meteor):
   vfact = 180
   for key in meteor:
      if "obs" in key:
         vp = []
         for data in meteor[key]['mo_vectors'] :
            vx,vy,vz = data
            veX = meteor[key]['ObsX'] + ( vx * vfact)
            veY = meteor[key]['ObsY'] + ( vy * vfact)
            veZ = meteor[key]['ObsZ'] + ( vz * vfact)
            vp.append((veX,veY,veZ))
         meteor[key]['vector_points'] = vp

   planes = {}
   for key in meteor:
      if "obs" in key :
         mod = meteor[key]
         print(mod) 
         planes[key] = Plane( \
            Point3D(mod['ObsX'],mod['ObsY'],mod['ObsZ']), \
            Point3D(mod['vector_points'][0][0],mod['vector_points'][0][1],mod['vector_points'][0][2]), \
            Point3D(mod['vector_points'][-1][0],mod['vector_points'][-1][1], mod['vector_points'][-1][2]))
   print(planes)

   meteor_points = {}


   for pkey in planes: 
      plane = planes[pkey]
      for key in meteor:
         if "obs" in key and key != pkey:
            mod = meteor[key]
            point_key = pkey + "-" + key
            meteor_points[point_key] = []
            for veX,veY,veZ in mod['vector_points']:

               print("LINE DATA:", mod['ObsX'],mod['ObsY'],mod['ObsZ'],veX,veY,veZ)
               line = Line3D(Point3D(mod['ObsX'],mod['ObsY'],mod['ObsZ']),Point3D(veX,veY,veZ))

               inter = plane.intersection(line)
               print(inter[0])
               mx = float((eval(str(inter[0].x))))
               my = float((eval(str(inter[0].y))))
               mz = float((eval(str(inter[0].z))))
               meteor_points[point_key].append((mx,my,mz))

   meteor['meteor_points'] = meteor_points
   #print(meteor_points)
   return(meteor)      
         

def compute_solution(meteor):
   # vector factor
   vfact = 180 

   # plot line vectors for obs1
   Obs1X = meteor['obs1']['ObsX']
   Obs1Y = meteor['obs1']['ObsY']
   Obs1Z = meteor['obs1']['ObsZ']
   mv = meteor['obs1']['vectors']
   vp1 = []
   for data in mv:
      vx,vy,vz = data
      veX = Obs1X + ( vx * vfact)
      veY = Obs1Y + ( vy * vfact)
      veZ = Obs1Z + ( vz * vfact)
      vp1.append((veX,veY,veZ))
   plane1 = Plane(Point3D(Obs1X,Obs1Y,Obs1Z),Point3D(vp1[0][0],vp1[0][1],vp1[0][2]),Point3D(vp1[-1][0], vp1[-1][1], vp1[-1][2]))

   # plot line vectors for obs2
   Obs2X = meteor['obs2']['ObsX']
   Obs2Y = meteor['obs2']['ObsY']
   Obs2Z = meteor['obs2']['ObsZ']
   mv = meteor['obs2']['vectors']
   vp2 = []
   for data in mv:
      vx,vy,vz = data
      veX = Obs2X + ( vx * vfact)
      veY = Obs2Y + ( vy * vfact)
      veZ = Obs2Z + ( vz * vfact)
      vp2.append((veX,veY,veZ))

 # plot line vectors for obs2
   Obs2X = meteor['obs2']['ObsX']
   Obs2Y = meteor['obs2']['ObsY']
   Obs2Z = meteor['obs2']['ObsZ']
   mv = meteor['obs2']['vectors']
   vp2 = []
   for data in mv:
      vx,vy,vz = data
      veX = Obs2X + ( vx * vfact)
      veY = Obs2Y + ( vy * vfact)
      veZ = Obs2Z + ( vz * vfact)
      vp2.append((veX,veY,veZ))

   plane2 = Plane(Point3D(Obs2X,Obs2Y,Obs2Z),Point3D(vp2[0][0],vp2[0][1],vp2[0][2]),Point3D(vp2[-1][0], vp2[-1][1], vp2[-1][2]))

   meteor_points1 = []
   meteor_points2 = []

   for veX,veY,veZ in vp1:
      line = Line3D(Point3D(Obs1X,Obs1Y,Obs1Z),Point3D(veX,veY,veZ))

      inter = plane2.intersection(line)
      mx = float((eval(str(inter[0].x))))
      my = float((eval(str(inter[0].y))))
      mz = float((eval(str(inter[0].z))))
      meteor_points1.append((mx,my,mz))

   for veX,veY,veZ in vp2:
      line = Line3D(Point3D(Obs2X,Obs2Y,Obs2Z),Point3D(veX,veY,veZ))

      inter = plane1.intersection(line)
      mx = float((eval(str(inter[0].x))))
      my = float((eval(str(inter[0].y))))
      mz = float((eval(str(inter[0].z))))
      meteor_points2.append((mx,my,mz))

   xs = []
   ys = []
   zs = []
   for mx,my,mz in meteor_points1:
      xs.append(mx)
      ys.append(my)
      zs.append(mz)

   for mx,my,mz in meteor_points2:
      xs.append(mx)
      ys.append(my)
      zs.append(mz)

   meteor['meteor_points1'] = meteor_points1
   meteor['meteor_points2'] = meteor_points2
   meteor['vp1'] = vp1 
   meteor['vp2'] = vp2 
   return(meteor)





def plot_xyz(x,y,z,meteor):
   vfact = 180 
   fig = plt.figure()
   ax = Axes3D(fig)
   #line1, line2 = make_lines_for_obs(cart1)
   #x = [line1[0][0],line1[0][1],line2[0][1]]
   #y = [line1[1][0],line1[1][1],line2[1][1]]
   #z = [line1[2][0],line1[2][1],line2[2][1]]


   ax.scatter3D(x,y,z,c='r',marker='o')


   # plot line vectors for obs1 
   Obs1X = meteor['obs1']['ObsX']
   Obs1Y = meteor['obs1']['ObsY']
   Obs1Z = meteor['obs1']['ObsZ']
   mv = meteor['obs1']['vectors']
   vp = []
   for data in mv:
      vx,vy,vz = data
      veX = Obs1X + ( vx * vfact)
      veY = Obs1Y + ( vy * vfact)
      veZ = Obs1Z + ( vz * vfact)
      #ax.plot([Obs1X,veX],[Obs1Y,veY],[Obs1Z,veZ], color='green')
      vp.append((veX,veY,veZ))


   plane1 = Plane(Point3D(Obs1X,Obs1Y,Obs1Z),Point3D(vp[0][0],vp[0][1],vp[0][2]),Point3D(vp[-1][0], vp[-1][1], vp[-1][2]))

   # plot line vectors for obs2
   Obs2X = meteor['obs2']['ObsX']
   Obs2Y = meteor['obs2']['ObsY']
   Obs2Z = meteor['obs2']['ObsZ']
   mv = meteor['obs2']['vectors']
   vp2 = []
   for data in mv:
      vx,vy,vz = data
      veX = Obs2X + ( vx * vfact)
      veY = Obs2Y + ( vy * vfact)
      veZ = Obs2Z + ( vz * vfact)
      vp2.append((veX,veY,veZ))

   plane2 = Plane(Point3D(Obs2X,Obs2Y,Obs2Z),Point3D(vp2[0][0],vp2[0][1],vp2[0][2]),Point3D(vp2[-1][0], vp2[-1][1], vp2[-1][2]))

   meteor_points1 = []
   meteor_points2 = []

   for veX,veY,veZ in vp:
      line = Line3D(Point3D(Obs1X,Obs1Y,Obs1Z),Point3D(veX,veY,veZ))

      inter = plane2.intersection(line)
      mx = float((eval(str(inter[0].x))))
      my = float((eval(str(inter[0].y))))
      mz = float((eval(str(inter[0].z))))
      #ax.scatter3D(mx,my,mz,c='r',marker='x')
      ax.plot([Obs1X,mx],[Obs1Y,my],[Obs1Z,mz],c='g')
      meteor_points1.append((mx,my,mz))


   for veX,veY,veZ in vp2:
      line = Line3D(Point3D(Obs2X,Obs2Y,Obs2Z),Point3D(veX,veY,veZ))

      inter = plane1.intersection(line)
      mx = float((eval(str(inter[0].x))))
      my = float((eval(str(inter[0].y))))
      mz = float((eval(str(inter[0].z))))
      #ax.scatter3D(mx,my,mz,c='r',marker='x')
      ax.plot([Obs2X,mx],[Obs2Y,my],[Obs2Z,mz],c='b')
      meteor_points2.append((mx,my,mz))

   xs = []
   ys = []
   zs = []
   for mx,my,mz in meteor_points1:
      xs.append(mx)
      ys.append(my)
      zs.append(mz)
   ax.scatter3D(xs,ys,zs,marker='x')

   for mx,my,mz in meteor_points2:
      xs.append(mx)
      ys.append(my)
      zs.append(mz)
   ax.scatter3D(xs,ys,zs,marker='o')


   #ax.set_zlim(0, 140)
   #ax.set_xlim(np.min(x)-100, np.max(x)+100)
   #ax.set_ylim(np.min(y)-100, np.max(y)+100)

   ax.set_xlabel('X Label')
   ax.set_ylabel('Y Label')
   ax.set_zlabel('Z Label')
   plt.show()

def make_obs_vectors(mo):
   fc = 0
   mo_vectors = []
   for data in mo['meteor_frame_data']:
      az = data[9]
      el = data[10]
      vx = math.sin(math.radians(az)) * math.cos(math.radians(el))
      vy = math.cos(math.radians(az)) * math.cos(math.radians(el))
      vz = math.sin(math.radians(el))
      mo_vectors.append((vx,vy,vz))
   return(mo_vectors)

def setup_obs(meteors_obs):

   meteor = {}
   mos = {}
   lats = []
   lons = []
   alts = []
   for i in range(1,len(meteor_obs)+1):
      mokey = 'mo' + str(i)
      obskey = 'obs' + str(i)
      mo = meteor_obs[mokey]
      mos[mokey] = mo
      meteor[obskey] = {}
      lats.append(float(mos[mokey]['cal_params']['site_lat']))
      lons.append(float(mos[mokey]['cal_params']['site_lng']))
      alts.append(float(mos[mokey]['cal_params']['site_alt']) / 1000)

   # determine base lat/lon (use first observer) 


   Obs1Z = alts[0]
   Obs1Y = 0 
   Obs1X = 0 

   meteor['obs1']['station_name'] = mo1['station_name']
   meteor['obs1']['lat'] = lats[0]
   meteor['obs1']['lon'] = lons[0]
   meteor['obs1']['alt'] = alts[0]
   meteor['obs1']['ObsX'] = Obs1X
   meteor['obs1']['ObsY'] = Obs1Y
   meteor['obs1']['ObsZ'] = Obs1Z
   meteor['obs1']['mo_vectors'] = make_obs_vectors(meteor_obs['mo1'])


   for i in range(2,len(meteor_obs)+1):
      obskey = "obs" + str(i) 
      mokey = 'mo' + str(i)



      meteor[obskey]['station_name'] = meteor_obs[mokey]['station_name']
      meteor[obskey]['lat'] = lats[i-1]
      meteor[obskey]['lon'] = lons[i-1]
      meteor[obskey]['alt'] = alts[i-1]
      meteor[obskey]['ObsZ'] = alts[i-1] - alts[0]
      meteor[obskey]['ObsY'] = (lats[i-1]- lats[0])*111.14
      meteor[obskey]['ObsX'] = (lons[i-1] - lons[0])*111.32*math.cos(((lats[0]+lats[i-1])/2)*math.pi/180)
      meteor[obskey]['mo_vectors'] = make_obs_vectors(meteor_obs[mokey])

   return(meteor)


if len(sys.argv) == 3:
   obs1_file, obs2_file = sys.argv[1], sys.argv[2]
   hd_datetime, cam1, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(obs1_file)
   hd_datetime, cam2, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(obs2_file)
   meteor_file = "/mnt/ams2/multi_station/" + hd_y + "_" + hd_m + "_" + hd_d + "/" + hd_y + "_" + hd_m + "_" + hd_d + "_" + hd_h + "_" + hd_M + "_" + hd_s + "_" + cam1 + "_" + cam2 + "-solved.json" 
   mo1 = load_json_file(obs1_file)
   mo2 = load_json_file(obs2_file)
   meteor_obs = {}
   meteor_obs['mo1'] = mo1
   meteor_obs['mo2'] = mo2

if len(sys.argv) == 4:
   obs1_file, obs2_file,obs3_file = sys.argv[1], sys.argv[2], sys.argv[3]
   hd_datetime, cam1, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(obs1_file)
   hd_datetime, cam2, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(obs2_file)
   hd_datetime, cam3, hd_date, hd_y, hd_m, hd_d, hd_h, hd_M, hd_s = convert_filename_to_date_cam(obs3_file)
   meteor_file = "/mnt/ams2/multi_station/" + hd_y + "_" + hd_m + "_" + hd_d + "/" + hd_y + "_" + hd_m + "_" + hd_d + "_" + hd_h + "_" + hd_M + "_" + hd_s + "_" + cam1 + "_" + cam2 + "_" + cam3 + "-solved.json" 
   mo1 = load_json_file(obs1_file)
   mo2 = load_json_file(obs2_file)
   mo3 = load_json_file(obs3_file)
   meteor_obs = {}
   meteor_obs['mo1'] = mo1
   meteor_obs['mo2'] = mo2
   meteor_obs['mo3'] = mo3

if cfe(meteor_file) == 0:
   meteor = setup_obs(meteor_obs)
   #meteor = compute_solution(meteor)
   meteor = compute_ms_solution(meteor)
else:
   meteor = load_json_file(meteor_file)
   meteor = plot_meteor_ms(meteor)
#plot_meteor_obs(meteor, meteor_file)
save_json_file(meteor_file, meteor)
make_kmz(meteor)


