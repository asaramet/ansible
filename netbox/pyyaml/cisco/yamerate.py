#!/usr/bin/env python3

# Collect Cisco devices data and create yaml configs file 

import logging
logger = logging.getLogger(__name__)

#import re, os, sys, yaml
#from tabulate import tabulate


def devices_json(data_folder):
    logger.info(data_folder)

if __name__ == "__main__":
    from std_functions import _main
    _main("Collect devices info into a JSON file", devices_json)
