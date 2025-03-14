#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder
ansible --version

#ansible-playbook playbooks/sync_data.yaml | tee ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_singles.py &&

ansible-playbook playbooks/hp_switches.yaml --tags aruba_8,production,switches | tee ${logs_folder}/aruba_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_8,production,trunks | tee -a ${logs_folder}/aruba_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_8,production,interfaces | tee -a ${logs_folder}/aruba_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_8,production,create_vlans | tee -a ${logs_folder}/aruba_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_8,production,untagged_vlans | tee -a ${logs_folder}/aruba_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_8,production,tagged_vlans | tee -a ${logs_folder}/aruba_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_8,production,ip | tee -a ${logs_folder}/aruba_8_ports.logs