#!/usr/bin/env bash

# Update netbox switches configs from synct config files

SCRIPT_DIR="$(dirname $(realpath $0))"
EXEC_DIR="$(dirname ${SCRIPT_DIR})"

logs_folder="${SCRIPT_DIR}/logs"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

server='production'
#server='development'

cd $EXEC_DIR

python3 sql_scripts/backup_database.py backup
python3 sql_scripts/netbox_to_db_sync.py sync --dry-run --server production
python3 sql_scripts/netbox_to_db_sync.py sync --server production

ansible-playbook playbooks/0.new_sync.yaml | tee ${logs_folder}/sync_data.logs &&
python3 pyyaml/sort_data.py | tee ${logs_folder}/sync_data.logs  &&

python3 pyyaml/aruba/yamerate.py | tee ${logs_folder}/pynetbox.logs  &&
python3 pyyaml/cisco/yamerate.py | tee -a ${logs_folder}/pynetbox.logs  &&

ansible-playbook playbooks/backup_sql.yaml | tee ${logs_folder}/backup.logs &&

python3 pynetbox/update_data.py -s ${server}

echo "== Updates finished - $(date)"
