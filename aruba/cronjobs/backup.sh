#!/usr/bin/env bash

# Backup devices running configs

echo -e "=== Source Ansible ===\n"
source /opt/ansible/envs
cd /opt/ansible/inventories/aruba
ansible --version

echo -e "\n=== Collect Aruba OS-CX 'runnig-config' to rhlx99:/tftpboot if updated ===\n"
ansible-playbook playbooks/backup_config.yaml