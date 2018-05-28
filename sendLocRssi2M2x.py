# NOTES:
#    body = json.dumps({"value": value, "timestamp":"2015-10-15T18:23:01.000Z"})
# or body = json.dumps({"value": value, "timestamp":"2015-10-15T18:23:01Z"})

import time
import datetime
import httplib
import json

def sendLocRssi2M2x(primary_key, device_id, timestamp, lat, lng, rssi):
    time.sleep(1.1) # Delay required by M2x, could be optimized, cause they specify 1 sec/stream
    m2x_host = 'api-m2x.att.com'
    url = '/v2/devices/' + device_id + '/location'
    headers = {"Content-Type": "application/json", "X-M2X-KEY": primary_key}
    body = json.dumps({"latitude":lat, "longitude":lng, "timestamp":timestamp, "elevation":rssi})
    print "Connecting to " + m2x_host + url + str(datetime.datetime.now())
    m2x_conn = httplib.HTTPConnection(m2x_host)
    m2x_conn.request("PUT", url, body, headers)
    response = m2x_conn.getresponse()
    http_status =  response.status
    # 202 = 'Accepted' This is what I see from ATT in the success case
    # 404 = 'Not Found' This is what I see from ATT in the case of incorrect keys (primary/device)
    # or other poorly formed url
    if http_status == 202:
       result = response.read()
       return result
    elif http_status == 404:
       print 'ERROR(SendLocRssi2M2x.py): HTTP Status = ', http_status, datetime.datetime.now()
       print 'DEBUG: Check that the m2x_primary_key, m2x_device_id are correct in create_devices.py'
       return http_status
    else:
       print 'ERROR(SendLocRssi2M2x.py): HTTP Status = ', http_status, datetime.datetime.now()
       return http_status
