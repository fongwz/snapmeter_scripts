# createDevices.py creates a json file with devices for use in AT&T M2X system

import json

# Create a dictionary for each device, and add it to the list below. Include the phone number
# to text when an alarm is received, if enabled
# The parser name gets looked up in rest2m2x.py. If it is new, you need to add it
# in rest2m2x.py as well.
# NOTE: to send a text to a cellphone, use this as the email address: Ten_digit_number@X,
# X = vtext.com (verizon), text.att.net (att), tmomail.net (tmobile), messaging.sprintpcs.com (sprint)
# ex. 'alarm_email_lest':['8585551212@text.att.net']



devices = [
{'desc':'Jianhong Serial #2',
'nodeId':'0x725f5',
'parser':'serial_1',
'headend_loopback_enabled':1,
'thingworx_enabled':0,
'thingworx_app_key':'e6d09b31-7fe2-4db5-b1f5-cd55efb35b1c',
'm2x_enabled':0,
'm2x_device_id': '50ad616d0ba9735bd94072020d4cffd2',
'm2x_primary_key':'8548598bbbe544b4963583dd98f51c0f', 
'plasma_enabled':0,
'plasma_api_key':'GIS9jFLaBaZrkb3NTWjwM1nbz5gLDN',
'plasma_feed_key':'KZHbPInWmXwob5FXkxdAhNTeRNpc/xqyoBWLM1T7Hak=',
'alarm_email_enabled':0,
'alarm_email_list':[]},

{'nodeId': '0x729f0'},
{'nodeId': '0x729f1'},
{'nodeId': '0x72875'},
{'nodeId': '0x72565'},
{'nodeId': '0x724d7'},
{'nodeId': '0x725bd'},

{'desc':'Jianhong Serial #2',
'nodeId':'0x72a1c',
'parser':'serial_1',
'headend_loopback_enabled':1,
'thingworx_enabled':0,
'thingworx_app_key':'e6d09b31-7fe2-4db5-b1f5-cd55efb35b1c',
'm2x_enabled':0,
'm2x_device_id': '50ad616d0ba9735bd94072020d4cffd2',
'm2x_primary_key':'8548598bbbe544b4963583dd98f51c0f', 
'plasma_enabled':0,
'plasma_api_key':'GIS9jFLaBaZrkb3NTWjwM1nbz5gLDN',
'plasma_feed_key':'KZHbPInWmXwob5FXkxdAhNTeRNpc/xqyoBWLM1T7Hak=',
'alarm_email_enabled':0,
'alarm_email_list':[]},

#{'desc':'Jianhong Serial #2',
#'nodeId':'0x72a1c',
#'parser':'serial_1',
#'headend_loopback_enabled':1,
#'thingworx_enabled':0,
#'thingworx_app_key':'e6d09b31-7fe2-4db5-b1f5-cd55efb35b1c',
#'m2x_enabled':0,
#'m2x_device_id': '50ad616d0ba9735bd94072020d4cffd2',
#'m2x_primary_key':'8548598bbbe544b4963583dd98f51c0f', 
#'plasma_enabled':0,
#'plasma_api_key':'GIS9jFLaBaZrkb3NTWjwM1nbz5gLDN',
#'plasma_feed_key':'KZHbPInWmXwob5FXkxdAhNTeRNpc/xqyoBWLM1T7Hak=',
#'alarm_email_enabled':0,
#'alarm_email_list':[]}
]

with open('Devices.json', 'w') as outfile:
   json.dump(devices, outfile)

print "create_devices: Done"
