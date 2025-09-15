#!/usr/bin/env python3

'''
Specific pynetbox functions
'''

import pynetbox, yaml
from pathlib import Path

def read_data(nb):
    for device in nb.dcim.devices.all():
        print(f"- {device.name} ({device.device_type.display}) in {device.site.name}")

def load_yaml(file_path):
    yaml_file = Path(file_path)

    with yaml_file.open('r') as f:
        return yaml.safe_load(f)

# --- bulk create with fallback to per-item create ---
def _bulk_create_with_fallback(endpoint, payloads, kind):
    if not payloads: return []

    created = []

    try:
        # pynetbox accepts a list as the first argument to create()
        created = endpoint.create(payloads)
        print(f"|+ Bulk-created {len(created)} {kind}(s).")
        return created
    except Exception as exc:
        print(f"|- Bulk create for {kind} failed ({exc}), falling back to per-item create.")
        created = []
        for payload in payloads:
            try: 
                obj = endpoint.create(payload)
                created.append(obj)
            except Exception as exc2:
                print(f"|- ERROR: Failed to create {kind} {payload.get('name')}: {exc2}")
        return created
