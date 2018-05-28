0) Get a primary key and device ID from the m2x web site for your device
1) Edit createDevices.py to make an entry for your device, then run it
   to get a .json output file that will be used by rest2m2x to look up device to parser mappings etc.
1A) If your device doesn't use one of the supported parsers:
1B) add a parser name to createDevices.py
1C) in parsers.py, add a function for your parser, name format is parser_xxx, see examples
1D) in rest2m2x.py add an elif clause for your parser, see Temp/Humidity example
   The main functions in rest2m2x are:
     1) logging/error handling,
     2) decimating data to meet M2x rate limits
     3) converting alarms to data stream data (for m2x's trigger functions)
     4) submitting the data to M2x and verifying acceptance
     5) converting multi sensor data to single m2x streams
     6) submitting multi measurements one at a time to m2x


Command line: stdbuf -oL python rest2M2x.py | tee -a log.txt   (stdbuf flushes log entries quickly to the screen)
or better:
use runscript to launch the script, and add this to your crontab (commmand is crontab -e):
*/5 * * * * /opt/ingenu/m2m/m2m_thingworx/runscript  (this sets 5 minute timeout to restart, save :w)

File list:
rest2Thingworx.py: main script looks up each UL SDU's nodeId to get parser information and M2x Keys, submits to M2x etc.
createDevices.py: creates the file ATT_Devices.json containing the mapping of nodeId, key, parser, other config
ATT_Devices.json: generated file containing device info for all known nodes, including which parser etc.
getNextUlSdu.py: gets the next UL SDU from the REST interface, based on the SDU ID stored in file nextUlSdu.cfg
nextUlSdu.cfg: provides non-volatile storage of the next UL SDU ID to parse, in case the script is restarted
   During new parser development you may edit this file to re-submit SDUs to the script
racm_ul_parser.py: class that knows how to parse RACM payloads. Methods are used to get Data, Status, MsgType etc.
parsers.py: Each device has a known expected set of sensors (ex. Temp and Humidity). This script
  checks that the expected data type is returned, and flags errors. It calls racm_ul_parser,
  except in special cases (ex. GPS).
sendStream2M2x.py: performs the HTTP Put of stream data to M2X and verifies success
sendLocRssi2M2x.py: performs the HTTP Put of location/RSSI data to M2X and verifies success
sendEmails.py: sends automated email alerts (texts also by emailing to a phone number)
m2xCallback.py: This is a daemon, listening on port 8001 for posts from M2X. Currently it supports two modes: 
   serial loopback and alarm email generation, based on device type (in the M2X post)

Gaowei: loopback and send data with receive data