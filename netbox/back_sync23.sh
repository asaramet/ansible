#!/usr/bin/env bash

remote_srv="23:/opt/ansible/inventories/netbox/src"

sync_objs="
devices.yaml
serial_numbers.yaml
"

for file in ${sync_objs}; do
    rsync -uav ${remote_srv}/${file} src/${file}
done