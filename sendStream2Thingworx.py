# NOTES:
# 1) LC 9/13/2016 should improve someday to send multiple measurements, maybe even multiple devices in one POST

import time
import datetime
import httplib
import json
import ssl

def sendStream2Thingworx(app_key, node_id_hex, stream, timestamp, value):
    #thingworx_host = '52.4.2.14' # this should go in a config file as a future enhancement
    thingworx_host = 'wave.thingworx.com:8443' # this should go in a config file as a future enhancement
    # https://52.4.2.14/Thingworx/Things/*0x56A36/Services/UpdatePropertyValues 
    # Note hex(int(node_id_hex is to get rid of leading zeros. I don't recall why node_id_hex is passed in with leading 0's
    url = '/Thingworx/Things/*' + hex(int(node_id_hex,16)) + '/Services/UpdatePropertyValues'
    # -H "appKey: e6d09b31-7fe2-4db5-b1f5-cd55efb35b1c" -H "Accept: application/json" -H "Content-Type: application/json" -H "Cache-Control: no-cache"  
    headers = {"appKey":app_key, "Accept":"application/json", "Content-Type": "application/json", "Cache-Control":"no-cache"}
    body = '{"values":{"created":1473708874231,"description":"","name":"Infotable","dataShape":{"fieldDefinitions":{"name":{"name":"name","aspects":{"isPrimaryKey":true},"description":"Property name","baseType":"STRING","ordinal":0},"time":{"name":"time","aspects":{},"description":"time","baseType":"DATETIME","ordinal":0},"value":{"name":"value","aspects":{},"description":"value","baseType":"VARIANT","ordinal":0},"quality":{"name":"quality","aspects":{},"description":"quality","baseType":"STRING","ordinal":0}},"name":"NamedVTQ","description":"Property name, value, time, quality, state"},\
"rows":[\
                {"name":"' + stream + '","time":"' + timestamp + '","value":"' + str(value) + '","quality":"GOOD"}\
]}\
}'
    print "Connecting to " + thingworx_host + url + ' at time' + str(datetime.datetime.now())
    #thingworx_conn = httplib.HTTPConnection(thingworx_host)
    thingworx_conn = httplib.HTTPSConnection(thingworx_host, context=ssl._create_unverified_context())
    thingworx_conn.request("POST", url, body, headers)
    response = thingworx_conn.getresponse()
    http_status =  response.status
    verbose_status = response.read()
    # 200 is success for Thingworx I was told
    # 202 = 'Accepted' This is what I see from ATT in the success case
    # 404 = 'Not Found' This is what I see from ATT in the case of incorrect keys (primary/device)
    # or other poorly formed url
    if http_status == 200:
       #result = response.read()
       # LC 9/13/2016 Thingworx has no response body, just 200. So give it the response below
       result = '{"status":"accepted"}'
       return result
    else:
       print 'ERROR(sendStream2Thingworx.py): HTTP Status = ', http_status, verbose_status, datetime.datetime.now()
       return http_status

if __name__ == '__main__':
   sendStream2Thingworx('e6d09b31-7fe2-4db5-b1f5-cd55efb35b1c', '0x56a36', 'temp_f', '2016-09-13T22:39:57Z', 85)
