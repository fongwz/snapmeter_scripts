#!bin/env python
# getNextUlSdu.py Lew Cohen 10/16/2015
# Pull one UL SDU from REST interface
# Note as of this writing m2x only accepts one write per second per device
# which influences why we only pull 1 SDU
# We also need to be concerned to not duplicate sdus into the m2x database
# This script uses nextUlSdu.cfg to keep track of next messageId 
# 2/15/2016 The terminology has changed from SDUs to messages, may not be fully reflected in
# variable names
# Note: we believe this default messageId corresponds to a config response from
# racm 0x304b1 (197809) sent 2-29-2016 21:43:31 GMT on ingenudemo REST
# messageId = 1e095a80-df2d-11e5-8fe9-0380bd1c3ac8 

import sys
import httplib
import json
import time, datetime, calendar
from getLoginInfo import getLoginInfo
from xml.dom import minidom
from xml.parsers.expat import ExpatError

import ssl
from functools import wraps
def sslwrap(func):
      @wraps(func)
      def bar(*args, **kw):
            kw['ssl_version'] = ssl.PROTOCOL_TLSv1
            return func(*args, **kw)
      return bar

ssl.wrap_socket = sslwrap(ssl.wrap_socket)


#------------------------------------------------------------------------------
# CONSTANTS and CONFIG:
#------------------------------------------------------------------------------
max_results = 500 # normally should be 1000 but for m2x limitation, this simplifies

# Get REST Login Info from a file
(host, username, password) = getLoginInfo("login_info.json")

# Note you can append to this url:
# messageId: this will pull only mssgs AFTER the appended messageID (last one you received)
# count: "?count=10" will return 10 mssgs. Max/Default = 500
data_url = "/data/v1/receive"
token_url = "/config/v1/session"


#------------------------------------------------------------------------------
# Get a Login Token for the REST Interface
#------------------------------------------------------------------------------
def getLoginToken (host, token_url, username, password):
      print ('lets get a login token :)')
      print 'login deets: ', username, password
      try:
            rst_conn = httplib.HTTPSConnection(host)
            rst_headers = {"Username": username, "Password": password, "Accept": "application/json"}
            rst_conn.request("POST", token_url, "", rst_headers)
            response = rst_conn.getresponse()
            result = response.read()
            print 'yay i got mail ', result
            login_token = json.loads(result)["token"]
            #print result
            
            return login_token

      except Exception as e:
            print 'login tokens are hard to get :( ', e
            print "wait 10 sec and continue"
            time.sleep(10)
            return -1

      finally:
            print 'finally closing first connection'
            rst_conn.close()



#------------------------------------------------------------------------------
# Pull The Next SDU From REST Interface 
#------------------------------------------------------------------------------
def pullUlSdu (start_sdu_id, count):

   login_token = getLoginToken(host, token_url, username, password)
   response = 'blank'
   if login_token == -1:
         return("i couldnt log in :'(", 'stupid', 'code', 'design')
   print 'new request connection!'
   try:
      rest_conn = httplib.HTTPSConnection(host,timeout=60) # external appliance or hosted network use HTTPSConn
      sdus = [] # init
      # Note the SDUs get appended to global list of lists sdus in parseResults
      size = max_results # initialize so while loop runs at least one time
      url  = data_url
      if start_sdu_id != '':
            url = url + '/' + start_sdu_id
      url = url.replace('\n','').replace('\r','') # make sure no carriage return/line feed
      url = url + '?count=' + str(count)
      data_rest_headers = {"Authorization": login_token, "Accept":"application/xml"}

      rest_conn.request("GET", url, "", data_rest_headers)
      response = rest_conn.getresponse() # sometimes fails with BadStatusLine or CannotSendRequest
      result = response.read()
      dom = minidom.parseString(result)
      (last_sdu_id, sdus) = parseResults(dom, sdus)
      size = len(sdus)
      return ('OK', last_sdu_id, size, sdus)
   except Exception as e:
      return ('ERROR', str(sys.exc_info()[0]),e,'')
   finally:
      print 'closing the connection yall'
      rest_conn.close()

#------------------------------------------------------------------------------
# Parses the REST ULSDU Query Results (XML)
#------------------------------------------------------------------------------
def parseResults(dom, sdus):
   ul_elements = dom.getElementsByTagName("uplink")
   last_sdu_id = ''
   for ul in ul_elements:
      sdu_id = ul.getElementsByTagName("messageId")[0].childNodes[0].nodeValue
      messageType = ul.getElementsByTagName("messageType")[0].childNodes[0].nodeValue # future use
      if messageType == 'DatagramUplinkEvent':
         datagramContents = ul.getElementsByTagName("datagramUplinkEvent")[0]
         raw_hex = datagramContents.getElementsByTagName("payload")[0].childNodes[0].nodeValue
         node_id = datagramContents.getElementsByTagName("nodeId")[0].childNodes[0].nodeValue
         timestamp = datagramContents.getElementsByTagName("timestamp")[0].childNodes[0].nodeValue
         sdus.append([sdu_id, raw_hex, node_id, timestamp])
      elif messageType == 'DatagramDownlinkResponse':
         datagramContents = ul.getElementsByTagName("datagramDownlinkResponse")[0]
         node_id = datagramContents.getElementsByTagName("nodeId")[0].childNodes[0].nodeValue
         timestamp = datagramContents.getElementsByTagName("timestamp")[0].childNodes[0].nodeValue
         status = datagramContents.getElementsByTagName("status")[0].childNodes[0].nodeValue
         tag = datagramContents.getElementsByTagName("tag")[0].childNodes[0].nodeValue
         print 'getNextUlSdu.py: Downlink Status (no further action) ', node_id, timestamp, status,\
            'tag = ', tag, 'messageId = ', sdu_id
      else:
         print 'getNextUlSdu.py: No action taken on messageType: ', messageType

      last_sdu_id = sdu_id # increment to get next message from REST
   return (last_sdu_id, sdus)

