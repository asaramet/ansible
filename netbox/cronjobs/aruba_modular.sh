#!/usr/bin/env bash

# Update netbox Aruba Modular switches configs

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder

#server='production'
server='development'

echo "== Updating Aruba Modular switches on $server server - $(date)"
ansible --version

#ansible-playbook playbooks/sync_data.yaml &>> ${logs_folder}/sync_data.logs

ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,${server},switches &> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,${server},modules &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,${server},trunks &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,${server},interfaces &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,${server},create_vlans &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,${server},untagged_vlans &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,${server},tagged_vlans &>> ${logs_folder}/aruba_modular.logs &&
ansible-playbook playbooks/hp_switches.yaml --tags aruba_modular,${server},ip &>> ${logs_folder}/aruba_modular.logs

echo "== Done updating Aruba Modular switches - $(date)"