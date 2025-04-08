#!/usr/bin/env bash

# Update devices yaml data files

# Get the scripts directory
SCRIPT_DIR="$(dirname $(realpath $0))"

python3 ${SCRIPT_DIR}/yaml_aruba.py
python3 ${SCRIPT_DIR}/yaml_aruba_os_cx.py
#python3 ${SCRIPT_DIR}/yaml_cisco.py