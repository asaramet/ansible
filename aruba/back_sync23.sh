#!/usr/bin/env bash

remote_srv="23:/opt/ansible/inventories/aruba"

sync_objs="
hosts.ini
"

for file in ${sync_objs}; do
    rsync -uav --delete-excluded ${remote_srv}/${file} ${file}
done

rsync -uav --delete-excluded ${remote_srv}/host_vars .