#!/usr/bin/env python3

'''
Add collected data to NetBox servers using `pynetbox` library
'''

import pynetbox, argparse
from nb import development, production

# Disable warnings about self-signed certificates
from urllib3 import disable_warnings, exceptions
disable_warnings(exceptions.InsecureRequestWarning)

def read_data(nb):
    for device in nb.dcim.devices.all():
        print(f"- {device.name} ({device.device_type.display}) in {device.site.name}")

def main():
    # Initialize NetBox API with custom session
    parser = argparse.ArgumentParser(
        description="Add collected data to a NetBox server"
    )

    parser.add_argument(
        '-s', "--server",
        choices = ["development", "production"],
        default= "development",
        help = "Select which NetBox server to connect to (default: development)"
    )

    args = parser.parse_args()

    if args.server == "development":
        nb = development
    elif args.server == "production":
        nb = production

    nb.http_session.verify = False # Disable SSL verification

    # Run functions
    read_data(nb)

if __name__ == '__main__':
    main()