#!/usr/bin/env python3

# Return Cisco devices JSON objects

import logging
import re
from pathlib import Path
from std_functions import data_folder, get_hostname_and_stack

logger = logging.getLogger(__name__)


def devices_json(data_folder):
    data = {'devices': [], 'chassis': []}

    for device in get_hostname_and_stack(data_folder):
        hostname = device['hostname']

        if not device['stack']:
            data['devices'].append({
                'name': hostname
            })
            continue

        data['chassis'].append({
            'master':f"{hostname}-1",
            'name': hostname
        })

        for switch_nr in device['switches']:
            data['devices'].append({
                'name': f"{hostname}-{switch_nr}"
            })

    return data

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from functions import _debug

    # Test the get_hostname_and_stack function
    _debug(devices_json, data_folder)

'''
devices:
- device_role: distribution-layer-switch
  device_type: hpe-5406r-zl2
  name: rscs0007-1
  serial: SG7AG4906Y
  site: campus-stadtmitte
  tags: &id001
  - switch
  - stack
  vc_position: 1
  vc_priority: 255
  virtual_chassis: rscs0007
'''