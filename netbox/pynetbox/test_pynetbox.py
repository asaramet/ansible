#!/usr/bin/env python3

import pynetbox, requests
from pprint import pprint

# Default server configs
netbox_server = "https://192.168.122.140"
netbox_token = "10aefe29d86af92cf9e14e1f804fb7b08c40cf71"

def netbox_session():
    # start a netbox session
    session = requests.Session()
    session.verify = False # do not verify SSL Certificate

    netbox = pynetbox.api(
        netbox_server,
        token = netbox_token
    )
    netbox.http_session = session
    return netbox

def devices(session):
    # https://<hostname>/dcim/devices/
    devices = session.dcim.devices
    pprint(dict(devices.get(1)))
    #for device in session.dcim.devices.all():
    for device in devices.all():
        #print(device.display)
        print(device.name)
        #pprint(dict(device))

def ip_addresses(session):
    # https://<hostname>/ipam/ip-addresses/
    ip_addresses = session.ipam.ip_addresses
    for address in ip_addresses.all():
        #pprint(dict(address))
        print(address.address)

def main():
    netbox = netbox_session()
    devices(netbox)
    ip_addresses(netbox)

def debug():
    print(netbox_token)

if __name__ == "__main__":
    main()
    #debug()