#!/usr/bin/env bash

remote_srv="23:/opt/ansible/inventories/aruba"

sync_objs="
playbooks
"

for file in ${sync_objs}; do
    rsync -uav --delete-excluded ${file} ${remote_srv}/
done
