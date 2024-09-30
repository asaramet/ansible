#!/usr/bin/env bash

# Update netbox switches configs from synct config files

cd `dirname $0`
this_folder=$PWD

exec_folder="${this_folder}/.."
logs_folder=${this_folder}/logs

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $exec_folder
ansible --version

#ansible-playbook playbooks/sync_data.yaml | tee ${logs_folder}/sync_data.logs

ansible-playbook playbooks/aruba_6100.yaml --tags aruba_6100,production,location | tee ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6100.yaml --tags aruba_6100,production,switches | tee ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6100.yaml --tags aruba_6100,production,lags | tee ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6100.yaml --tags aruba_6100,production,vlans | tee ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6100.yaml --tags aruba_6100,production,ip | tee ${logs_folder}/aruba_6100.logs &&
ansible-playbook playbooks/aruba_6100.yaml --tags aruba_6100,production,interfaces | tee ${logs_folder}/aruba_6100.logs