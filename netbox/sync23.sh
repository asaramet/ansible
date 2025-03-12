#!/usr/bin/env bash

rsync -uav --delete-excluded pynetbox 23:/opt/ansible/inventories/netbox/