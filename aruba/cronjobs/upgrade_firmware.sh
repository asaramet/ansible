#!/usr/bin/env bash

# Upgrade devices firmware

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

echo -e "=== Source Ansible ===\n"
source /opt/ansible/envs
cd /opt/ansible/inventories/aruba
ansible --version

#HOSTS_GROUP='aruba_6xxx'
HOSTS_GROUP='aos_cx_failed'

echo -e "\n++ Firmware version before updates --\n"
ansible-playbook playbooks/show_version.yaml -l ${HOSTS_GROUP} | tee ${logs_folder}/version_before.logs

ansible-playbook playbooks/update_firmware.yaml -l ${HOSTS_GROUP} | tee ${logs_folder}/update_firmware.logs

#ansible-playbook playbooks/update_firmware_distri_1.yaml | tee ${logs_folder}/update_firmware_distri_1.logs

sleep 30m &&
#ansible-playbook playbooks/update_firmware_distri_2.yaml | tee ${logs_folder}/update_firmware_distri_2.logs

sleep 15m &&
echo -e "\n++ Firmware version after updates --\n"
ansible-playbook playbooks/show_version.yaml | tee ${logs_folder}/version_after.logs