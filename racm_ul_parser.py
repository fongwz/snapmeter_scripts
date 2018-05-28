#!/bin/env python

import math
import datetime

#------------------------------------------------------------------------------
# RACM Message Parser: Does the work parsing the RACM Messages
#------------------------------------------------------------------------------
class RacmUlMssg:
   # Constants
   readIntervalMinutesTable = {0:15, 1:30, 2:60, 3:120, 4:180, 5:240, 6:360,\
      7:480, 8:720, 9:24*60, 10:0.5, 11:1, 12:2, 13:4, 14:8, 15:0}

   bytesPerReadingTable = {0x050:2, 0x051:1, 0x090:1, 0x0B0:1, 0x035:2}
   sensorUnitsTable = {0x050:'16 bit signed degrees F', 0x051:'8 bit signed degrees C',\
                       0x090:'1 bit digital I/O in lsbit', 0x0B0:'8 bit percent humidity',\
                       0x035:'16 bit signed DC mV'}

   def __init__(self, payload, expectedSensors=[], expectedAlarmTypes=[]):
      self.payload = payload
      self.data = [] 
      self.status = 'OK'
      self.err = []
      self.sensorInfo = []

      # In general we will keep grabbing the MSBytes and parsing them...

      # Remove leading '0x', if needed
      # MSBytes = self.get_msbytes_and_left_shift(1)

      # Get Message Type
      # NOTE: This parser ignores Config_Response(0x4), Legacy Alarm (0x1) messages and others
      # need to implement this later
      opcode = self.get_msbytes_and_left_shift(1)

      # Parse The Message, based on Message Type

      # Sensor Data History Message
      if opcode == '06':
         self.msgType = 'SensorData'
         sensorCnt = self.get_msbytes_and_left_shift(1)
         for i in range(int(sensorCnt)):
            sensorHeader = self.get_msbytes_and_left_shift(4)
            sensorHeader = self.big_2_little_endian(sensorHeader, 4)
            sensorId = self.bit_slice(sensorHeader, 3, 0) # note this will be appIntf-1
            sensorType = self.bit_slice(sensorHeader, 15, 4)
            stat = self.check_sensor(sensorId, sensorType, expectedSensors)
            if stat == 'ERROR':
               return
            sensorUnits = self.sensorUnitsTable[sensorType]
            self.sensorInfo.append({'sensorId':sensorId,\
                                    'sensorType':hex(sensorType),\
                                    'sensorUnits':sensorUnits,\
                                    'sensorName':self.sensorName,\
                                    'sensorDesc':self.sensorDesc})
            readInterval = self.bit_slice(sensorHeader, 23, 16)
            readCount = self.bit_slice(sensorHeader, 31, 24)
            sensorLastTimeStamp = self.get_msbytes_and_left_shift(4)
            sensorLastTimeStamp = self.get_racm_datetime(sensorLastTimeStamp)
            bytesPerReading = self.bytesPerReadingTable[sensorType]

            # Note we return a list of dictionaries containing time series data
            for j in range(readCount):
               mn = self.readIntervalMinutesTable[readInterval]
               if mn == 0 and readCount > 1:
                  print 'WARNING: unexpected readInterval (0) for multiple measurements', readCount
               data = self.get_msbytes_and_left_shift(bytesPerReading)
               data = self.big_2_little_endian(data, bytesPerReading)
               timeStamp = sensorLastTimeStamp - j * datetime.timedelta(minutes = mn)
               self.data.append({'sensorId' : sensorId,\
                  'sensorName' : self.sensorName,\
                  'timeStamp' : timeStamp,\
                  'data' : data})

      # Serial Data Message
      elif opcode == '07':
         self.msgType = 'Serial'
         # The serial message over the air doesn't contain sensorId=6, sensorName
         # but this matches the way we check other sensors. It is good to check the parser
         stat = self.check_sensor(6, 0xFFF, expectedSensors)
         if stat == 'ERROR':
            return
         byteCnt = self.get_msbytes_and_left_shift(2)
         byteCnt = self.big_2_little_endian(byteCnt, 2)
         # Note an SDU maximum size is 464 bytes, and we subtract opcode, and lenght
         if byteCnt <= 461:
            # Note we return a dictionary containing the hexadecimal serial data string, no leading 0x
            self.data = [{'sensorName':'serial', 'data':self.get_msbytes_and_left_shift(byteCnt)}]
         else:
            self.status = 'ERROR'
            self.err.append('Serial Data message length says too many bytes (Max=461) byteCnt: ' + str(byteCnt))

      # Config Message
      elif opcode == '04':
         self.msgType = 'Config'
         self.data = self.payload # we have not implemented parsing yet

      # Alarm Message
      elif opcode == '08':
         self.msgType = 'Alarm'
         alarmCnt = self.get_msbytes_and_left_shift(1)
         for i in range(int(alarmCnt)):
            d={}
            d['alarmCnt'] = alarmCnt # NOTE LCohen 01-08-2016 alarmCnt > 1 not supported!
            alarmLastTimeStamp = self.get_msbytes_and_left_shift(4)
            alarmLastTimeStamp = self.get_racm_datetime(alarmLastTimeStamp)
            d['timeStamp'] = alarmLastTimeStamp

            alarmState = int(self.get_msbytes_and_left_shift(1))
            if alarmState == 0:
               d['alarmState'] = 'Cleared'
            else:
               d['alarmState'] = 'Set'

            alarmType = int(self.get_msbytes_and_left_shift(1), 16)
            if alarmType < 8:
               d['alarmType'] = 'AppIntf%d' % (alarmType + 1) # app ID
            elif alarmType == 9:
               d['alarmType'] = 'LowBattery'
            elif alarmType == 12:
               d['alarmType'] = 'Exception'
            elif alarmType == 13:
               d['alarmType'] = 'TestButton'
            else:
               d['alarmType'] = 'OtherAlarmType=%d' % (alarmType)

            d['alarmExpected'] = d['alarmType'] in expectedAlarmTypes

            alarmDetailFormat = self.get_msbytes_and_left_shift(1)
            d['alarmDetailFormat'] = alarmDetailFormat # for debug

            # Analog Alarm
            if alarmDetailFormat == '01':
               analogValue = self.get_msbytes_and_left_shift(4)
               d['analogValue'] = self.big_2_little_endian(analogValue, bytesPerReading)
               analogUnits = self.get_msbytes_and_left_shift(2)
               d['analogUnits'] = self.big_2_little_endian(analogValue, bytesPerReading)
               upperThreshHi = self.get_msbytes_and_left_shift(4)
               d['upperThreshHi'] = self.big_2_little_endian(analogValue, bytesPerReading)
               upperThreshLo = self.get_msbytes_and_left_shift(4)
               d['upperThreshLo'] = self.big_2_little_endian(analogValue, bytesPerReading)
               lowerThreshHi = self.get_msbytes_and_left_shift(4)
               d['lowerThreshHi'] = self.big_2_little_endian(analogValue, bytesPerReading)
               lowerThreshLo = self.get_msbytes_and_left_shift(4)
               d['lowerThreshLo'] = self.big_2_little_endian(analogValue, bytesPerReading)
               analogAlarmType = int(self.get_msbytes_and_left_shift(1))
               if analogAlarmType == 1:
                  d['analogAlarmType'] = 'High_Threshold'
               elif analogAlarmType == 2:
                  d['analogAlarmType'] = 'Low_Threshold'
               elif analogAlarmType == 3:
                  d['analogAlarmType'] = 'Outside_Range'
               elif analogAlarmType == 4:
                  d['analogAlarmType'] = 'Inside_Range (does anyone really use this?)'
      
            # Digital Alarm
            elif alarmDetailFormat == '02':
                # This is was the alarm condition that triggered. 1=Active Hi, 2=Active Low
                digAlarmThresh = int(self.get_msbytes_and_left_shift(1))
                if digAlarmThresh == 1:
                   d['digAlarmThresh'] = 'Active_High'
                elif digAlarmThresh == 2:
                   d['digAlarmThresh'] = 'Active_Low'
                else:
                   d['digAlarmThresh'] = 'Unknown Value: %d' %(digAlarmThresh)
                   self.status = 'ERROR'
                   self.err.append('unknown digital alarm threshold: %d' %(digAlarmThresh))

            # Exception Alarm
            elif alarmDetailFormat == '03':
                d['exceptionAlarmType'] = self.get_msbytes_and_left_shift(1)

            # Write Dictionary of Alarm Data
            self.alarmData = d

      # Unknown Message
      else:
         self.msgType = 'Unknown'
         self.status = 'ERROR'
         self.err.append('unknown message type: opcode = ' + opcode)

   # User Methods:

   def getStatus(self):
      return self.status

   def getMsgType(self):
      return self.msgType

   # Note this is informational only since the head end should know a priori what 
   # kind of device this is. It could be used for error checking.
   def getSensorInfo(self):
      return self.sensorInfo

   def getData(self):
      return self.data

   def getAlarmData(self):
      return self.alarmData

   def getError(self):
      return self.err

   # Local Functions
   # Check that a sensor is the expected Id and Type
   def check_sensor(self, sensorId, sensorType, expectedSensors):
      self.sensorName = ''
      self.sensorDesc = ''
      # Skip Checking if no information supplied
      if len(expectedSensors) == 0:
         return

      foundSensorId = 0
      for d_exp in expectedSensors:
         if d_exp['sensorId'] == sensorId:
            foundSensorId = 1
            expSensorType = d_exp['sensorType']
            expSensorName = d_exp['sensorName']
            expSensorDesc = d_exp['sensorDesc']

      if not foundSensorId:
         self.status = 'ERROR'
         self.err.append('Unexpected SensorId message contains: %d, expected one of: %s' % (sensorId, expectedSensors))
         return 'ERROR'
      elif sensorType != expSensorType:
         self.status = 'ERROR'
         self.err.append('Unexpected SensorType message contains: %s, expected: %s' % (hex(int(sensorType)), hex(int(expSensorType))))
         return 'ERROR'
      else:
         self.sensorName = expSensorName
         self.sensorDesc = expSensorDesc
         return 'OK'
      
   # Parse the timestamp in a RACM UL Message and
   # convert it to a datetime object
   def get_racm_datetime(self, word):
      word = self.big_2_little_endian(word, 4)
      sec = self.bit_slice(word, 5, 0)
      mn = self.bit_slice(word, 11, 6)
      hr = self.bit_slice(word, 16, 12)
      day = self.bit_slice(word, 21, 17)
      mon = self.bit_slice(word, 25, 22)
      yr = self.bit_slice(word, 31, 26) + 2000 # offset from base=y2k
      try:
         dt = datetime.datetime(yr, mon, day, hr, mn, sec, 0)
      except:
         self.status = 'ERROR'
         self.err.append('error converting RACM timestamp to datetime: ' + hex(word))

      return dt

   # Returns the Left MSBytes requested and changes payload to chop off the MSBytes
   def get_msbytes_and_left_shift(self, num_bytes):
      # Note I believe payload can be too big to treat as int, so do shifting,
      # and chunking of payload as strings
      MSBytes = self.payload[0:2*num_bytes]
      self.payload = self.payload[2*num_bytes:]
      return MSBytes

   # Takes in a string representing N bytes big endian and converts to an int
   # with the endianness changed to little endian. No leading 0x on big_in
   def big_2_little_endian(self, big_in, num_bytes):
      little_out = ''

      for i in range(num_bytes-1, -1, -1):
         little_out += big_in[2*i:2*i+2]

      little_out = int('0x'+little_out, 16)
      return little_out
   
   # Returns an integer value for the bit slice, word input is integer
   # ex. bit_slice(0x32, 7, 4) = 3
   def bit_slice(self, input_word, msb_index, lsb_index):
      mask = pow(2, msb_index + 1) - 1
      slice = (input_word & mask) >> lsb_index
      return slice
