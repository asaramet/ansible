#!/usr/bin/env bash

# Update netbox switches configs from synct config files

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

cd $EXEC_DIR

ansible-playbook playbooks/sync_data.yaml | tee ${logs_folder}/sync_data.logs &&

python3 pynetbox/yaml_singles.py | tee ${logs_folder}/pynetbox.logs  &&
python3 pynetbox/yaml_stacks.py | tee -a ${logs_folder}/pynetbox.logs  && 
python3 pynetbox/yaml_hpe_modular.py | tee -a ${logs_folder}/pynetbox.logs  &&

python3 pynetbox/yaml_aruba_6xxx.py | tee -a ${logs_folder}/pynetbox.logs &&
#python3 pynetbox/yaml_cisco.py | tee -a ${logs_folder}/pynetbox.logs  &&

ansible-playbook playbooks/backup_sql.yaml | tee ${logs_folder}/backup.logs &&

cd $SCRIPT_DIR
./aruba_8_ports.sh &&
./aruba_12_ports.sh &&
./aruba_48_ports.sh &&

./hpe_8_ports.sh &&
./hpe_48_ports.sh &&

./aruba_stack_2920.sh &&
./aruba_stack_2930.sh &&

./procurve_single.sh &&
./procurve_modular.sh

#./aruba_modular.sh &&
#./aruba_modular_stack.sh &&

./aruba_6xxx.sh