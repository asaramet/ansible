#!/usr/bin/env bash

# Update netbox ProCurve Modular switches configs

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $EXEC_DIR

echo "== Updating ProCurve modular switches - $(date)"
ansible --version
echo "Log file: ${logs_folder}/procurve_modular.logs"

#ansible-playbook playbooks/sync_data.yaml &> ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_hpe_modular.py &&

ansible-playbook playbooks/hp_switches.yaml --tags procurve_modular,production,switches &> ${logs_folder}/procurve_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_modular,production,modules &>> ${logs_folder}/procurve_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_modular,production,trunks &>> ${logs_folder}/procurve_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_modular,production,interfaces &>> ${logs_folder}/procurve_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_modular,production,create_vlans &>> ${logs_folder}/procurve_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_modular,production,untagged_vlans &>> ${logs_folder}/procurve_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_modular,production,tagged_vlans &>> ${logs_folder}/procurve_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags procurve_modular,production,ip &>> ${logs_folder}/procurve_modular.logs

echo "== Done updating ProCurve modular switches - $(date)"