#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder

echo "== Updating Aruba stacked switches - $(date)"
ansible --version

#ansible-playbook playbooks/sync_data.yaml &> ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_stacks.py &&

#ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,delete_chassis &>> ${logs_folder}/aruba_stack_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,switches &> ${logs_folder}/aruba_stack_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,interfaces &>> ${logs_folder}/aruba_stack_ports.logs &&

ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,chassis &>> ${logs_folder}/aruba_stack_ports.logs
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,trunks &>> ${logs_folder}/aruba_stack_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,create_vlans &>> ${logs_folder}/aruba_stack_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,untagged_vlans &>> ${logs_folder}/aruba_stack_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,tagged_vlans &>> ${logs_folder}/aruba_stack_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,ip &>> ${logs_folder}/aruba_stack_ports.logs

echo "== Done updating Aruba stacked switches - $(date)"