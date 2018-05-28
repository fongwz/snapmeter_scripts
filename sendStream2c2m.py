# NOTES:
#  "timestamp":"2015-10-15T18:23:01Z"})

import socket
import time
import datetime

TCP_IP = '199.108.99.62' # C2M TCP Server
TCP_PORT = 3001          # C2M TCP Port
BUFFER_SIZE = 1024       # TCP Message Buffer

def TCP_send(MESSAGE):
    length = len(MESSAGE)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TCP_IP, TCP_PORT))
    if s.send(MESSAGE):
        print 'Sending TCP Message to C2M: ' + MESSAGE + 'at ' + str(datetime.datetime.now())
        return True
    else:
        print 'ERROR: SendLocRssi2Plasma failed'
        return False
    s.close()
    del MESSAGE

def sendTempHumidity2c2m(api_key, feed_key, timestamp, tempf, humidity):
    time.sleep(1.1) # Delay required by M2x, could be optimized, cause they specify 1 sec/stream

    # Create TCP message payload expected by c2m
    MESSAGE = 'apikey:'+api_key+',feedId:'+feed_key+',feed='+\
       'tempf,'+str(tempf)+'|humidity,'+str(humidity)+'|devicedatetime,'+timestamp
    #print 'MESSAGE = ', MESSAGE
    TCP_send(MESSAGE)

    return '0' # don't know what could be sent in error case

###   MAIN   #############################################################################
if __name__ == '__main__':

   api_key = 'GIS9jFLaBaZrkb3NTWjwM1nbz5gLDN'
   feed_key = 'KZHbPInWmXwob5FXkxdAhNTeRNpc/xqyoBWLM1T7Hak='
   timestamp = '2015-04-08T11:23:45Z'
   lat = '32.7782'
   lng = '-96.7753'
   rssi = '-105'
   sendLocRssi2Plasma(api_key, feed_key, timestamp, lat, lng, rssi)

