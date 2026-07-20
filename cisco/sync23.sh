#!/usr/bin/env bash

remote_srv="23:/opt/ansible/inventories/cisco/"

sync_objs="
playbooks
hosts.ini
ansible.cfg
cronjobs
"

rsync -uav --delete-excluded ${sync_objs} ${remote_srv}
