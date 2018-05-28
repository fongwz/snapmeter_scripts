#!/bin/env python

import httplib
import json
import traceback

host = "172.16.50.11:8001"

test_url = "/test"

# When using test_m2xCallback.py to monitor the health of m2xCallback.py and restart it, you should set device serial to
# something we don't expect, such as ABC123 to avoid nuisance emails etc. Conversely, if you want a text or downlink,
# you must set serial to a device that was defined in create_devices.py
test_body = {'device':{'serial':'ABC123'}}

test_json = json.dumps(test_body)
print 'test_json' , test_json

test_headers = {"Content-Type": "application/json"}

#------------------------------------------------------------------------------
# POST test
#------------------------------------------------------------------------------
def doPostTest(test_conn):
   try:
      test_conn.request("POST", test_url, test_json, test_headers)
      response = test_conn.getresponse()
      result = response.read()
      print 'Result = ', result
      test_conn.close()
   except:
      print 'test_m2xCallback.py: Exception (traceback below):'
      traceback.print_exc()
      res = test_conn.close()
      print 'Result of close = ', res

#------------------------------------------------------------------------------
# MAIN
#------------------------------------------------------------------------------
test_conn = httplib.HTTPConnection(host) # use this for VM use HTTP (LEW SHOULD MOVE TO CONFIG FILE HTTP VS HTTPS)

if __name__ == '__main__':
   doPostTest(test_conn)
