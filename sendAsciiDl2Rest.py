#!/bin/env python
# sendAsciiDl2Rest.py Lew Cohen 11/6/2015
# Send an ASCII text payload to a RACM configured for serial data

import sys
import time
import httplib
import uuid
from getLoginInfo import getLoginInfo
from xml.dom import minidom

# Get REST Login Info from a file
(host, username, password) = getLoginInfo("login_info.json")

rest_headers = {"Username": username, 
		"Password": password,
                "Content-Type": "application/xml",
                "Accept": "application/xml"}

#------------------------------------------------------------------------------
# GET A LOGIN TOKEN FOR REST INTERFACE
#------------------------------------------------------------------------------
#def getLoginToken(rest_conn):
#   rest_conn.request("POST", login_url, login_body, rest_headers)
#   response = rest_conn.getresponse()
#   result = response.read()
#   print result
#   dom = minidom.parseString(result)
#   login_token = dom.getElementsByTagName("token")[0].childNodes[0].nodeValue
#   #print "Login Token: ", login_token
#   return login_token

#------------------------------------------------------------------------------
# CREATE BODY OF XML FOR REST, GIVEN TEXT STRING INPUT
#------------------------------------------------------------------------------
def createXmlBody(text_str, node_id_hex):
   #node_id_dec = str(int(node_id_hex, 16))
   payload_len = hex(len(text_str)+1)[2:].zfill(4) # zero pad 2 bytes hex, +1 is for line feed we add
   payload_len = payload_len[2:] + payload_len[0:2] # big to little endian
   asc_vals = [ord(c) for c in text_str] # decimal ascii values per character
   hex_vals = [hex(c)[2:].zfill(2) for c in asc_vals] # convert each ascii to hex (no 0x)
   # not sure the following line is required
   #hex_vals = [val + ' ' for val in hex_vals] # insert a space between each value
   data = ''.join(val for val in hex_vals) # convert list to string
   # note a line feed is needed by chrome app to display a line
   payload = '07' + payload_len + data + '0a' # opcode (1B), len (2B), data, line feed
   dl_tag = str(uuid.uuid4())
   body =\
      '<downlink xmlns="http://www.ingenu.com/data/v1/schema"><datagramDownlinkRequest><tag>' +\
        dl_tag + '</tag><nodeId>' +\
        node_id_hex + '</nodeId><payload>' +\
        payload + '</payload></datagramDownlinkRequest></downlink>'

   return body

#------------------------------------------------------------------------------
# MAIN
#------------------------------------------------------------------------------
rest_conn = httplib.HTTPSConnection(host) # external appliance or hosted network use HTTPS
#login_token = getLoginToken(rest_conn)

dl_sdu_url = "/data/v1/send"

# text_str is a string, node_id_hex is in form '0x32abc'
def sendAsciiDl2Rest(text_str, node_id_hex):
   #print 'dl_sdu_url = ', dl_sdu_url
   #print 'rest_headers = ', rest_headers
   #print 'text = ', text_str
   xml_body = createXmlBody(text_str, node_id_hex)
   #print 'xml_body = ', xml_body

   try:
      rest_conn.request("POST", dl_sdu_url, xml_body, rest_headers)
      response = rest_conn.getresponse() # this is the line that fails with 'BadStatusLine'
      result = response.read()
      print 'INFO: sendSerialText2Rest ', node_id_hex, text_str
      retval = 'OK'
   except:
      print 'ERROR: sendSerialText2Rest exception= ', sys.exc_info()[0]
      rest_conn.close() # helps with BadStatusLine, CannotSendRequest
      retval = 'ERROR'
  
   rest_conn.close() # This is for robustness. I had httplib "CannotSendRequest"
   return retval

if __name__ == '__main__':
   sendAsciiDl2Rest('aabbcc', '0x724ff')
