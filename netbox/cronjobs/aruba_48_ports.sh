#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder

echo "== Updating Aruba 48 Ports Switches - $(date)"
ansible --version

#ansible-playbook playbooks/sync_data.yaml &>> ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_singles.py &&

ansible-playbook playbooks/hp_switches.yaml --tags aruba_48,production,switches &> ${logs_folder}/aruba_48_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_48,production,trunks &>> ${logs_folder}/aruba_48_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_48,production,interfaces &>> ${logs_folder}/aruba_48_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_48,production,create_vlans &>> ${logs_folder}/aruba_48_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_48,production,untagged_vlans &>> ${logs_folder}/aruba_48_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_48,production,tagged_vlans &>> ${logs_folder}/aruba_48_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_48,production,ip &>> ${logs_folder}/aruba_48_ports.logs

echo "== Done updating Aruba 48 Ports Switches - $(date)"