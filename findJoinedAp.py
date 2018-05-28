#!/bin/env python
# findJoinedAp.py finds the last AP a node was joined to, before a given gmt_datetime
# It takes a csv file, exported from Intellect to associate node MAC ID with Ingenu Device Id

import sys
import re
import httplib
import json
import datetime
from getLoginInfo import getLoginInfo

#------------------------------------------------------------------------------
# CONSTANTS and CONFIG:
#------------------------------------------------------------------------------
max_results = 1 # normally should be 1000 but for m2x limitation, this simplifies


# Get REST Login Info from a file
(host, username, password) = getLoginInfo("login_info.json")
rest_headers = {"Username": username, "Password": password, "Accept":"application/json"}

#------------------------------------------------------------------------------
# Pull The Join History From Intellect
#------------------------------------------------------------------------------
def makeDeviceIdTable(device_id_file):
   device_id_table = []
   for line in device_id_file:
      line = line.split(',')
      # Don't include the header line
      if line[0] != 'Id':
         device_id = re.sub('"','', line[0])
         node_id_hex = re.sub('"','', line[1])
         device_id_table.append({'node_id_hex': node_id_hex, 'device_id': device_id})
   return(device_id_table)
   
def getDeviceId(node_id_hex):
   match = next((d for d in device_id_table if int(d['node_id_hex'], 16) == int(node_id_hex, 16)), None)
   return match['device_id']

def findJoinedAp(node_id_hex, gmt_datetime):
   try:
      (status, join_info) = pullJoinInfo(node_id_hex)
   except:
      print "LEW", pullJoinInfo(node_id_hex)

   if status == 'OK':
      # Assumption: list is ordered oldest to newest join AP
      last_join_dt = ''
      last_join_ap = ''
      for d in join_info:
        if d['joinDateTimeGmt'] < gmt_datetime:
           last_join_dt = d['joinDateTimeGmt']
           last_join_ap = d['apMacAddr']
      if last_join_dt != '':
         return ('OK', last_join_ap)
      else:
         print 'WARNING: No join history for: ', node_id_hex, gmt_datetime
         return ('ERROR', '')
   else:
      print "ERROR: can't findJoinedAp"
      return ('ERROR', '')

def pullJoinInfo (node_id_hex):
   device_id = getDeviceId(node_id_hex)
   join_url = "/config/v1/device/"+device_id+"/join/day/30"
   # Note the SDUs get appended to global list of lists sdus in parseResults
   size = max_results # initialize so while loop runs at least one time
   url  = join_url
   url = url.replace('\n','').replace('\r','') # make sure no carriage return/line feed
   try:
      #print url
      rest_conn.request("GET", url, "", rest_headers)
      response = rest_conn.getresponse() # sometimes fails with BadStatusLine or CannotSendRequest
      result = response.read()
      d = json.loads(result)
      dat = d['data']
      join_info = []
      for i in range(len(dat)):
         epoch_ms = int(dat[i]['joinTime'])
         epoch_sec = int(epoch_ms/1000)
         join_dt = datetime.datetime.utcfromtimestamp(epoch_sec)
         join_info.append({'nodeIdHex': dat[i]['nodeIdHex'], 'joinDateTimeGmt': join_dt, 'apMacAddr': dat[i]['apId']})
      return ('OK', join_info)
   except:
      try:
         print 'ERROR(pullJoinInfo): ', sys.exc_info()[:2]
         print 'url ', url, 'rest_headers ', rest_headers
         print 'response= ', response # 'This method may not be used.'
         print 'result = ', result
         print 'dom = ', dom
      except:
	 pass
      rest_conn.close() # This line helps with BadStatusLine error recovery
      # added 2 dummy return values at end to match success case
      return ('ERROR', str(sys.exc_info()[0]),'','')

#------------------------------------------------------------------------------
# MAIN
#------------------------------------------------------------------------------
rest_conn = httplib.HTTPSConnection(host) # external appliance or hosted network use HTTPSConn
print "rest_conn, host = ", rest_conn, host
# LEW should make this an argument or put the filename in a config file
#device_id_file = open('devices_04_19_2016_23_09_16.csv','r')
device_id_file = open('device_id_vs_node_id_07-07-16.csv','r')
device_id_table = makeDeviceIdTable(device_id_file)

if __name__ == '__main__':
   findJoinedAp('0x569cf', datetime.datetime.now()+datetime.timedelta(hours=7))
   findJoinedAp('0x56a32', datetime.datetime.now()+datetime.timedelta(hours=7))
