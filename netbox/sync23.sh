#!/usr/bin/env bash

remote_srv="23:/opt/ansible/inventories/netbox/"

sync_objs="
ansible.cfg
hosts.ini
envs.sh
py*
playbooks
host_vars
group_vars
cronjobs
src
"

rsync -uav --delete-excluded ${sync_objs} ${remote_srv}