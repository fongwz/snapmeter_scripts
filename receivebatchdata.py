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
from getNextUlSdu import getNextUlSdu
from getNextUlSdu import incrementNextUlSduPointer
from sendStream2M2x import sendStream2M2x
#from sendStream2Thingworx import sendStream2Thingworx
from sendMqtt2Thingworx import sendMqtt2Thingworx
from sendLocRssi2M2x import sendLocRssi2M2x
from sendData2C2m import sendData2C2m
from getDeviceInfo import getDeviceInfo
from findJoinedAp import findJoinedAp
from sendAsciiDl2Rest import sendAsciiDl2Rest
import parsers

def getSduInfo(sdu_list, index):
    sdu = sdu_list[index]
    sdu_id = sdu[0]
    payload = sdu[1]
    node_id_hex = sdu[2] # note intellect reports hex node id not dec as of 3/16/2016
    rx_timestamp = sdu[3]
    #gaowei
    print "\nULSDU begin:\n"
    print sdu
    print "\nULSDU end\n"
    return(sdu_id, node_id_hex, rx_timestamp, payload)

# Invert a one bit binary number
def flipBit(input):
   if input == 0:
      output = 1
   elif input == 1:
      output = 0
   else:
      output = input
   return output

# Convert date from REST IF (string) to python datetime, and change timezone to GMT
#   input date format      = '2015-08-10T17:14:20-07:00'
def convertToDateTime(input_date):
   # Strip off decimal part of seconds, if it is there
   a = input_date.find('.')
   if a != -1:
      input_date = input_date[:a] + input_date[a+7:]
   # Small conversion on input time to handle timezone, python can't
   # if there is an appended timezone (ex. "-07:00")
   if len(input_date)==25:
      tzHours = int(input_date[-6:-3])
      input_date = input_date[0:-6]
   elif len(input_date)==20 and input_date[-1:]=='Z':
      input_date = input_date[0:-1]
      tzHours = 0
   elif len(input_date)==19 and input_date[-9]=='T':
      tzHours = 0
   else:
      print 'WARNING: unexpected date format in rest2m2x.py', input_date
      tzHours = 0

   # Python doesn't have datetime.strptime (my version 2.6.6)
   input_t = time.strptime(input_date, '%Y-%m-%dT%H:%M:%S')
   # some hoops you have to jump through in python:
   input_dt = datetime.datetime.fromtimestamp(time.mktime(input_t))
   input_dt = input_dt - datetime.timedelta(hours=tzHours)
   return input_dt

# Convert a hexadicamal string of form '656667' to text 'ABC'
# for use displaying serial input
def hex2text(hex_string):
   txt_string = ''
   hasIllegalChar = 0
   for i in range(len(hex_string)/2):
      byte = hex_string[2*i:2*i+2]
      ascval = int(byte, 16)
      # Note we skip illegal characters to avoid JSON UTF-8 errors
      if ascval <= 127:
         txt_string += chr(ascval)
      else:
         hasIllegalChar = 1

   if hasIllegalChar:
      print 'ERROR: serial text contains illegal characters(ASCII value > 127), check baud rate'
   return txt_string
      
# Should I decimate this GPS?
#   - timestamp is a datetime
def shouldDecimate(nodeIdHex, timestamp):
   GPS_MINUTES_TO_DECIMATE = 5
   must_decimate = 0
   node_in_list = 0

   for d in gpsHistoryList:
      if d['nodeIdHex'] == nodeIdHex:
         node_in_list = 1
         if timestamp - d['timestamp'] <= datetime.timedelta(seconds=0):
            must_decimate = 1
         else:
            # Because gpsHistoryList is mutable, this will update 
            # the timestamp of the node in gpsHistoryList
            # to this timestamp plus 1 minute
            d['timestamp'] = timestamp + datetime.timedelta(minutes=GPS_MINUTES_TO_DECIMATE)

   if not node_in_list:
      next_timestamp = timestamp + datetime.timedelta(minutes=GPS_MINUTES_TO_DECIMATE)
      gpsHistoryList.append({'nodeIdHex':nodeIdHex, 'timestamp':next_timestamp})
       
   return must_decimate

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

