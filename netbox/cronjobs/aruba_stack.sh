#!/usr/bin/env bash

# Update netbox switches configs from synct config files

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $EXEC_DIR

echo "== Updating Aruba stacked switches - $(date)"
ansible --version
echo "Log file: ${logs_folder}/aruba_stack.logs"

#ansible-playbook playbooks/sync_data.yaml &> ${logs_folder}/sync_data.logs
#python3 pynetbox/yaml_stacks.py &&

#ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,delete_chassis &>> ${logs_folder}/aruba_stack.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,switches &> ${logs_folder}/aruba_stack.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,interfaces &>> ${logs_folder}/aruba_stack.logs &&

ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,chassis &>> ${logs_folder}/aruba_stack.logs
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,trunks &>> ${logs_folder}/aruba_stack.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,create_vlans &>> ${logs_folder}/aruba_stack.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,untagged_vlans &>> ${logs_folder}/aruba_stack.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,tagged_vlans &>> ${logs_folder}/aruba_stack.logs &&
ansible-playbook playbooks/stacks.yaml --tags aruba_stack,production,ip &>> ${logs_folder}/aruba_stack.logs

echo "== Done updating Aruba stacked switches - $(date)"