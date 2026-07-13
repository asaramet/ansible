#!/usr/bin/env bash

# Upgrade devices firmware

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

echo -e "=== Source Ansible ===\n"
source /opt/ansible/envs
cd /opt/ansible/inventories/aruba
ansible --version

HOSTS_GROUP='wc_2930f'

echo -e "\n++ Firmware version on ${HOSTS_GROUP} before updates --\n"
ansible-playbook playbooks/show_version_procurve.yaml -l ${HOSTS_GROUP} | tee ${logs_folder}/${HOSTS_GROUP}_version_before.logs

ansible-playbook playbooks/update_firmware_procurve.yaml -l ${HOSTS_GROUP} | tee ${logs_folder}/${HOSTS_GROUP}_update_firmware.logs

sleep 30m &&

echo -e "\n++ Firmware version on ${HOSTS_GROUP} after updates --\n"
ansible-playbook playbooks/show_version.yaml | tee ${logs_folder}/${HOSTS_GROUP}_version_after.logs

HOSTS_GROUP='ya_2530'

echo -e "\n++ Firmware version on ${HOSTS_GROUP} before updates --\n"
ansible-playbook playbooks/show_version_procurve.yaml -l ${HOSTS_GROUP} | tee ${logs_folder}/${HOSTS_GROUP}_version_before.logs

ansible-playbook playbooks/update_firmware_procurve.yaml -l ${HOSTS_GROUP} | tee ${logs_folder}/${HOSTS_GROUP}_update_firmware.logs

sleep 30m &&

echo -e "\n++ Firmware version on ${HOSTS_GROUP} after updates --\n"
ansible-playbook playbooks/show_version.yaml | tee ${logs_folder}/${HOSTS_GROUP}_version_after.logs