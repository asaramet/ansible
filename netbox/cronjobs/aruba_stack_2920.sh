#!/usr/bin/env bash

# Update netbox switches configs from synct config files

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $EXEC_DIR

echo "== Updating Aruba 2920 stacked switches - $(date)"
ansible --version
echo "Log file: ${logs_folder}/aruba_stack_2920.logs"

#ansible-playbook playbooks/sync_data.yaml &> ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_stacks.py &&

#ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,delete_chassis &>> ${logs_folder}/aruba_stack_2920.logs &&

ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,switches &> ${logs_folder}/aruba_stack_2920.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,modules &>> ${logs_folder}/aruba_stack_2920.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,interfaces &>> ${logs_folder}/aruba_stack_2920.logs &&

ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,chassis &>> ${logs_folder}/aruba_stack_2920.logs

ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,trunks &>> ${logs_folder}/aruba_stack_2920.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,create_vlans &>> ${logs_folder}/aruba_stack_2920.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,untagged_vlans &>> ${logs_folder}/aruba_stack_2920.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,tagged_vlans &>> ${logs_folder}/aruba_stack_2920.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack_2920,production,ip &>> ${logs_folder}/aruba_stack_2920.logs 

echo "== Dome updating Aruba 2920 stacked switches - $(date)"