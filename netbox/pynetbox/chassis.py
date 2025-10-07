#!/usr/bin/env python3

'''
Process chassis on NetBox platform using `pynetbox` library
Main function, to import:

- chassis(nb_session, data):
    - nb_session - pynetbox API session
    - data - data (yaml format)
'''

import pynetbox, logging

from typing import Dict, List
from pynetbox.core.api import Api as NetBoxApi

from pynetbox_functions import _bulk_create, _bulk_update
from pynetbox_functions import _main, _resolve_tags, _get_device

# Configure logging
logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

def get_chassis(nb_session: NetBoxApi, master_name: str) -> NetBoxApi:
    """
    Find chassis by master device.
    Args:
        nb_session: pynetbox API session
        name: name string, the name of the master device 
    Returns:
        Virtual chassis object or None
    """
    try:
        master_device = nb_session.dcim.devices.get(name = master_name)
        if not master_device: return None
    
        chassis = nb_session.dcim.virtual_chassis.get(master = master_device.id)
        return chassis

    except Exception as e:
        logger.error(f"Error finding chassis for master {master_name}: {e}")
        return None

def chassis(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> List[Dict[str, str | int]]:
    """
    Process chassis on a NetBox server from YAML data.
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'chassis' list
    Returns:
        List of device update payloads or None if no updated needed
    """

    c_chassis = data.get('chassis', None) 
    devices = data.get('devices', None)
    if not c_chassis or not devices: return None

    nb_chassis = nb_session.dcim.virtual_chassis
    nb_devices = nb_session.dcim.devices

    # Cache existing chassis and devices data
    try:
        existing_chassis = {ch.name: ch for ch in nb_chassis.all()}
        chassis_cache = {
            name: {
                'id': ch.id,
                'master': ch.master.id if ch.master else None,
                'master_name': ch.master.name if ch.master else None,
                'master_count': len(ch.members) if hasattr(ch, 'members') else 0,
                'members': [member.id for member in ch.members] if hasattr(ch, 'members') else []
            }
            for name, ch in existing_chassis.items()
        }

        # Cache devices that will be referenced
        device_names = {device.get('name') for device in devices if device.get('name')}
        master_names = {item.get('master') for item in c_chassis if item.get('master')}
        all_device_names = device_names | master_names

        existing_devices = {
            dev.name: dev for dev in nb_devices.filter(name = list(all_device_names))
        }

    except Exception as e:
        logger.error(f"Error caching existing data: {e}")
        return None
    
    # Collect chassis to create
    chassis_to_create = []
    for item in c_chassis:
        c_name = item.get('name', None)
        if not c_name: continue

        if c_name not in existing_chassis:
            master_name = item.get('master')
            master_device = existing_devices.get(master_name) if master_name else None

            if not master_device:
                logging.warning(f"Master device {master_name} not found for chassis {c_name}")
                continue

            payload = {
                'name': c_name,
                'master': master_device.id,
                'tags': _resolve_tags(nb_session, 'stack')
            }
            chassis_to_create.append(payload)

    # Create new chassis in bulk
    new_chassis = []
    if chassis_to_create: 
        try:
            new_chassis = _bulk_create(nb_chassis, chassis_to_create, 'chassis')
            if new_chassis:
                logger.info(f"Successfully created {len(new_chassis)} chassis")

                # Update cache with new chassis
                for ch in new_chassis:
                    logger.info(f"New chassis added: {ch.name}")
                    chassis_cache[ch.name] = {
                        'id': ch.id,
                        'master': ch.master.id if ch.master else None,
                        'master_name': ch.master.name if ch.master else None,
                        'members': []
                    }
        except Exception as e:
            logger.error(f"Failed to crate chassis: {e}")

    # Process device assignments
    devices_to_update = []

    for device in devices:
        d_name = device.get('name')
        d_chassis = device.get('virtual_chassis')

        if not d_name or not d_chassis:
            continue

        # Get device from cache
        d_obj = existing_devices.get(d_name)
        if not d_obj:
            logger.warning(f"Device {d_name} not found in NetBox")
            continue

        # Check if chassis exists in cache
        if d_chassis not in chassis_cache:
            logger.warning(f"Chassis {d_chassis} not found for device {d_name}")
            continue

        chassis_obj = chassis_cache[d_chassis]
        chassis_id = chassis_obj['id']

        # Build update payload 
        update_payload = {'id': d_obj.id}
        device_needs_update = False
        updates_logged = []

        # Check virtual chassis assignment
        current_chassis_id = d_obj.virtual_chassis.id if d_obj.virtual_chassis else None
        if current_chassis_id != chassis_id:
            update_payload['virtual_chassis'] = chassis_id
            device_needs_update = True
            updates_logged.append(f"chassis assignment to {d_chassis}")

        # Check VC position
        d_vc_position = device.get('vc_position')
        if d_vc_position and d_obj.vc_position != d_vc_position:
            update_payload['vc_position'] = d_vc_position
            device_needs_update = True
            updates_logged.append(f"VC position to {d_vc_position}")

        # Check VC priority
        d_vc_priority = device.get('vc_priority')
        if d_vc_priority and d_obj.vc_priority != d_vc_priority:
            update_payload['vc_priority'] = d_vc_priority 
            device_needs_update = True
            updates_logged.append(f"VC priority to {d_vc_priority}")

        if device_needs_update:
            devices_to_update.append(update_payload)
            logger.info(f"Device {d_name} will be updated: {', '.join(updates_logged)}")

    # Bulk update devices 
    if not devices_to_update: 
        logger.info("No chassis needs update")
        return None

    try:
        updated_devices = _bulk_update(nb_devices, devices_to_update, 'switch')
        if updated_devices:
            logger.info(f"Successfully updated {len(updated_devices)} devices with chassis assignments")

    except Exception as e:
        logger.error(f"Error updating devices: {e}")

    return devices_to_update

if __name__ == '__main__':
    _main("Processing chassis data on a NetBox server", chassis)