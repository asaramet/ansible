#!/usr/bin/env python3
"""
Get device type
"""

from device_specs import DeviceSpecifications

def check_router_model(hostname: str):
    # The defaults we set earlier make this incredibly clean!
    with DeviceSpecifications() as db:
        device_type = db.get_device_type(hostname)
        
    if device_type:
        print(f"The device '{hostname}' is a {device_type}.")
    else:
        print(f"Device '{hostname}' not found, or it has no type assigned.")

if __name__ == "__main__":
    # Example usage:
    check_router_model("router-01")