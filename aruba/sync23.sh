#!/usr/bin/env bash

remote_srv="23:/opt/ansible/inventories/aruba/"

sync_objs="
playbooks
hosts.ini
"

rsync -uav --delete-excluded ${sync_objs} ${remote_srv}
