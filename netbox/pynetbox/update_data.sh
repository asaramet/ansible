#!/usr/bin/env bash

# Update devices yaml data files by running data collection scripts

# Get the scripts directory
SCRIPT_DIR="$(dirname $(realpath $0))"

python3 ${SCRIPT_DIR}/yaml_aruba.py
#python3 ${SCRIPT_DIR}/yaml_aruba_os_cx.py
#python3 ${SCRIPT_DIR}/yaml_cisco.py

# Update NetBox over python and pynetbox

server='development'
server='production'

python3 ${SCRIPT_DIR}/add_locations.py -s ${server}
python3 ${SCRIPT_DIR}/add_switches.py -s ${server}
python3 ${SCRIPT_DIR}/chassis.py -s ${server}
python3 ${SCRIPT_DIR}/modules.py -s ${server}