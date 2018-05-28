#!/bin/env python
# m2xCallback.py Lew Cohen 11/6/2015
# For a trigger, there are currently 2 behaviors:
# 1) if it is a serial device, loop back text
# 2) for all other devices, send alarm emails if enabled
# The triggers are JSON
# Must receive a POST from M2X

from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
import sys
import traceback
import json
import datetime
from sendAsciiDl2Rest import sendAsciiDl2Rest
from getDeviceInfo import getDeviceInfo
from sendEmails import sendEmails

with open('Devices.json','r') as infile:
    devices = json.load(infile)
    infile.close()

# -----------------------------------------------------------
# Create a server to receive POST from M2X
# and send something on Downlink to device
# -----------------------------------------------------------
ADDR = "172.16.50.11" # local address of VM on OpenStack
# This port must agree with the port in the callback URL configured in M2X
# It was arbitrarily selected
PORT = 8001

class RequestHandler(BaseHTTPRequestHandler):        
    def do_POST(self):
        try:
           length = int(self.headers['Content-length'])
           m2x_post_contents = self.rfile.read(length)
           self.send_response(200, "OK")
           self.end_headers()
           print 'm2xCallback.py: received a POST at time ', datetime.datetime.now(), length
           payload = json.loads(m2x_post_contents)
           print payload
           node_id_hex = payload['device']['serial']
           (match_found, dev_info) = getDeviceInfo(node_id_hex), devices)
           # FUTURE IMPROVEMENT: add supported alarm types to dev_info for each device
           if match_found:
              try:
                 # The trigger names below match what you MUST name them in m2x
                 if payload['trigger'] == 'serial_trig':
                    if payload['custom_data'] != None:
                       data_string = payload['custom_data'] + payload['values']['serial']['value']
                    else:
                       data_string = payload['values']['serial']['value']

                    # Robustness, try 3 times, if needed
                    for i in range (3):
                       retval = sendAsciiDl2Rest(data_string, node_id_hex)
                       if retval == 'OK':
                          break
                       else:
                          print 'ERROR: sendAsciiDl2Rest cannot send to REST retval =', retval, i
                    
                 elif payload['trigger'] == 'intrusion_trig':
                    subject = 'Alarm: 0x' + node_id_hex
                    if payload['values']['intrusion']['value'] == 1:
                      alarm_cond = 'Set'
                    elif payload['values']['intrusion']['value'] == 0:
                      alarm_cond = 'Cleared'
                    message_body = 'Sensor:%s Alarm:%s Timestamp:%s' %(payload['device']['name'], alarm_cond, payload['timestamp'])
                    sendEmails(dev_info['alarm_email_list'], subject, message_body)
              except:
                 traceback.print_exc()
                 print 'm2xCallback.py: Exception(1): ', sys.exc_info()[0]
           else:
              print 'm2xCallback.py: no match found for node ID 0x', node_id_hex, payload

        except:
           traceback.print_exc()
           print 'lew 2 m2xCallback.py: Exception(2): ', sys.exc_info()[0]

# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
httpd = HTTPServer((ADDR, PORT), RequestHandler)
httpd.serve_forever()