# Convert a list of dictionaries, each containing timestamp, sensorType, and data
# to a list of dictionaries, each containing timestamp and a list of all sensorType/Meas
# at that timestamp
# The parsers return the first format, ATT M2X expects streams in the first format
# c2m by Plasma (and other head ends) expects Multisensor measurements in the 2nd format
# Input format: [{sensorType:foo,data:bar,timestamp:foobar},...]
# Outputformat: [{timestamp:foobar,meas_list:[{sensorName:foo, dataval:bar},{sensorName:foo2, dataval:bar2}]},...]
def convertToMultiSensor (data_in):
   ms_data = [] 

   for i in range(len(data_in)):
      # 1st pass - create timestamp entries
      timestamp = data_in[i]['timeStamp'].strftime("%Y-%m-%dT%H:%M:%SZ") # format m2x expects
      found_dup = 0
      for d in ms_data:
        if d['timeStamp'] == timestamp:
           found_dup = 1 
      # No duplicates: only add unique timestamps to list
      if not found_dup:
         ms_data.append({'timeStamp':timestamp, 'meas_list':[]})

   for i in range(len(data_in)):
      # 2nd pass - Add measurements to timestamps
      timestamp = data_in[i]['timeStamp'].strftime("%Y-%m-%dT%H:%M:%SZ") # format m2x expects
      for d in ms_data:
        if d['timeStamp'] == timestamp:
           # Write to ms_data: This only works cause dictionaries are mutable
           d['meas_list'].append({'sensorName':data_in[i]['sensorName'], 'measVal':data_in[i]['data']})
   return ms_data

# ---------------------------------------------------------------------------------------------------
# Change a UTC datetime GPS was received to a ULP Date (RPMA 4.65 sec frames since Jan1, 2008)
# ---------------------------------------------------------------------------------------------------
def getUlpFrame(utc_datetime):
   ulp_epoch = datetime.datetime(2008, 1, 1)
   delta = utc_datetime - ulp_epoch
   ulp_day_frames = 18600 * delta.days
   ulp_sec = utc_datetime.hour*60*60 + utc_datetime.minute*60 + utc_datetime.second + utc_datetime.microsecond/1e6
   sfn = int(ulp_sec/4.644864)
   ulp_frame = ulp_day_frames + sfn
   return str(ulp_frame) # return a string for csv file writing       

# Write the GPS/RSSI information to a .csv file, per node
# create the file if it doesn't exist, based on the first rx timestamp
def writeGps2Csv(node_id_hex, lat, lng, rssi, utc_rx_timestring, ap_mac, ulp_frame):
   match = next((d for d in gpsFileList if int(d['node_id_hex'], 16) == int(node_id_hex, 16)), None)
   # Case where a file has not been created yet
   if not match:
      fname = 'gps_' + str(node_id_hex) + '_' + utc_rx_timestring + '.csv'
      fname = fname.replace(' ','_') # get rid of spaces in filename
      fname = fname.replace(':','_') # get rid of colons in filename
      try:
         with open(fname,'w') as csv_file:
            gpsFileList.append({'node_id_hex':node_id_hex, 'csv_file':fname})
            csv_file.write('nodeIdHex,lat,lng,rssi,utc_rx_timestring,ap_mac,ulp_frame\n') # Header
            gps_list = [nodeIdHex,lat,lng,rssi,utc_rx_timestring,ap_mac,ulp_frame]
            gps_str = makeCsvRow(gps_list)
            csv_file.write(gps_str)
      except:
         print "ERROR(rest2m2x.py): can't open csv_file: %s to write GPS RSSI info" % (fname)
         print sys.exc_info()[0]
   # Case where file exists
   else:
      fname = match['csv_file']
      gps_list = [nodeIdHex,lat,lng,rssi,utc_rx_timestring,ap_mac,ulp_frame]
      gps_str = makeCsvRow(gps_list)
      try:
         with open(fname,'a') as csv_file:
            csv_file.write(gps_str) # 2nd - Nth Data
      except:
         print "ERROR(rest2m2x.py): can't open csv_file: %s to append GPS RSSI info" % (fname)
         print sys.exc_info()[0]

# Helper function to form up the comma separated text in a row
def makeCsvRow(list_of_val):
   s = ''
   for v in list_of_val:
      s = s + str(v) + ','
   s = s[:-1] # get rid of last comma
   s = s + '\n'
   return s

# -------------------------------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------------------------------
# This file contains the SDU ID (UUID) of the next UL SDU. It provides non-volatile storage,
# so we only fetch the latest SDUs, in case this script is stopped/restarted for any reason.
nextSduFile = 'lastFetchedMssgId.json'
gpsHistoryList = [] # list of dicts timestamp vs node ID for decimation
gpsFileList = [] # list of dicts used in writeGps2Csv()

