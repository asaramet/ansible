#!/usr/bin/env bash

# Update netbox switches configs from synct config files

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $EXEC_DIR

echo "== Updating HPE 8 Ports switches - $(date)"
ansible --version
echo "Log file: ${logs_folder}/hpe_8_ports.logs"

#ansible-playbook playbooks/sync_data.yaml &> ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_singles.py &&

ansible-playbook playbooks/hp_switches.yaml --tags hpe_8,production,switches &> ${logs_folder}/hpe_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags hpe_8,production,trunks &>> ${logs_folder}/hpe_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags hpe_8,production,interfaces &>> ${logs_folder}/hpe_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags hpe_8,production,create_vlans &>> ${logs_folder}/hpe_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags hpe_8,production,untagged_vlans &>> ${logs_folder}/hpe_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags hpe_8,production,tagged_vlans &>> ${logs_folder}/hpe_8_ports.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags hpe_8,production,ip &>> ${logs_folder}/hpe_8_ports.logs

echo "== Done updating HPE 8 Ports switches - $(date)"