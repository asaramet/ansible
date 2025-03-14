#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder

ansible-playbook playbooks/sync_data.yaml | tee ${logs_folder}/sync_data.logs

python3 pynetbox/yaml_singles.py | tee ${logs_folder}/yaml_singles.logs  &&
python3 pynetbox/yaml_stacks.py | tee ${logs_folder}/yaml_stacks.logs  && 
python3 pynetbox/yaml_hpe_modular.py | tee ${logs_folder}/yaml_hpe_modular.logs  &&

#python3 pynetbox/yaml_aruba_6xxx.py | tee ${logs_folder}/yaml_aruba_6xxx.logs &&
#python3 pynetbox/yaml_cisco.py | tee ${logs_folder}/yaml_cisco.logs 

cd $this_folder
./aruba_8_ports.sh &&
./aruba_12_ports.sh &&
./aruba_48_ports.sh &&

./hpe_8_ports.sh &&
./hpe_48_ports.sh &&

./aruba_stack_2920.sh &&
./aruba_stack_2930.sh &&

./procurve_single.sh &&
./procurve_modular.sh

#./aruba_modular.sh &&
#./aruba_modular_stack.sh &&

#./aruba_6xxx.sh