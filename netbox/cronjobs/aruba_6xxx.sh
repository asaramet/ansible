#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder

#server='development'
server='production'

echo "== Updating Aruba 6xxx Switches of ${server} server - $(date)"
ansible --version

#ansible-playbook playbooks/sync_data.yaml &>> ${logs_folder}/sync_data.logs

ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,${server},location &> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,${server},switches &>> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,${server},lags &>> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,${server},vlans &>> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,${server},ip &>> ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6100,${server},interfaces &>> ${logs_folder}/aruba_6100.logs

ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,${server},location &> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,${server},switches &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,${server},chassis &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,${server},lags &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,${server},vlans &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,${server},ip &>> ${logs_folder}/aruba_6300.logs &&
ansible-playbook playbooks/aruba_6xxx.yaml --tags aruba_6300,${server},interfaces &>> ${logs_folder}/aruba_6300.logs


echo "== Done updating Aruba 6xxx Switches - $(date)"