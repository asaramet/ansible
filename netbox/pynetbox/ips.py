#!/usr/bin/env python3

'''
IP Address Management Functions for NetBox

Handles creation of VLAN interfaces and IP address assignment for switches
'''

import logging
from typing import Dict, List, Optional, Tuple, Union

from pynetbox.core.api import Api as NetBoxApi
from pynetbox.core.endpoint import Endpoint

# Import helper functions from pynetbox_functions
from pynetbox_functions import (
    _cache_devices,
    _resolve_or_create,
    _bulk_create,
    _bulk_update,
    _extract_identifier,
    _extract_error_detail
)

logger = logging.getLogger(__name__)

def ips(nb_session: NetBoxApi, data: Dict) -> bool:
    """
    Update switch IPs on a NetBox server from YAML data.
    
    This function:
    1. Creates VLAN interfaces for loopback IPs if they don't exist
    2. Creates IP addresses if they don't exist
    3. Assigns IPs to the interfaces
    4. Sets primary_ip4 on devices
    
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'ip_addresses' list with structure:
              - hostname: device hostname
              - ip: IP address with CIDR (e.g., 192.168.104.16/23)
              - name: interface name (e.g., "vlan 201")
              - vlan: boolean indicating if this is a VLAN interface
              - vlan_id: VLAN ID (optional)
              - vlan_name: VLAN name (optional)
    
    Returns:
        True if successful, False if errors occurred
    """
    if not data or 'ip_addresses' not in data:
        logger.warning("No 'ip_addresses' found in data")
        return False
    
    ip_data_list = data['ip_addresses']
    if not ip_data_list:
        logger.info("No IP addresses to process")
        return True
    
    logger.info(f"Processing {len(ip_data_list)} IP address entries")
    
    # Step 1: Extract all hostnames and cache devices
    hostnames = list(set([entry['hostname'] for entry in ip_data_list]))
    logger.info(f"Caching {len(hostnames)} unique devices")
    device_cache = _cache_devices(nb_session, hostnames)
    
    if not device_cache:
        logger.error("No devices found in NetBox")
        return False
    
    logger.info(f"Found {len(device_cache)} devices in NetBox")
    
    # Step 2: Resolve tenant and role
    tenant_id = _resolve_tenant(nb_session, "netzadmin")
    role_id = _resolve_ip_role(nb_session, "Loopback")
    
    if not tenant_id:
        logger.warning("Could not resolve tenant 'netzadmin', proceeding without tenant")
    if not role_id:
        logger.warning("Could not resolve role 'Loopback', proceeding without role")
    else:
        # Log what type of role value we got
        if isinstance(role_id, int):
            logger.info(f"Using role ID: {role_id}")
        else:
            logger.info(f"Using role as choice field: '{role_id}'")
    
    # Step 3: Prepare data structures for batch operations
    interface_specs, ip_specs = _prepare_interface_and_ip_data(
        nb_session, ip_data_list, device_cache, tenant_id, role_id
    )
    
    # Step 4: Ensure interfaces exist
    interface_map = _ensure_vlan_interfaces(nb_session, interface_specs, device_cache)
    
    if not interface_map:
        logger.error("Failed to create/retrieve interfaces")
        return False
    
    # Step 5: Ensure IP addresses exist and are assigned
    success = _process_ip_addresses(nb_session, ip_specs, interface_map)
    
    # Step 6: Set primary IPs on devices
    _set_primary_ips_on_devices(nb_session, ip_data_list, device_cache)
    
    return success