logfilename = time.strftime( "%Y%m%d%H%M%S", time.localtime() )
logfilename = "Rxlog\\" + logfilename + '.txt'


# Get the Devices, their parsers, and head end configurations
with open('Devices.json','r') as infile:
    devices = json.load(infile)
    infile.close()

# Check if you will pull based on a Start Date, and set up the pointer as needed
# Note: If you want to pull messages starting from a Start Date, change the startupConfig.json file
# The same applies to setting an End Date
with open('startupConfig.json','r') as infile:
    cfg = json.load(infile)
    infile.close()
    if cfg['useStartDatetime']=='1':
       startUtcDatetime = eval(cfg['startUtcDatetime'])
       (status, last_sdu_id, size, sdu_list) = getNextUlSdu(nextSduFile, startUtcDatetime, 1)
       incrementNextUlSduPointer(nextSduFile, last_sdu_id)
       print 'INFO: UTC start date requested', startUtcDatetime, 'mssgId set to', last_sdu_id
    if cfg['useEndDatetime']=='1':
       endUtcDatetime = eval(cfg['endUtcDatetime'])
       print 'INFO: UTC end date requested', endUtcDatetime
       endTimeReached = 0
       endTimeWarned = 0
       

while cfg['useEndDatetime'] != '1' or not endTimeReached:
   try:
      # Performance profiling - measure delta start to finish
      # print 'Profiling Debug: about to fetch 500 messages at time ', datetime.datetime.now()

      (status, last_sdu_id, size, sdu_list) = getNextUlSdu(nextSduFile, None, 500)
      #print "Debug: ", status, 'lastsduid', last_sdu_id,'size', size, sdu_list
      if status != 'OK':
         print 'sleep on error'
         time.sleep(5) # problem, wait and try again
         print 'done sleep on error'
      elif size == 0 and last_sdu_id == '':
         time.sleep(1) # queue is empty, attempt to get latest SDUs every 1 second
      elif size == 0:
         print 'rest2m2x.py: assuming downlinkDatagramResponse (or non-uplink mssg), incrementing nextUlSdu'
         incrementNextUlSduPointer(nextSduFile, last_sdu_id)
      else:
         for idx in range(size):
            # print 'Profiling Debug: idx = ', idx , datetime.datetime.now()
            (sdu_id, node_id_hex, rx_timestamp, payload) = getSduInfo(sdu_list, idx) 
            rx_dt = convertToDateTime(rx_timestamp)
            if cfg['useEndDatetime'] == '1' and rx_dt > endUtcDatetime:
               endTimeReached = 1
               if not endTimeWarned:
                  print 'INFO: Stopping due to End Datetime reached.', rx_dt
               endTimeWarned = 1
   
            (match_found, dev_info) = getDeviceInfo(node_id_hex, devices)
   
            if match_found:
                # Call a parser with the payload
                try:
                   no_head_end_enabled = 0
                   m2x_enabled = 0
                   if dev_info['m2x_enabled'] == 1:
                      m2x_enabled = 1
                   thingworx_enabled = 0
                   if dev_info['thingworx_enabled'] == 1:
                      thingworx_enabled = 1
                   headend_loopback_enabled = 0
                   if dev_info['headend_loopback_enabled'] == 1:
                      headend_loopback_enabled = 1
                   plasma_enabled = 0
                   if dev_info['plasma_enabled'] == 1:
                      plasma_enabled = 1
                   # Add all possible head ends here in the future
                   if m2x_enabled == 0 and plasma_enabled == 0 and thingworx_enabled == 0:
                      no_head_end_enabled = 1
                except:
                   pass
   
                # ---------------------------------------------------------------------------------------------------
                # Serial (You Must set M2X stream data type to alphanumeric when creating device in M2X)
                # ---------------------------------------------------------------------------------------------------
                if dev_info['parser'] == 'serial_1':
                   print '\nBegin parsing ULSDU at %s with: serial_1, sdu_id %s \nnodeId %s rx_timestamp %s payload %s'\
                      % (datetime.datetime.now(), sdu_id, node_id_hex, rx_timestamp, payload)
                   if no_head_end_enabled and cfg['warnNoHeadEnd']=='1':
                      print 'INFO: There is no head end configured for this device.'
                   (msgType, data) = parsers.parser_serial_1(payload)
      
                   # Note we do not send the test button alarm to M2x, so we only accept one message type
                   if msgType == 'Serial':
                      allMeasAccepted = 1 # default means M2X accepted all measurements
                      for i in range(len(data)):
                         timestamp = convertToDateTime(rx_timestamp).strftime("%Y-%m-%dT%H:%M:%SZ") # format m2x expects
                         text = hex2text(data[i]['data']) # convert bytes to human readable text
                         print "CONSOLE: ", node_id_hex, data[i]['sensorName'], '(ASCII)=', data[i]['data'],\
                            ' meas_time =', timestamp

                         sendtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                         #Rxlogfile.write(node_id_hex + " " + text + " " + rx_timestamp + " " + sendtime + "\n\n")
                         Rxlogfile = open(logfilename, "a")
                         Rxlogfile.write(node_id_hex + " " + text + " rx_time" + " " + sendtime + "\n\n")
                         Rxlogfile.close()
                         #if headend_loopback_enabled:
                            #print 'INFO: Head End Loopback enabled, sending...'
                            #gaowei
                            #sendAsciiDl2Rest(text, node_id_hex)
                            #sendtime = time.strftime( "%Y-%m-%d %H:%M:%S", time.localtime() )
                            #sendAsciiDl2Rest(text +" "+ rx_timestamp+" "+sendtime, node_id_hex)

                         if m2x_enabled:
                            res = sendStream2M2x(dev_info['m2x_primary_key'], dev_info['m2x_device_id'],\
                                                 data[i]['sensorName'], timestamp, text)
                            if res == '{"status":"accepted"}':
                               print "OK: M2X Stream Updated on ATT Servers", data[i]['sensorName'],\
                                  datetime.datetime.now(),'\n text = ', text, node_id_hex
    
                            else:
                               print "ERROR: M2X Stream Failed to Update on ATT Servers reason: %s" % (res)
                               print data[i]['sensorName'], timestamp, data[i]['data'], text, node_id_hex,\
                                  datetime.datetime.now()
                               # We can't let a misconfigured device block all other UL SDUs
                               # so we drop this SDU and must go back and push it to M2x in the future
                               incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                               allMeasAccepted = 0
      
                      # We only increment next SDU if the current SDU made it to M2X completely
                      # or in the case of certain errors
                      if allMeasAccepted:
                         incrementNextUlSduPointer(nextSduFile, last_sdu_id)
   
                   else:
                      print 'INFO: msgType will not be sent to M2x: ', msgType
                      print 'Data: ', data
                      incrementNextUlSduPointer(nextSduFile, last_sdu_id) # increment if we discard  and don't send to M2X
   
                # ---------------------------------------------------------------------------------------------------
                # Temperature Humidity 4-20mA Omega
                # Note Over the air alarms are not used in this example code, therefore if we receive any
                # alarm messages, they are ignored. Alarms (triggers) may be implemented in M2x
                # ---------------------------------------------------------------------------------------------------
                elif dev_info['parser'] == 'temperature_humidity_1':
                   print '\nBegin parsing ULSDU at %s with: temperature_humidity_1, sdu_id %s \nnodeId %s rx_timestamp %s payload %s'\
                      % (datetime.datetime.now(), sdu_id, node_id_hex, rx_timestamp, payload)
                   if no_head_end_enabled and cfg['warnNoHeadEnd']=='1':
                      print 'INFO: There is no head end configured for this device.'
                   (msgType, data) = parsers.parser_temperature_humidity_1(payload)
                   if msgType == 'SensorData':
                      allMeasAccepted = 1 # default means M2X accepted all measurements
                      if plasma_enabled:
                         ms_data = convertToMultiSensor(data)
                         res = sendData2C2m(dev_info['parser'], dev_info['plasma_api_key'], dev_info['plasma_feed_key'],\
                            ms_data)
                         print 'here3'
   
                      for i in range(len(data)):
                         timestamp = data[i]['timeStamp'].strftime("%Y-%m-%dT%H:%M:%SZ") # format m2x expects
                         print "CONSOLE: ", node_id_hex, data[i]['sensorName'], '=', data[i]['data'],\
                            'meas_time =', timestamp
                         if m2x_enabled:
                            res = sendStream2M2x(dev_info['m2x_primary_key'], dev_info['m2x_device_id'],\
                                                 data[i]['sensorName'], timestamp, data[i]['data'])
                            if res == '{"status":"accepted"}':
                               print "OK: M2X Stream Updated on ATT Servers", data[i]['sensorName'],\
                                  datetime.datetime.now(),'\n', data[i]['data'], node_id_hex
                                  
                            else:
                               print "ERROR: M2X Stream Failed to Update on ATT Servers reason: %s" % (res)
                               print data[i]['sensorName'], timestamp, data[i]['data'], node_id_hex,\
                                  datetime.datetime.now()
                               # We can't let a misconfigured device block all other UL SDUs
                               # so we drop this SDU and must go back and push it to M2x in the future
                               incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                               allMeasAccepted = 0
      
                         if thingworx_enabled:
                            res = sendMqtt2Thingworx(node_id_hex,\
                                                 data[i]['sensorName'], timestamp, data[i]['data'])
                            if res == '{"status":"accepted"}':
                               print "OK: Thingworx Stream Updated on Server", data[i]['sensorName'],\
                                  datetime.datetime.now(), data[i]['data'], node_id_hex
                                  
                            else:
                               print "ERROR: Thingworx Stream Failed to Update on Server reason: %s" % (res)
                               print data[i]['sensorName'], timestamp, data[i]['data'], node_id_hex,\
                                  datetime.datetime.now()
                               # We can't let a misconfigured device block all other UL SDUs
                               # so we drop this SDU and must go back and push it to M2x in the future
                               incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                               allMeasAccepted = 0
      
                      # We only increment next SDU if the current SDU made it to M2X completely
                      if allMeasAccepted:
                         incrementNextUlSduPointer(nextSduFile, last_sdu_id)
      
                   else:
                      print 'INFO: msgType will not be sent to M2x: ', msgType
                      print 'INFO: Data= ',  data
                      incrementNextUlSduPointer(nextSduFile, last_sdu_id) # increment if we don't send to M2X
   
                # ---------------------------------------------------------------------------------------------------
                # INTRUSION DETECTOR1 (Normally Closed Switch) & PROCESSOR TEMPERATURE
                # Note we re-map over the air alarm messages to sensor data, to allow triggers in M2X
                # to do the alarming
                # ---------------------------------------------------------------------------------------------------
   #cleanup when plasma intrusion detection ready
                elif dev_info['parser'] == 'intrusion_detector_1':
                   print '\nBegin parsing ULSDU at %s with: intrusion_detector_1, sdu_id %s \nnodeId %s rx_timestamp %s payload %s'\
                      % (datetime.datetime.now(), sdu_id, node_id_hex, rx_timestamp, payload)
                   if no_head_end_enabled and cfg['warnNoHeadEnd']=='1':
                      print 'INFO: There is no head end configured for this device.'
                   (msgType, data) = parsers.parser_intrusion_detector_1(payload)
      
                   # For M2X testing/demo only, we convert alarm into data stream time series value. We
                   # do this so M2X will trigger the alarm.
                   # Ignore the "interrupt" pushbutton, by not parsing those alarms
                   validAlarmType = 0
                   if msgType == 'Alarm' and data['alarmCnt'] != '01':
                      print 'ERROR: Greater than 1 alarm per message not supported. Not sent to M2X!!! Data: ',  data
                      print 'Try increasing hysteresis so only 1 alarm is sent per SDU.'
                      incrementNextUlSduPointer(nextSduFile) # increment if we don't send to M2X
                   elif msgType == 'Alarm' and data['alarmType'] == 'TestButton':
                      print 'INFO: TestButton Alarm will not be sent to M2X. Data: ',  data
                      incrementNextUlSduPointer(nextSduFile, last_sdu_id) # increment if we don't send to M2X
                   elif msgType == 'Alarm' and data['alarmType'] == 'AppIntf1'\
                      and data['digAlarmThresh']=='Active_High':
                      validAlarmType = 1
                      if data['alarmState']=='Set':
                         alarm_data = [{'sensorName':'intrusion', 'timeStamp':data['timeStamp'], 'data':1}]
                      elif data['alarmState']=='Cleared':
                         alarm_data = [{'sensorName':'intrusion', 'timeStamp':data['timeStamp'], 'data':0}]
                      data = alarm_data # overwrite data with only the stuff we need to send to m2x...
                   elif msgType == 'SensorData':
                      pass # SensorData is already in the correct format for sendStream2M2x
                   else:
                      print 'INFO: msgType will not be sent to M2x: ', msgType
                      print 'INFO: Data= ',  data
                      incrementNextUlSduPointer(nextSduFile, last_sdu_id) # increment if we don't send to M2X
   
                   if msgType == 'SensorData' or validAlarmType == 1:
                      allMeasAccepted = 1 # default means M2X accepted all measurements
                      if plasma_enabled:
                         ms_data = convertToMultiSensor(data)
                         res = sendData2C2m(dev_info['parser'], dev_info['plasma_api_key'], dev_info['plasma_feed_key'],\
                            ms_data)
   
                      for i in range(len(data)):
                         timestamp = data[i]['timeStamp'].strftime("%Y-%m-%dT%H:%M:%SZ") # format m2x expects
                         print "CONSOLE: ", node_id_hex, data[i]['sensorName'], '=', data[i]['data'],\
                            'meas_time =', timestamp
                         if m2x_enabled:
                            res = sendStream2M2x(dev_info['m2x_primary_key'], dev_info['m2x_device_id'],\
                                                 data[i]['sensorName'], timestamp, data[i]['data'])
                            if res == '{"status":"accepted"}':
                               print "OK: M2X Stream Updated on ATT Servers", data[i]['sensorName'],\
                                  datetime.datetime.now(), node_id_hex
                            else:
                               print "ERROR: M2X Stream Failed to Update on ATT Servers reason: %s" % (res)
                               print data[i]['sensorName'], timestamp, data[i]['data'], node_id_hex,\
                                  datetime.datetime.now()
                               # We can't let a misconfigured device block all other UL SDUs
                               # so we drop this SDU and must go back and push it to M2x in the future
                               incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                               allMeasAccepted = 0
      
                      # We only increment next SDU if the current SDU made it to M2X completely
                      if allMeasAccepted:
                         incrementNextUlSduPointer(nextSduFile, last_sdu_id)
      
                # ---------------------------------------------------------------------------------------------------
                # INTRUSION DETECTOR2 (Normally Open Switch) & PROCESSOR TEMPERATURE
                # Note we re-map over the air alarm messages to sensor data, to allow triggers in M2X
                # to do the alarming
                # Note we invert intrusion data, too (flipBit)
                # ---------------------------------------------------------------------------------------------------
   #cleanup when plasma intrusion_detector_2 ready
                elif dev_info['parser'] == 'intrusion_detector_2' and m2x_enabled:
                   print '\nBegin parsing ULSDU at %s with: intrusion_detector_2, sdu_id %s \nnodeId %s rx_timestamp %s payload %s'\
                      % (datetime.datetime.now(), sdu_id, node_id_hex, rx_timestamp, payload)
                   if no_head_end_enabled and cfg['warnNoHeadEnd']=='1':
                      print 'INFO: There is no head end configured for this device.'
                   (msgType, data) = parsers.parser_intrusion_detector_2(payload)
      
                   # On the way into M2X we convert sign of intrusion detector from active low to active high for
                   # graphing (so 1=intrusion)
                   if msgType == 'SensorData':
                      for i in range(len(data)):
                         if data[i]['sensorName']=='intrusion':
                            data[i]['data'] = flipBit(data[i]['data'])
      
                   # For M2X testing/demo only, we convert alarm into data stream time series value. We
                   # do this so M2X will trigger the alarm.
                   elif msgType == 'Alarm' and data['alarmCnt'] != '01':
                      print 'ERROR: Greater than 1 alarm per message not supported. Not sent to M2X!!! Data: ',  data
                      print 'Try increasing hysteresis so only 1 alarm is sent per SDU.'
   
                   # Ignore the "interrupt" pushbutton, by not parsing exception alarms
                   elif msgType == 'Alarm' and data['alarmType'] == 'TestButton':
                      validAlarmType = 0
                      print 'INFO: Test PushButton Alarm will not be sent to M2X. Data: ',  data
                      incrementNextUlSduPointer(nextSduFile, last_sdu_id) # increment if we don't send to M2X
   
                   elif msgType == 'Alarm' and data['alarmType'] == 'AppIntf2'\
                      and data['digAlarmThresh']=='Active_Low':
                      validAlarmType = 1
                      # note inversion of data in two places below
                      if data['alarmState']=='Set':
                         alarm_data = [{'sensorName':'intrusion', 'timeStamp':data['timeStamp'], 'data':1}]
                      elif data['alarmState']=='Cleared':
                         alarm_data = [{'sensorName':'intrusion', 'timeStamp':data['timeStamp'], 'data':0}]
                      data = alarm_data # overwrite data with only the stuff we need to send to m2x. Regret: has caused me much confusion
      
                   else:
                      print 'INFO: msgType will not be sent to M2x: ', msgType
                      print 'INFO: Data= ',  data
                      validAlarmType = 0
                      incrementNextUlSduPointer(nextSduFile, last_sdu_id) # increment if we don't send to M2X
   
                   if msgType == 'SensorData' or validAlarmType == 1:
                      allMeasAccepted = 1 # default means M2X accepted all measurements
                      for i in range(len(data)):
                         timestamp = data[i]['timeStamp'].strftime("%Y-%m-%dT%H:%M:%SZ") # format m2x expects
                         print "CONSOLE: ", node_id_hex, data[i]['sensorName'], '=', data[i]['data'],\
                            'meas_time =', timestamp
                         res = sendStream2M2x(dev_info['m2x_primary_key'], dev_info['m2x_device_id'],\
                                                 data[i]['sensorName'], timestamp, data[i]['data'])
                         if res == '{"status":"accepted"}':
                            print "OK: M2X Stream Updated on ATT Servers", data[i]['sensorName'],datetime.datetime.now(),\
                               node_id_hex
                         else:
                            print "ERROR: M2X Stream Failed to Update on ATT Servers reason: %s" % (res)
                            print data[i]['sensorName'], timestamp, data[i]['data'], node_id_hex,\
                               datetime.datetime.now()
                            # We can't let a misconfigured device block all other UL SDUs
                            # so we drop this SDU and must go back and push it to M2x in the future
                            incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                            allMeasAccepted = 0
      
                      # We only increment next SDU if the current SDU made it to M2X completely
                      if allMeasAccepted:
                         incrementNextUlSduPointer(nextSduFile, last_sdu_id)
      
                # ---------------------------------------------------------------------------------------------------
                # GPS LAT/LNG & DOWNLINK RSSI
                # Notes:
                # 1) This is not a stream in M2x. We update the device location (waypoints)
                # 2) We use the 'elevation' attribute to report DL RSSI in dBm (-132dB is edge of cell)
                # 3) We implement decimation in what is reported to M2X to avoid rate limiting, we measure every 4.5
                #    seconds, and report one location every minute.
                # 4) Discard incorrect GPS values (including (0,0) means no fix)
                # ---------------------------------------------------------------------------------------------------
                elif dev_info['parser'] == 'gps_2':
                   print '\nBegin parsing ULSDU at %s with: gps_2, sdu_id %s \nnodeId %s payload %s'\
                      % (datetime.datetime.now(), sdu_id, node_id_hex, payload)
                   if no_head_end_enabled and cfg['warnNoHeadEnd']=='1':
                      print 'INFO: There is no head end configured for this device.'
                   (msgType, data) = parsers.parser_gps_2(payload)
   
                   # Rare Case of deprecated RACM alarm message (opcode 0x01)
                   if msgType == 'ERROR':
                      print "ERROR: GPS dropped unexpected length. This could be a RACM alarm message ", sdu_id, rx_timestamp, payload
                      incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                      allMeasAccepted = 0
   
                   elif msgType == 'RfdtData':
                      allMeasAccepted = 1 # default means M2X accepted all measurements
                      # create stream data out of the GPS data
                      # I'm just tricking the convertToMultiSensor function into thinking it is getting stream data...
                      ts = convertToDateTime(rx_timestamp)
                      gps_stream = [{'timeStamp':ts,'sensorName':'lat','data':data[0]['lat']},\
                                    {'timeStamp':ts,'sensorName':'lng','data':data[0]['lng']},\
                                    {'timeStamp':ts,'sensorName':'rssi','data':data[0]['rssi']}]
                      ms_data = convertToMultiSensor(gps_stream)
   
                      if plasma_enabled:
                         # LEW: sendData2C2m doesn't send (0,0) as of 4/14/2016
                         #gps_ok = isGpsValid(data[i]['lat'], data[i]['lng'])
                         #if gps_ok:
                         if 1:
                            res = sendData2C2m(dev_info['parser'], dev_info['plasma_api_key'],\
                               dev_info['plasma_feed_key'], ms_data)
   
                      # Expect one location data but this is generalized to list of N
                      for i in range(len(data)):
                         ts = convertToDateTime(rx_timestamp)
                         timestamp = ts.strftime("%Y-%m-%dT%H:%M:%SZ") # format m2x expects
                         gps_ok = isGpsValid(data[i]['lat'], data[i]['lng'])
                         nodeIdHex = node_id_hex # Clean up this needless renaming 4/23/2016
                         if cfg['enableFindJoinedAp']=='1':
                            (status, joinedAp) = findJoinedAp(nodeIdHex, ts)
                         else:
                            joinedAp = ''

                         print "CONSOLE: ", node_id_hex, data[i]['sensorName'], 'lat/lng =', data[i]['lat'],\
                            data[i]['lng'],'RSSI =', data[i]['rssi'], 'dBm', 'meas_time =', str(ts)
                            
                         if cfg['writeGps2Csv']=='1':
                            writeGps2Csv(node_id_hex, data[i]['lat'], data[i]['lng'], data[i]['rssi'], str(ts),joinedAp, getUlpFrame(ts))
                               
                         if gps_ok:
                            should_decimate = shouldDecimate(nodeIdHex, ts)
                            if not should_decimate and m2x_enabled:
                               res = sendLocRssi2M2x(dev_info['m2x_primary_key'], dev_info['m2x_device_id'],\
                                                     timestamp, data[i]['lat'], data[i]['lng'], data[i]['rssi'])
                               if res == '{"status":"accepted"}':
                                  print "OK: M2X Stream Updated on ATT Servers", data[i]['sensorName'],datetime.datetime.now(),\
                                     '\n', data[i]['lat'], data[i]['lng'], node_id_hex,\
                                     data[i]['rssi'], 'dBm RSSI', timestamp
                               else:
                                  print "ERROR: M2X Stream Failed to Update on ATT Servers reason: %s" % (res)
                                  print data[i]['sensorName'], timestamp, data[i], node_id_hex,\
                                     datetime.datetime.now()
                                  # We can't let a misconfigured device block all other UL SDUs
                                  # so we drop this SDU and must go back and push it to M2x in the future
                                  incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                                  allMeasAccepted = 0
   # should print "Valid GPS/Rssi" entry above here for completeness
   #improve error checking here
                               #if res == '{"status":"accepted"}':
                               #   print "OK: Plasma Stream Updated on Servers", data[i]['sensorName'],datetime.datetime.now(),\
                               #      '\n', data[i]['lat'], data[i]['lng'], node_id_hex,\
                               #      data[i]['rssi'], 'dBm RSSI', timestamp
                               #else:
                               #   print "ERROR: Plasma Stream Failed to Update on Servers reason: %s" % (res)
                               #   print data[i]['sensorName'], timestamp, data[i], node_id_hex,\
                               #      datetime.datetime.now()
                               #   # We can't let a misconfigured device block all other UL SDUs
                               #   # so we drop this SDU and must go back and push it to M2x in the future
                               #   incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                               #   allMeasAccepted = 0
                            else:
                               if cfg['warnGpsDecimation']=='1':
                                  print "INFO: GPS dropped (decimated) to reduce rate, not sent to Head End Servers",\
                                     data[i]['sensorName'],datetime.datetime.now(),\
                                     node_id_hex, data[i]['lat'], data[i]['lng'], data[i]['rssi'], timestamp
                               incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                               allMeasAccepted = 0
                         else:
                            if cfg['warnGpsDecimation']=='1':
                               print "INFO: GPS dropped due to invalid location , not sent to ATT Servers",\
                                  data[i]['sensorName'],datetime.datetime.now(),\
                                  node_id_hex, data[i]['lat'], data[i]['lng'], data[i]['rssi'], timestamp
                            incrementNextUlSduPointer(nextSduFile, last_sdu_id)
                            allMeasAccepted = 0
      
                      # We only increment next SDU if the current SDU made it to M2X completely
                      # or in the case of certain errors
                      if allMeasAccepted:
                         incrementNextUlSduPointer(nextSduFile, last_sdu_id)
      
                   else:
                      print 'INFO: msgType will not be send to M2x: ', msgType
                      print 'INFO: Data= ',  data
                      incrementNextUlSduPointer(nextSduFile, last_sdu_id) # increment if we don't send to M2X
   
                # ---------------------------------------------------------------------------------------------------
                # Unknown Parser
                # ---------------------------------------------------------------------------------------------------
                else:
                   print "ERROR: Can't find specified parser: %s for SDU_ID:%s nodeId=%s,rx_timestamp=%s,payload=%s"\
                      % (dev_info['parser'], sdu_id, node_id_hex, rx_timestamp, payload)
      
            # else not match_found
            else:
               if cfg['warnNoDevice']=='1':
                  print "\nINFO: No device in Devices.json for sdu_id, node_id, rx_timestamp, payload: ",\
                                         sdu_id, node_id_hex, rx_timestamp, payload
               incrementNextUlSduPointer(nextSduFile, last_sdu_id) # increment if we don't send to M2X

      # debug for performance profiling - how long it took to process 500 messages from Intellect
      # indent level of while not end time reached, try
      # print 'Profiling Debug: Done processing ', size, 'messages at time ', datetime.datetime.now()

   except KeyboardInterrupt:
      sys.exit()