#!/bin/env python
# getLoginInfo.py LCohen 2/29/2016
# Gets hostname, username, password from a JSON file
# The user can modify the JSON file (login_info.json) with his own credentials

import json

def getLoginInfo(infilename):

   with open(infilename,'r') as infile:
       login_dict = json.load(infile)[0]
       infile.close()
       host = login_dict["host"]
       username = login_dict["username"]
       password = login_dict["password"]
       return (host, username, password)

