#!/usr/bin/env bash

# Upgrade devices firmware

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

echo -e "=== Source Ansible ===\n"
source /opt/ansible/envs
cd /opt/ansible/inventories/aruba
ansible --version

#HOSTS_GROUPS='wc_2930f ya_2530 yb_2530 yc_2540 wc_2930f wc_2930m'
#HOSTS_GROUPS='procurve_distri'
HOSTS_GROUPS='procurve_reboot'

for i in ${HOSTS_GROUPS}; do

echo -e "\n++ Firmware version on ${i} before updates --\n"
ansible-playbook playbooks/show_version.yaml -l ${i} | tee ${logs_folder}/${i}_version_before.logs

ansible-playbook playbooks/update_procurve.yaml -l ${i} | tee ${logs_folder}/${i}_update.logs
ansible-playbook playbooks/reboot_procurve.yaml -l ${i} | tee ${logs_folder}/${i}_reboot.logs

sleep 10m &&

echo -e "\n++ Firmware version on ${i} after updates --\n"
ansible-playbook playbooks/show_version.yaml -l ${i} | tee ${logs_folder}/${i}_version_after.logs

done