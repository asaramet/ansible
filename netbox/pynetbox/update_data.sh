#!/usr/bin/env bash

# Update all data
python3 yaml_aruba_6100.py
python3 yaml_hpe_singles.py
python3 yaml_hpe_modular.py
python3 yaml_stacks.py