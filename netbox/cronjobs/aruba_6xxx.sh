#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder

echo "== Updating Aruba 6xxx Switches..."

ansible --version

#ansible-playbook playbooks/sync_data.yaml &>> ${logs_folder}/sync_data.logs

ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,production,location &> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,production,switches &>> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,production,lags &>> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,production,vlans &>> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,production,ip &>> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,production,interfaces &>> ${logs_folder}/aruba_6100.logs

ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,production,location &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,production,switches &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,production,chassis &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,production,lags &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,production,vlans &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,production,ip &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,production,interfaces &>> ${logs_folder}/aruba_6300.logs


echo "== Done updating Aruba 6xxx Switches...