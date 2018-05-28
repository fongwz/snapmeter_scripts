# -*- coding: utf-8 -*-
# NOTES:
# 1) LC 9/13/2016 should improve someday to send multiple measurements, maybe even multiple devices in one POST

import time
import datetime
import httplib
import json
import ssl
import paho.mqtt.client as mqtt

def sendMqtt2Thingworx(node_id_hex, stream, timestamp, value):
    #print node_id_hex, stream, timestamp, value
    node_id_hex = hex(int(node_id_hex, 16)) # this strips the leading zeros

    topic = 'ingenu'
    mqtt_broker = '52.44.66.185'
    #message = '{"device":"' + node_id_hex + '","name":"' + stream + '"time":"' + timestamp + '","value":"' + str(value) + '","quality":"GOOD"}'
    # Lew: decided to use built in dict to JSON
    message_dict = {"device":node_id_hex, "name":stream, "time":timestamp, "value":str(value), "quality":"GOOD"}
    message = json.dumps(message_dict)
    print "message = ", message
    # Use other format above per Jake Moody Thingworx 9/17/2016
    # This format is for sending to a Thingworx Service
    #message = '{"values":{"created":1473708874231,"description":"","name":"Infotable","dataShape":{"fieldDefinitions":{"name":{"name":"name","aspects":{"isPrimaryKey":true},"description":"Property name","baseType":"STRING","ordinal":0},"time":{"name":"time","aspects":{},"description":"time","baseType":"DATETIME","ordinal":0},"value":{"name":"value","aspects":{},"description":"value","baseType":"VARIANT","ordinal":0},"quality":{"name":"quality","aspects":{},"description":"quality","baseType":"STRING","ordinal":0}},"name":"NamedVTQ","description":"Property name, value, time, quality, state"},\
#                "rows":[\
#                    {"name":"' + stream + '","time":"' + timestamp + '","value":"' + str(value) + '","quality":"GOOD"}\
#                ]}\
#            }'
    
    print "Connecting to MQTT Broker: " + mqtt_broker + ' at time ' + str(datetime.datetime.now())

    mqttc = mqtt.Client()
    # Removed per Jake
    # mqttc.tls_set("ca.crt")
    mqttc.connect(mqtt_broker, 1883)
    mqttc.publish(topic, message)
    mqttc.disconnect()

    return '{"status":"accepted"}'
    
    
if __name__ == '__main__':
   sendMqtt2Thingworx('0x000724ff', 'temp_f', '2016-09-13T22:39:57Z', 62)