def _resolve_tenant(nb_session: NetBoxApi, tenant_name: str) -> Optional[int]:
    """
    Resolve tenant name to tenant ID.
    Tries multiple lookup methods: exact name, slug, case-insensitive.
    
    Args:
        nb_session: pynetbox API session
        tenant_name: Name of the tenant
    
    Returns:
        Tenant ID or None if not found
    """
    try:
        # Try 1: Exact name match
        tenant = nb_session.tenancy.tenants.get(name=tenant_name)
        if tenant:
            logger.debug(f"Resolved tenant '{tenant_name}' by name to ID {tenant.id}")
            return tenant.id
        
        # Try 2: Slug match (lowercase, normalized)
        tenant_slug = tenant_name.lower().replace(' ', '-').replace('_', '-')
        tenant = nb_session.tenancy.tenants.get(slug=tenant_slug)
        if tenant:
            logger.debug(f"Resolved tenant '{tenant_name}' by slug '{tenant_slug}' to ID {tenant.id}")
            return tenant.id
        
        # Try 3: Case-insensitive search using filter
        results = nb_session.tenancy.tenants.filter(name__ic=tenant_name)
        if results:
            tenant = results[0]
            logger.debug(f"Resolved tenant '{tenant_name}' by case-insensitive search to ID {tenant.id}")
            return tenant.id
        
        logger.warning(f"Tenant '{tenant_name}' not found in NetBox (tried name, slug, case-insensitive)")
        return None
        
    except Exception as e:
        logger.error(f"Error resolving tenant '{tenant_name}': {e}", exc_info=True)
        return None


def _resolve_ip_role(nb_session: NetBoxApi, role_name: str) -> Optional[int | str]:
    """
    Resolve IP address role name to role ID or role string.
    
    NetBox can store roles in two ways:
    1. As separate objects (ipam.roles) - returns ID
    2. As choice fields (string values) - returns string
    
    Tries multiple lookup methods: exact name, slug, case-insensitive.
    Falls back to returning the role name as a string if no endpoint exists.
    
    Args:
        nb_session: pynetbox API session
        role_name: Name of the IP address role
    
    Returns:
        Role ID (int) if roles are objects, or role name (str) if choice field,
        or None if not found
    """
    if not role_name:
        return None
    
    # Check if ipam.roles endpoint exists
    try:
        roles_endpoint = nb_session.ipam.roles
        
        # Try 1: Exact name match
        try:
            role = roles_endpoint.get(name=role_name)
            if role:
                logger.debug(f"Resolved role '{role_name}' by name to ID {role.id}")
                return role.id
        except Exception:
            pass
        
        # Try 2: Slug match (lowercase, normalized)
        role_slug = role_name.lower().replace(' ', '-').replace('_', '-')
        try:
            role = roles_endpoint.get(slug=role_slug)
            if role:
                logger.debug(f"Resolved role '{role_name}' by slug '{role_slug}' to ID {role.id}")
                return role.id
        except Exception:
            pass
        
        # Try 3: Case-insensitive search using filter
        try:
            results = roles_endpoint.filter(name__ic=role_name)
            if results:
                role = results[0]
                logger.debug(f"Resolved role '{role_name}' by case-insensitive search to ID {role.id}")
                return role.id
        except Exception:
            pass
        
        logger.warning(
            f"IP address role '{role_name}' not found in ipam.roles "
            f"(tried name, slug, case-insensitive)"
        )
        
    except AttributeError:
        # ipam.roles endpoint doesn't exist - role is likely a choice field
        logger.info(
            f"ipam.roles endpoint not found - treating role '{role_name}' as choice field (string value)"
        )
        # Return the role name as-is (likely lowercase based on URL)
        return role_name.lower()
    except Exception as e:
        logger.warning(f"Error accessing ipam.roles endpoint: {e}")
    
    # If we get here and still haven't found it, return the lowercase version
    # as it's likely a choice field value
    logger.info(f"Returning role '{role_name}' as string value (choice field)")
    return role_name.lower()


