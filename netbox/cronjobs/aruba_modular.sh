#!/usr/bin/env bash

# Update netbox Aruba Modular switches configs

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder
ansible --version

#ansible-playbook playbooks/sync_data.yaml | tee ${logs_folder}/sync_data.logs

ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,switches | tee ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,modules | tee -a ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,trunks | tee -a ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,interfaces | tee -a ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,create_vlans | tee -a ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,untagged_vlans | tee -a ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,tagged_vlans | tee -a ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,production,ip | tee -a ${logs_folder}/aruba_modular.logs