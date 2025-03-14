#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder
ansible --version

#ansible-playbook playbooks/sync_data.yaml &>> ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_singles.py &&

ansible-playbook playbooks/hp_switches.yaml --tags aruba_12,production,switches &> ${logs_folder}/aruba_12_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_12,production,trunks &>> ${logs_folder}/aruba_12_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_12,production,interfaces &>> ${logs_folder}/aruba_12_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_12,production,create_vlans &>> ${logs_folder}/aruba_12_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_12,production,untagged_vlans &>> ${logs_folder}/aruba_12_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_12,production,tagged_vlans &>> ${logs_folder}/aruba_12_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_12,production,ip &>> ${logs_folder}/aruba_12_ports.logs