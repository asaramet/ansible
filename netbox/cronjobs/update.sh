#!/usr/bin/env bash

# Update netbox switches configs from synct config files

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

tags=(
    aruba_8 
    aruba_12
    aruba_48

    hpe_8
    hpe_48

    procurve_modular
    procurve_single

    aruba_stack
    aruba_stack_2920
    aruba_stack_2930

    #aruba_modular
    #aruba_modular_stack

    aruba_6100
    aruba_6300
)

server='production'

cd $EXEC_DIR

ansible-playbook playbooks/sync_data.yaml | tee ${logs_folder}/sync_data.logs &&

python3 pynetbox/yaml_aruba.py | tee ${logs_folder}/pynetbox.logs  &&
python3 pynetbox/yaml_aruba_os_cx.py | tee -a ${logs_folder}/pynetbox.logs &&
#python3 pynetbox/yaml_cisco.py | tee -a ${logs_folder}/pynetbox.logs  &&

ansible-playbook playbooks/backup_sql.yaml | tee ${logs_folder}/backup.logs &&

for i in ${tags[@]}; do
    echo "== Updating ${i} - $(date)" &&
    ansible-playbook playbooks/aruba.yaml --tags ${i},${server},update &> ${logs_folder}/${i}.logs ;
    echo "== Done updating ${i} - $(date)"
done

echo "== Updates finished - $(date)"
