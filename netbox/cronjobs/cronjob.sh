#!/usr/bin/env bash

# Script to run the cronjob on 23d

echo -e "=== Source Ansible ===\n"
source /opt/ansible/envs
cd /opt/ansible/inventories/netbox
ansible --version

cd cronjobs
./update.sh