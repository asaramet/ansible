#!/usr/bin/env bash

# Update netbox Aruba Modular switches configs

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder
ansible --version

#ansible-playbook playbooks/sync_data.yaml &>> ${logs_folder}/sync_data.logs

ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,switches &> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,modules &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,trunks &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,interfaces &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,create_vlans &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,untagged_vlans &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,tagged_vlans &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,ip &>> ${logs_folder}/aruba_modular.logs