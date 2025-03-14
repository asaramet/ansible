#!/usr/bin/env bash

# Update netbox ProCurve Modular switches configs

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder
ansible --version

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