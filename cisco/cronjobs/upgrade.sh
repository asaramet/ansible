#!/usr/bin/env bash

# Upgrade devices firmware

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

echo -e "=== Source Ansible ===\n"
source /opt/ansible/envs
cd /opt/ansible/inventories/aruba
ansible --version

HOSTS_GROUPS='cisco'

for i in ${HOSTS_GROUPS}; do

echo -e "\n++ Firmware version ${i} before updates --\n"
ansible-playbook playbooks/show_version.yaml -l ${i} | tee ${logs_folder}/${i}_version_before.logs

ansible-playbook playbooks/update.yaml -l ${i} | tee ${logs_folder}/${i}_update_.logs
ansible-playbook playbooks/reboot.yaml -l ${i} | tee ${logs_folder}/${i}_reboot.logs

sleep 15m &&
echo -e "\n++ Firmware version ${i} after updates --\n"
ansible-playbook playbooks/show_version.yaml -l ${i} | tee ${logs_folder}/${i}_version_after.logs

done