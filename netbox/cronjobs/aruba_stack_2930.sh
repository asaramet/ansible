#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder

echo "== Updating Aruba 2930 stacked switches - $(date)"
ansible --version

#ansible-playbook playbooks/sync_data.yaml &> ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_stacks.py &&

#ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,delete_chassis &>> ${logs_folder}/aruba_stack_2930_ports.logs &&

ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,switches &> ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,modules &>> ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,interfaces &>> ${logs_folder}/aruba_stack_2930_ports.logs &&

ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,chassis &>> ${logs_folder}/aruba_stack_2930_ports.logs

ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,trunks &>> ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,create_vlans &>> ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,untagged_vlans &>> ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,tagged_vlans &>> ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,ip &>> ${logs_folder}/aruba_stack_2930_ports.logs 

echo "== Done updating Aruba 2930 stacked switches - $(date)"