# NOTES:
#  "timestamp":"2015-10-15T18:23:01Z"})

import socket
import time
import datetime
import traceback
import sys

TCP_IP = '199.108.99.62' # C2M TCP Server
TCP_PORT = 3001          # C2M TCP Port
BUFFER_SIZE = 1024       # TCP Message Buffer

# Return 1 if GPS is non-zero and in range
# This simple function is biased toward no false readings in US
# It rejects England, and many other places...
def isGpsValid(lat, lng):
   lat = float(lat)
   lng = float(lng)
   gps_valid = 1
   if lat < 1 and lat > -1:
      gps_valid = 0
   if lng < 1 and lng > -1:
      gps_valid = 0
   if lat > 89 or lat < -89:
      gps_valid = 0
   if lng > 179 or lng < -179:
      gps_valid = 0
   return gps_valid

def TCP_send(MESSAGE):
    length = len(MESSAGE)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TCP_IP, TCP_PORT))
    if s.send(MESSAGE):
        #print 'Sending TCP Message to C2M: ' + MESSAGE + 'at ' + str(datetime.datetime.now())
        return True
    else:
        print 'ERROR: SendLocRssi2Plasma failed'
        return False
    s.close()
    del MESSAGE

# Parser tells you how to map multisensor data names from Ingenu RACM parser to C2m by Plasma
def sendData2C2m(parser, api_key, feed_key, ms_data):
    time.sleep(1.1) # Delay required by M2x, could be optimized, cause they specify 1 sec/stream

    for d_outer in ms_data:
       # Create TCP message payload expected by c2m. For now, this is per single timestamped
       # multisensor measurement.
       # preamble:
       MESSAGE = 'apikey:'+api_key+',feedId:'+feed_key+',feed='
       deviceDateTime = d_outer['timeStamp']
       meas_list = d_outer['meas_list'] # list of dicts with {sensorName measVal}
       meas_valid = 0

       try:
          if parser == 'temperature_humidity_1':
             print 'meas_list' , meas_list
             for d_inner in meas_list:
                if d_inner['sensorName'] == 'temp_f':
                   temp_f = str(d_inner['measVal'])
                elif d_inner['sensorName'] == 'humidity':
                   humidity = str(d_inner['measVal'])
             meas_valid = 1
             MESSAGE += 'tempf,'+temp_f+'|humidity,'+humidity+'|devicedatetime,'+deviceDateTime
   
          elif parser == 'intrusion_1':
             for d_inner in meas_list:
                if d_inner['sensorName'] == 'temp_c':
                   temp_c = str(d_inner['measVal'])
                elif d_inner['sensorName'] == 'intrusion':
                   intrusion = str(d_inner['measVal'])
             meas_valid = 1
             MESSAGE += 'intrusion,'+intrusion+'|tempc,'+temp_c+'|devicedatetime,'+deviceDateTime
   
          elif parser == 'serial_1':
             for d_inner in meas_list:
                if d_inner['sensorName'] == 'serial':
                   serial = d_inner['measVal']
             meas_valid = 1
             MESSAGE += 'serial,'+serial+'|devicedatetime,'+deviceDateTime
   
          elif parser == 'gps_2':
             for d_inner in meas_list:
                if d_inner['sensorName'] == 'lat':
                   lat = str(d_inner['measVal'])
                elif d_inner['sensorName'] == 'lng':
                   lng = str(d_inner['measVal'])
                elif d_inner['sensorName'] == 'rssi':
                   rssi = str(d_inner['measVal'])
             if isGpsValid(lat, lng):
                meas_valid = 1
                MESSAGE += 'lat,'+lat+'|lng,'+lng+'|rssi,'+rssi+'|devicedatetime,'+deviceDateTime
             else:
                print 'INFO: Invalid GPS coordinates, not sending to c2m', 'lat = ', lat, 'lng = ', lng
          else:
             print 'ERROR: unknown parser in sendData2C2m.py ', parser
       except:
          traceback.print_exc()
          print 'sendData2C2m.py: Exception(1): ', sys.exc_info()[0]
          print 'meas_list =', meas_list

   
       if meas_valid:
          TCP_send(MESSAGE)
          print 'Sent to C2M:', MESSAGE, str(datetime.datetime.now())

    return '0' # don't know what could be sent in error case

###   MAIN   #############################################################################
if __name__ == '__main__':

   api_key = 'GIS9jFLaBaZrkb3NTWjwM1nbz5gLDN'
   feed_key = 'KZHbPInWmXwob5FXkxdAhNTeRNpc/xqyoBWLM1T7Hak='
   timestamp = '2015-04-08T11:23:45Z'
   lat = '32.7782'
   lng = '-96.7753'
   rssi = '-105'
   sendLocRssi2Plasma(api_key, feed_key, timestamp, lat, lng, rssi)

