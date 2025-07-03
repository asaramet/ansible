#!/usr/bin/env bash

remote_srv="23:/opt/ansible/inventories/netbox"

sync_objs="
src/devices.yaml
serial_numbers.yaml
"

for file in ${sync_objs}; do
    rsync -uav ${remote_srv}/${file} ${file}
done