def _prepare_interface_and_ip_data(
    nb_session: NetBoxApi,
    ip_data_list: List[Dict],
    device_cache: Dict[str, object],
    tenant_id: Optional[int],
    role_id: Optional[Union[int, str]]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Prepare interface specifications and IP specifications from YAML data.
    
    Args:
        nb_session: pynetbox API session
        ip_data_list: List of IP address entries from YAML
        device_cache: Dictionary of cached device objects
        tenant_id: Tenant ID for IP addresses
        role_id: Role ID (int) or role name (str) for IP addresses.
                 Can be int if roles are objects, str if roles are choice fields.
    
    Returns:
        Tuple of (interface_specs, ip_specs)
    """
    interface_specs = []
    ip_specs = []
    
    for entry in ip_data_list:
        hostname = entry.get('hostname')
        ip_address = entry.get('ip')
        interface_name = entry.get('name')
        vlan_id = entry.get('vlan_id')
        
        if not hostname or not ip_address or not interface_name:
            logger.warning(f"Skipping incomplete entry: {entry}")
            continue
        
        # Check if device exists in cache
        device = device_cache.get(hostname)
        if not device:
            logger.warning(f"Device '{hostname}' not found in cache, skipping")
            continue
        
        # Prepare interface spec
        interface_spec = {
            'device': device,
            'name': interface_name,
            'type': 'virtual',  # VLAN interfaces are virtual
            'hostname': hostname,  # For logging
        }
        interface_specs.append(interface_spec)
        
        # Prepare IP address spec
        ip_spec = {
            'address': ip_address,
            'hostname': hostname,
            'interface_name': interface_name,
            'tenant': tenant_id,
            'role': role_id,
            'status': 'active',
            'vlan_id': vlan_id,
        }
        ip_specs.append(ip_spec)
    
    logger.info(f"Prepared {len(interface_specs)} interface specs and {len(ip_specs)} IP specs")
    return interface_specs, ip_specs


def _ensure_vlan_interfaces(
    nb_session: NetBoxApi,
    interface_specs: List[Dict],
    device_cache: Dict[str, object]
) -> Dict[Tuple[str, str], object]:
    """
    Ensure VLAN interfaces exist, creating them if necessary.
    
    Args:
        nb_session: pynetbox API session
        interface_specs: List of interface specifications
        device_cache: Dictionary of cached device objects
    
    Returns:
        Dictionary mapping (hostname, interface_name) to interface object
    """
    interface_map = {}
    interfaces_to_create = []
    
    logger.info("Checking for existing interfaces...")
    
    # Check which interfaces already exist
    for spec in interface_specs:
        device = spec['device']
        interface_name = spec['name']
        hostname = spec['hostname']
        
        try:
            # Query for existing interface
            existing_interface = nb_session.dcim.interfaces.get(
                device_id=device.id,
                name=interface_name
            )
            
            if existing_interface:
                logger.debug(f"Interface '{interface_name}' already exists on {hostname}")
                interface_map[(hostname, interface_name)] = existing_interface
            else:
                # Interface doesn't exist, prepare for creation
                interfaces_to_create.append(spec)
                
        except Exception as e:
            logger.error(
                f"Error checking interface '{interface_name}' on {hostname}: {e}",
                exc_info=True
            )
    
    # Create missing interfaces
    if interfaces_to_create:
        logger.info(f"Creating {len(interfaces_to_create)} missing interfaces")
        created_interfaces = _create_interfaces(nb_session, interfaces_to_create)
        
        # Add created interfaces to the map
        for interface in created_interfaces:
            # Find the corresponding spec to get hostname
            for spec in interfaces_to_create:
                if spec['device'].id == interface.device.id and spec['name'] == interface.name:
                    hostname = spec['hostname']
                    interface_map[(hostname, interface.name)] = interface
                    break
    else:
        logger.info("All interfaces already exist")
    
    return interface_map


def _create_interfaces(
    nb_session: NetBoxApi,
    interface_specs: List[Dict]
) -> List[object]:
    """
    Create interfaces in bulk.
    
    Args:
        nb_session: pynetbox API session
        interface_specs: List of interface specifications
    
    Returns:
        List of created interface objects
    """
    # Prepare payloads for bulk creation
    payloads = []
    for spec in interface_specs:
        payload = {
            'device': spec['device'].id,
            'name': spec['name'],
            'type': spec['type'],
        }
        payloads.append(payload)
    
    # Use the bulk create helper function
    created = _bulk_create(nb_session.dcim.interfaces, payloads, "interface")
    
    return created


def _process_ip_addresses(
    nb_session: NetBoxApi,
    ip_specs: List[Dict],
    interface_map: Dict[Tuple[str, str], object]
) -> bool:
    """
    Process IP addresses: create if missing, assign to interfaces, handle updates.
    
    Args:
        nb_session: pynetbox API session
        ip_specs: List of IP address specifications
        interface_map: Dictionary mapping (hostname, interface_name) to interface object
    
    Returns:
        True if successful, False if errors occurred
    """
    logger.info("Processing IP addresses...")
    
    # Collect all IP addresses to check
    ip_addresses_to_check = [spec['address'] for spec in ip_specs]
    
    # Query existing IP addresses
    existing_ips = _get_existing_ip_addresses(nb_session, ip_addresses_to_check)
    
    # Separate into create and update lists
    ips_to_create = []
    ips_to_update = []
    
    for spec in ip_specs:
        ip_address = spec['address']
        hostname = spec['hostname']
        interface_name = spec['interface_name']
        
        # Get the interface object
        interface_key = (hostname, interface_name)
        interface = interface_map.get(interface_key)
        
        if not interface:
            logger.warning(
                f"Interface '{interface_name}' on '{hostname}' not found in map, "
                f"skipping IP {ip_address}"
            )
            continue
        
        # Check if IP already exists
        existing_ip = existing_ips.get(ip_address)
        
        if existing_ip:
            # IP exists, check if it needs updating
            needs_update = False
            update_payload = {'id': existing_ip.id}
            
            # Check if assigned to correct interface
            if not existing_ip.assigned_object or existing_ip.assigned_object_id != interface.id:
                update_payload['assigned_object_type'] = 'dcim.interface'
                update_payload['assigned_object_id'] = interface.id
                needs_update = True
            
            # Check tenant
            if spec['tenant']:
                current_tenant_id = existing_ip.tenant.id if existing_ip.tenant else None
                if current_tenant_id != spec['tenant']:
                    update_payload['tenant'] = spec['tenant']
                    needs_update = True
            
            # Check role
            if spec['role']:
                current_role = existing_ip.role

                # Normalize current role for comparison
                if current_role:
                    # If role is an object with id attribute, get the id
                    if hasattr(current_role, 'id'):
                        current_role_value = current_role.id
                    # If role is a string or has a value attribute, use it directly
                    elif hasattr(current_role, 'value'):
                        current_role_value = current_role.value
                    else:
                        # It's a plain string
                        current_role_value = str(current_role)
                else:
                    current_role_value = None

                # Compare normalized values
                if current_role_value != spec['role']:
                    update_payload['role'] = spec['role']
                    needs_update = True
            
            # Check status
            if existing_ip.status != spec['status']:
                update_payload['status'] = spec['status']
                needs_update = True
            
            if needs_update:
                ips_to_update.append(update_payload)
                logger.debug(f"IP {ip_address} needs update")
            else:
                logger.debug(f"IP {ip_address} is already correctly configured")
        else:
            # IP doesn't exist, create it
            create_payload = {
                'address': ip_address,
                'status': spec['status'],
                'assigned_object_type': 'dcim.interface',
                'assigned_object_id': interface.id,
            }
            
            if spec['tenant']:
                create_payload['tenant'] = spec['tenant']
            if spec['role']:
                create_payload['role'] = spec['role']
            
            ips_to_create.append(create_payload)
    
    # Execute bulk operations
    success = True
    
    if ips_to_create:
        logger.info(f"Creating {len(ips_to_create)} new IP addresses")
        created = _bulk_create(nb_session.ipam.ip_addresses, ips_to_create, "IP address")
        if len(created) < len(ips_to_create):
            logger.warning(f"Only created {len(created)}/{len(ips_to_create)} IP addresses")
            success = False
    else:
        logger.info("No new IP addresses to create")
    
    if ips_to_update:
        logger.info(f"Updating {len(ips_to_update)} existing IP addresses")
        updated = _bulk_update(nb_session.ipam.ip_addresses, ips_to_update, "IP address")
        if len(updated) < len(ips_to_update):
            logger.warning(f"Only updated {len(updated)}/{len(ips_to_update)} IP addresses")
            success = False
    else:
        logger.info("No IP addresses need updates")
    
    return success


def _get_existing_ip_addresses(
    nb_session: NetBoxApi,
    ip_addresses: List[str]
) -> Dict[str, object]:
    """
    Get existing IP addresses from NetBox.
    
    Args:
        nb_session: pynetbox API session
        ip_addresses: List of IP addresses to query (with CIDR)
    
    Returns:
        Dictionary mapping IP address to IP object
    """
    existing_ips = {}
    
    try:
        # Query all IP addresses at once
        # NetBox requires addresses to be queried individually or in batches
        # We'll chunk them for efficiency
        chunk_size = 500
        
        for i in range(0, len(ip_addresses), chunk_size):
            chunk = ip_addresses[i:i + chunk_size]
            
            # Query using the 'address' filter
            results = nb_session.ipam.ip_addresses.filter(address=chunk)
            
            for ip_obj in results:
                existing_ips[str(ip_obj.address)] = ip_obj
        
        logger.debug(f"Found {len(existing_ips)} existing IP addresses")
        
    except Exception as e:
        logger.error(f"Error querying existing IP addresses: {e}", exc_info=True)
    
    return existing_ips


def _set_primary_ips_on_devices(
    nb_session: NetBoxApi,
    ip_data_list: List[Dict],
    device_cache: Dict[str, object]
) -> None:
    """
    Set primary_ip4 on devices based on IP assignments.
    
    Args:
        nb_session: pynetbox API session
        ip_data_list: List of IP address entries from YAML
        device_cache: Dictionary of cached device objects
    """
    logger.info("Setting primary IPs on devices...")
    
    # Group IPs by hostname
    device_ips = {}
    for entry in ip_data_list:
        hostname = entry.get('hostname')
        ip_address = entry.get('ip')
        
        if hostname and ip_address:
            if hostname not in device_ips:
                device_ips[hostname] = []
            device_ips[hostname].append(ip_address)
    
    # Prepare device updates
    updates_needed = []
    
    for hostname, ip_list in device_ips.items():
        device = device_cache.get(hostname)
        if not device:
            logger.warning(f"Device '{hostname}' not in cache, skipping primary IP update")
            continue
        
        # Use the first IP as primary (you may want different logic)
        primary_ip = ip_list[0]
        
        try:
            # Get the IP address object
            ip_obj = nb_session.ipam.ip_addresses.get(address=primary_ip)
            
            if not ip_obj:
                logger.warning(f"IP {primary_ip} not found, skipping primary IP for {hostname}")
                continue
            
            # Check if update is needed
            current_primary = device.primary_ip4.id if device.primary_ip4 else None
            
            if current_primary != ip_obj.id:
                updates_needed.append({
                    'id': device.id,
                    'primary_ip4': ip_obj.id
                })
                logger.debug(f"Will set primary IP for {hostname} to {primary_ip}")
            else:
                logger.debug(f"Primary IP for {hostname} already set to {primary_ip}")
                
        except Exception as e:
            logger.error(
                f"Error preparing primary IP update for {hostname}: {e}",
                exc_info=True
            )
    
    # Execute bulk updates
    if updates_needed:
        logger.info(f"Updating primary IPs for {len(updates_needed)} devices")
        updated = _bulk_update(nb_session.dcim.devices, updates_needed, "device primary IP")
        logger.info(f"Updated primary IPs for {len(updated)} devices")
    else:
        logger.info("No device primary IP updates needed")

if __name__ == '__main__':
    from pynetbox_functions import _main
    _main("Update devices IPs in NetBox", ips)