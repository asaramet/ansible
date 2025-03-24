#!/usr/bin/env bash

# Update netbox switches configs from synct config files

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $EXEC_DIR

echo "== Updating ProCurve switches - $(date)"
ansible --version
echo "Log file: ${logs_folder}/procurve_single.logs"

#ansible-playbook playbooks/sync_data.yaml &> ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_singles.py &&

ansible-playbook playbooks/hp_switches.yaml --tags procurve_single,production,switches &> ${logs_folder}/procurve_single.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_single,production,trunks &>> ${logs_folder}/procurve_single.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_single,production,interfaces &>> ${logs_folder}/procurve_single.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_single,production,create_vlans &>> ${logs_folder}/procurve_single.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_single,production,untagged_vlans &>> ${logs_folder}/procurve_single.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_single,production,tagged_vlans &>> ${logs_folder}/procurve_single.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_single,production,ip &>> ${logs_folder}/procurve_single.logs

echo "== Done updating ProCurve switches - $(date)"