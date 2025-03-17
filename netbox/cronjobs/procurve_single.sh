#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder

echo "== Updating ProCurve switches - $(date)"
ansible --version

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