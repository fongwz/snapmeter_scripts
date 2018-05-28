#!/bin/env python
# getDeviceInfo.py look up information

# Returns a dictionary, with parser info and m2x keys for nodeId
def getDeviceInfo(node_id_hex, devices):
    match_found = 0 # no match found
    ret_dict = {}
    for device in devices:
       if int(device['nodeId'], 16) == int(node_id_hex, 16):
          ret_dict = device
          match_found = 1

    return (match_found, ret_dict)

