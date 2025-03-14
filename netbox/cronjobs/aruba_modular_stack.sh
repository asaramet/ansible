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

ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular_stack,production,switches &> ${logs_folder}/aruba_modular_stack.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular_stack,production,modules &>> ${logs_folder}/aruba_modular_stack.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular_stack,production,interfaces &>> ${logs_folder}/aruba_modular_stack.logs &&

ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular_stack,production,chassis &>> ${logs_folder}/aruba_modular_stack.logs &&

ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular_stack,production,trunks &>> ${logs_folder}/aruba_modular_stack.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular_stack,production,create_vlans &>> ${logs_folder}/aruba_modular_stack.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular_stack,production,untagged_vlans &>> ${logs_folder}/aruba_modular_stack.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular_stack,production,tagged_vlans &>> ${logs_folder}/aruba_modular_stack.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular_stack,production,ip &>> ${logs_folder}/aruba_modular_stack.logs