#------------------------------------------------------------------------------
# Gets the messageId of the previous message from a file
# NOTE: You should store the previousMessageId in non-volatile (ex. disk) memory
# so that when your program is restarted, you don't fetch lots of old data
#------------------------------------------------------------------------------
def getNextUlSduPointer(filename):
   try:
      with open(filename,'r') as infile:
         mssg_id_dict = json.load(infile)
         infile.close()
         #The REST interface will return all messages AFTER this messageId, if you put it in query
         start_sdu_id = mssg_id_dict["lastFetchedMssgId"] # (naming) this is actually the last one you received
         return start_sdu_id
   except:
      # If you get this error, you should create an empty file (ex. nextUlSdu.cfg)
      print "ERROR: can't open file: %s to read next Ul SDU pointer" % (filename)
      print sys.exc_info()[0]
   
#------------------------------------------------------------------------------
# Writes the last message ID to a file, so next query will get all SDUs afterward.
# This function gets imported by other modules
#------------------------------------------------------------------------------
def incrementNextUlSduPointer(filename, last_sdu_id, lastFetchedMssgUtcDatetime=None):
   try:
      with open(filename,'w') as outfile:
         mssg_id_dict = {"lastFetchedMssgId":last_sdu_id, "lastFetchedMssgUtcDatetime":lastFetchedMssgUtcDatetime}
         json.dump(mssg_id_dict, outfile)
         outfile.close()
   except:
      print "ERROR: can't open file: %s to write next Ul SDU pointer" % (filename)
      print sys.exc_info()[0]

#------------------------------------------------------------------------------
# Helper Function for pulling data, given a Start Date
# Convert a UTC start datetime to a UUID for querying Intellect REST Interface
# The UUID contains the datetime, and a clock ID and MAC. The safe way to get 
# the clock ID and MAC is from the Intellect server, by pulling the first SDU
# in the database, just to get this information in the messageId.
# LEW this function returns SDUs 5-10 seconds before the requested start date need debug
# for now it is not that big a deal if it returns one extra (early) SDU
#------------------------------------------------------------------------------
def getMssgIdFromStartDate(startUtcDatetime):
   (status, last_sdu_id, size, sdus) = pullUlSdu('',1) # pulls oldest SDU
   uuid_components = last_sdu_id.split('-')
   clock_id = str(uuid_components[3])
   mac_address = str(uuid_components[4])
   ticks_to_epoch = 122192928000000000 # 100ns ticks from 15 Oct 1582 to 1 Jan 1970
   ticks_epoch_to_start_utc = calendar.timegm(startUtcDatetime.timetuple())
   # mktime is in local time. You need to fix timezone before calling
   local_dt = datetime.datetime.fromtimestamp(ticks_epoch_to_start_utc)
   ticks_epoch_to_start_loc = time.mktime(local_dt.timetuple())
   # mktime returns time in seconds, need to multiply by 1e7 to get 100ns
   hns_epoch_to_start_loc = ticks_epoch_to_start_loc * 1000 * 1000 * 10 # hundred ns ticks
   total_ticks = ticks_to_epoch + hns_epoch_to_start_loc
   total_ticks_hex = hex(int(total_ticks))
   total_ticks_hex = str(total_ticks_hex).replace('x','x1') # this is to prepend UUID type 1 to 60 bit time
   last_sdu_id = total_ticks_hex[10:18] + '-'\
               + total_ticks_hex[6:10] + '-'\
               + total_ticks_hex[2:6] + '-'\
               + clock_id + '-'\
               + mac_address
   return last_sdu_id


def getNextUlSdu(filename, startUtcDatetime = None, count=500):
   start_sdu_id = getNextUlSduPointer(filename)

   # Override the UUID in the file, if a start date was supplied
   if startUtcDatetime:
      start_sdu_id = getMssgIdFromStartDate(startUtcDatetime)
      print 'Info(startupConfig.json): start time override with start_sdu_id', start_sdu_id
      
   (status, last_sdu_id, size, sdus) = pullUlSdu(start_sdu_id, count)
   if status == 'OK':
      return ('OK', last_sdu_id, size, sdus)
   elif status == 'ERROR':
      return ('ERROR', '','','') # dummy so same fields get returned
   else:
      return ('unknown error lmao', '','','') # dummy so same fields get returned
      pass

if __name__ == '__main__':
   #(status, last_sdu_id, size, sdus) = getNextUlSdu('nextUlSdu.cfg', datetime.datetime(2016, 04, 17, 16, 00, 00))
   (status, last_sdu_id, size, sdus) = getNextUlSdu('lastFetchedMssgId.json')
   print "size = ", size 
   print "sdus  = ", sdus 
   print "last_sdu_id = ", last_sdu_id
   incrementNextUlSduPointer('lastFetchedMssgId.json', last_sdu_id)
