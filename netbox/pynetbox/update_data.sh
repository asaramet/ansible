#!/usr/bin/env bash

# Update devices yaml data files

# Get the scripts directory
SCRIPT_DIR="$(dirname $(realpath $0))"

python3 ${SCRIPT_DIR}/yaml_singles.py
python3 ${SCRIPT_DIR}/yaml_stacks.py
python3 ${SCRIPT_DIR}/yaml_hpe_modular.py
python3 ${SCRIPT_DIR}/yaml_aruba_6xxx.py
#python3 ${SCRIPT_DIR}/yaml_cisco.py