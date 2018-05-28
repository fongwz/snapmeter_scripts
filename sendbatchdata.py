# rest2m2x.py Pulls UL SDUs from ORW REST interface and pushes data to M2X99
# Pull an SDU, Look up what parser to use, Parse the SDU, For each measurement in the SDU send it individually to M2X
# Notes: 
# 1) M2X claims it has a 1 second per stream (meas) max rate, and 1000 meas/day/IPAddr, so implement pacing
# 2) If the device is multi-sensor, need to send one message per sensor (and per timestamped measurement).
# 3) I observe the web page limit is 30 locations per GPS sensor, so I set GPS_MINUTES_TO_DECIMATE = 5

import sys
import time
import datetime
import json
from sendAsciiDl2Rest import sendAsciiDl2Rest
import parsers

# -------------------------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------------------------
# This file contains the SDU ID (UUID) of the next UL SDU. It provides non-volatile storage,
# so we only fetch the latest SDUs, in case this script is stopped/restarted for any reason.
#gaowei
#sendAsciiDl2Rest(text, node_id_hex)
sendtime = time.strftime( "%Y-%m-%d %H:%M:%S", time.localtime() )
print sendtime
i = 1
if (sys.argv[1] != ''):
   node_id_hex = sys.argv[1]
else:
   node_id_hex = "0x000724ff"

if (sys.argv[2] != ''):
   sleeptime = float(sys.argv[2])
else:
   sleeptime = 1.0

if (sys.argv[3] != ''):
   count = int(sys.argv[3])
else:
   count = 100

if (sys.argv[4] != ''):
   data = sys.argv[4]
else:
   data = "1111111"

while i <= count:
    try:
       text =str(i)+ " " + data
       sendtime1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
       sendAsciiDl2Rest(text +"  sd_time:"+sendtime1, node_id_hex)
       time.sleep( sleeptime )
       i = i +1
    except KeyboardInterrupt:
       sys.exit()
