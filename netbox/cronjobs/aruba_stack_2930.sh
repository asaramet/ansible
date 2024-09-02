#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder
ansible --version

#ansible-playbook playbooks/sync_data.yaml | tee ${logs_folder}/sync_data.logs

ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,switches | tee ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,delete_chassis | tee ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,modules | tee -a ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,trunks | tee -a ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,interfaces | tee -a ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,create_vlans | tee -a ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,untagged_vlans | tee -a ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,tagged_vlans | tee -a ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,ip | tee -a ${logs_folder}/aruba_stack_2930_ports.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2930,production,chassis | tee ${logs_folder}/aruba_stack_2930_ports.logs