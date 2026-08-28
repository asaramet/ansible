#!/usr/bin/env python3

'''
IP Address Management Functions for NetBox

Handles creation of VLAN interfaces and IP address assignment for switches
'''

import logging
import concurrent.futures
from typing import Optional, Tuple, Union, Any

from pynetbox.core.api import Api as NetBoxApi
from pynetbox.core.endpoint import Endpoint


# Import helper functions from pynetbox_functions
from pynetbox_functions import (
    _cache_devices,
    _resolve_or_create,
    _bulk_create,
    _bulk_update,
    _delete_netbox_obj,
    _extract_identifier,
    _extract_error_detail,
    _fetch_netbox_objects
)

logger = logging.getLogger(__name__)

def ips(nb_session: NetBoxApi, data: dict) -> bool:
    """
    Update switch IPs on a NetBox server from YAML data.
    
    This function:
    1. Creates VLAN interfaces for loopback IPs if they don't exist
    2. Creates IP addresses if they don't exist
    3. Assigns IPs to the interfaces
    4. Sets primary_ip4 on devices
    
    Args:
        nb_session: pynetbox API session
        data: dictionary containing 'ip_addresses' list with structure:
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


def _resolve_ip_role(nb_session: NetBoxApi, role_name: str) -> Optional:
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
    ip_data_list: list[dict],
    device_cache: dict[str, object],
    tenant_id: Optional[int],
    role_id: Optional[Union[int, str]]
) -> Tuple[list[dict], list[dict]]:
    """
    Prepare interface specifications and IP specifications from YAML data.
    
    Args:
        nb_session: pynetbox API session
        ip_data_list: list of IP address entries from YAML
        device_cache: dictionary of cached device objects
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
        status = entry.get('status')
        
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
            'status': status,
            'vlan_id': vlan_id,
        }
        ip_specs.append(ip_spec)
    
    logger.info(f"Prepared {len(interface_specs)} interface specs and {len(ip_specs)} IP specs")
    return interface_specs, ip_specs


def _ensure_vlan_interfaces(
    nb_session: NetBoxApi,
    interface_specs: list[dict],
    device_cache: dict[str, object]
) -> dict[Tuple[str, str], object]:
    """
    Ensure VLAN interfaces exist, creating them if necessary.
    
    Args:
        nb_session: pynetbox API session
        interface_specs: list of interface specifications
        device_cache: dictionary of cached device objects
    
    Returns:
        dictionary mapping (hostname, interface_name) to interface object
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
    interface_specs: list[dict]
) -> list[object]:
    """
    Create interfaces in bulk.
    
    Args:
        nb_session: pynetbox API session
        interface_specs: list of interface specifications
    
    Returns:
        list of created interface objects
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


def _should_reassign_ip(
    nb_session: NetBoxApi,
    ip_address: str,
    current_interface_id: int,
    target_interface_id: int,
    target_device_name: str
) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Determine if an IP should be reassigned based on device statuses.
    
    Args:
        nb_session: pynetbox API session
        ip_address: IP address being checked
        current_interface_id: Current interface ID where IP is assigned
        target_interface_id: Target interface ID from YAML
        target_device_name: Target device name from YAML
    
    Returns:
        Tuple of (should_reassign, reason, old_device_info)
        - should_reassign: True if reassignment should proceed
        - reason: String explaining the decision (for logging)
        - old_device_info: dict with old device details for audit trail, or None
    """
    try:
        # Get current (old) interface and device
        old_interface = nb_session.dcim.interfaces.get(current_interface_id)
        if not old_interface or not old_interface.device:
            return True, "Current device not found", None
        
        old_device = nb_session.dcim.devices.get(old_interface.device.id)
        
        # Get target (new) device from interface
        target_interface = nb_session.dcim.interfaces.get(target_interface_id)
        if not target_interface or not target_interface.device:
            return False, "Target device not found", None
        
        target_device = nb_session.dcim.devices.get(target_interface.device.id)
        
        # Extract statuses
        old_status = old_device.status.value if hasattr(old_device.status, 'value') else str(old_device.status)
        target_status = target_device.status.value if hasattr(target_device.status, 'value') else str(target_device.status)
        
        old_is_active = old_status.lower() == 'active'
        target_is_active = target_status.lower() == 'active'
        
        old_device_info = {
            'name': old_device.name,
            'interface': old_interface.name,
            'status': old_status,
            'device_obj': old_device
        }
        
        # Decision logic
        if old_is_active and target_is_active:
            return False, (
                f"CONFLICT - Both devices ACTIVE: "
                f"'{old_device.name}' and '{target_device.name}'. "
                f"Decommission one device first."
            ), old_device_info
        
        if old_is_active and not target_is_active:
            return False, (
                f"IP staying on ACTIVE device '{old_device.name}' ({old_status}). "
                f"Target '{target_device.name}' is NOT active ({target_status})."
            ), old_device_info
        
        if target_is_active and not old_is_active:
            return True, (
                f"Moving to ACTIVE device '{target_device.name}' ({target_status}). "
                f"Current '{old_device.name}' is NOT active ({old_status})."
            ), old_device_info
        
        # Both inactive
        return True, (
            f"Both devices NOT active. "
            f"'{old_device.name}' ({old_status}), '{target_device.name}' ({target_status}). "
            f"Following YAML."
        ), old_device_info
        
    except Exception as e:
        logger.error(f"Error checking devices for IP {ip_address}: {e}", exc_info=True)
        return False, f"Error checking devices: {e}", None


def _clear_primary_ip_if_needed(device_obj: object, ip_id: int) -> bool:
    """
    Clear primary IP from device if the IP matches.
    
    Args:
        device_obj: Device object
        ip_id: IP address ID to check
    
    Returns:
        True if successfully cleared or not needed, False if failed
    """
    try:
        is_primary_ipv4 = device_obj.primary_ip4 and device_obj.primary_ip4.id == ip_id
        is_primary_ipv6 = device_obj.primary_ip6 and device_obj.primary_ip6.id == ip_id
        
        if not (is_primary_ipv4 or is_primary_ipv6):
            return True  # Not primary, nothing to clear
        
        logger.info(f"Clearing primary IP assignment from {device_obj.name}")
        
        if is_primary_ipv4:
            device_obj.primary_ip4 = None
        if is_primary_ipv6:
            device_obj.primary_ip6 = None
        
        device_obj.save()
        logger.debug(f"Primary IP cleared from {device_obj.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to clear primary IP from {device_obj.name}: {e}", exc_info=True)
        return False


def _process_existing_ip(
    nb_session: NetBoxApi,
    existing_ip: object,
    spec: dict,
    interface: object,
    interface_map: dict
) -> Optional[dict]:
    """
    Process an existing IP address and determine if it needs updating.
    
    Args:
        nb_session: pynetbox API session
        existing_ip: Existing IP object from NetBox
        spec: IP specification from YAML
        interface: Target interface object
        interface_map: Map of interfaces
    
    Returns:
        Update payload dict if update needed, None otherwise
    """
    ip_address = spec['address']
    hostname = spec['hostname']
    status = spec['status']
    update_payload = {'id': existing_ip.id}
    needs_update = False
    
    # Check interface assignment
    current_interface_id = existing_ip.assigned_object_id if existing_ip.assigned_object else None
    
    if current_interface_id and current_interface_id != interface.id:
        # IP on different interface - check reassignment
        should_reassign, reason, old_device_info = _should_reassign_ip(
            nb_session,
            ip_address,
            current_interface_id,
            interface.id,
            hostname
        )
        
        if not should_reassign:
            if "CONFLICT" in reason:
                logger.error(f"IP {ip_address}: {reason}")
            else:
                logger.info(f"IP {ip_address}: {reason}")
            return None  # Skip this IP
        
        logger.info(f"IP {ip_address}: {reason}")
        
        # Clear primary IP from old device
        if old_device_info and old_device_info['device_obj']:
            if not _clear_primary_ip_if_needed(old_device_info['device_obj'], existing_ip.id):
                logger.error(f"Cannot reassign IP {ip_address} - failed to clear primary IP")
                return None
        
        # Add audit trail
        if old_device_info:
            update_payload['description'] = _build_audit_trail(
                existing_ip.description or "",
                old_device_info
            )
        
        # Set reassignment
        update_payload['assigned_object_type'] = 'dcim.interface'
        update_payload['assigned_object_id'] = interface.id
        needs_update = True
    
    elif not current_interface_id:
        # IP not assigned - assign it
        update_payload['assigned_object_type'] = 'dcim.interface'
        update_payload['assigned_object_id'] = interface.id
        needs_update = True
    
    # Check other attributes
    if _compare_ip_attributes(existing_ip, spec, update_payload):
        needs_update = True
    
    if needs_update:
        logger.debug(f"IP {ip_address} needs update")
        return update_payload
    else:
        logger.debug(f"IP {ip_address} already correctly configured")
        return None


def _create_new_ip(spec: dict, interface: object) -> dict:
    """
    Create payload for a new IP address.
    
    Args:
        spec: IP specification from YAML
        interface: Target interface object
    
    Returns:
        Create payload dict
    """
    payload = {
        'address': spec['address'],
        'status': spec['status'],
        'assigned_object_type': 'dcim.interface',
        'assigned_object_id': interface.id,
    }
    
    if spec['tenant']:
        payload['tenant'] = spec['tenant']
    if spec['role']:
        payload['role'] = spec['role']
    
    return payload

def _compare_ip_attributes(
    existing_ip: object,
    spec: dict,
    update_payload: dict
) -> bool:
    """
    Compare IP attributes and add updates to payload if needed.
    """
    needs_update = False
    
    # --- 1. TENANT (Relational Field) ---
    # If spec['tenant'] is a string name/slug, this will STILL FAIL when sent to the API.
    if 'tenant' in spec and spec['tenant']:
        current_tenant_id = existing_ip.tenant.id if existing_ip.tenant else None
        
        # Coerce to int for a safe comparison, assuming spec['tenant'] is numeric
        try:
            target_tenant_id = int(spec['tenant'])
            if current_tenant_id != target_tenant_id:
                update_payload['tenant'] = target_tenant_id
                needs_update = True
        except ValueError:
            logger.error(f"Tenant in spec must be an integer ID, got: {spec['tenant']}")
            
    # --- 2. ROLE (Choice Field) ---
    if 'role' in spec and spec['role']:
        current_role = existing_ip.role.value if existing_ip.role else None
        
        # Force both to lowercase strings for safe comparison
        target_role = str(spec['role']).lower()
        current_role_str = str(current_role).lower() if current_role else None
        
        if current_role_str != target_role:
            update_payload['role'] = target_role
            needs_update = True
            
    # --- 3. STATUS (Choice Field) ---
    if 'status' in spec and spec['status']:
        current_status = existing_ip.status.value if existing_ip.status else None
        
        target_status = str(spec['status']).lower()
        current_status_str = str(current_status).lower() if current_status else None
        
        if current_status_str != target_status:
            logger.info(
                f"{spec['address']} needs to update status: "
                f"{current_status_str} to {target_status}"
            )
            update_payload['status'] = target_status
            needs_update = True
    
    return needs_update

def _build_audit_trail(existing_description: str, old_device_info: dict) -> str:
    """
    Build audit trail for IP reassignment.
    
    Args:
        existing_description: Current IP description
        old_device_info: dict with old device details
    
    Returns:
        Updated description with audit trail
    """
    from datetime import datetime
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    audit_note = (
        f"Previously: {old_device_info['name']} ({old_device_info['interface']}, "
        f"status: {old_device_info['status']}) until {current_date}"
    )
    
#    if existing_description:
#        return f"{existing_description}\n{audit_note}"
    return audit_note

from collections import defaultdict
from typing import Tuple, Any
import logging

logger = logging.getLogger(__name__)

def _process_ip_addresses(
    nb_session: Any,
    ip_specs: list[dict],
    interface_map: dict[Tuple[str, str], object]
) -> bool:
    """
    Process IP addresses: clean up conflicts, create if missing, handle updates.
    """
    logger.info("Processing IP addresses...")
    
    # 1. Group specs by IP address to find duplicates in the source YAML/dict
    specs_by_ip = defaultdict(list)
    for spec in ip_specs:
        specs_by_ip[spec['address']].append(spec)

    filtered_specs = []
    ips_to_hard_reset = set()

    # 2. Identify conflicts (same IP, one active, one deprecated)
    for ip, specs in specs_by_ip.items():
        if len(specs) > 1:
            statuses = [str(s.get('status', '')).lower() for s in specs]
            if 'deprecated' in statuses and 'active' in statuses:
                logger.info(f"Conflict found for {ip}: moving from deprecated device to active. Flagging for hard reset.")
                ips_to_hard_reset.add(ip)
                # Keep ONLY the active spec(s) going forward do not try to create the deprecated one
                filtered_specs.extend([s for s in specs if str(s.get('status', '')).lower() != 'deprecated'])
            else:
                filtered_specs.extend(specs)
        else:
            filtered_specs.extend(specs)
            
    # Replace the original list with the cleaned up list
    ip_specs = filtered_specs

    # 3. Query existing IP addresses
    ip_addresses_to_check = list(set(spec['address'] for spec in ip_specs))
    existing_ips = _get_existing_ip_addresses(nb_session, ip_addresses_to_check)
    
    # 4. Perform the hard reset (Delete the old IPs)
    ips_to_delete = []
    for ip in ips_to_hard_reset:
        if ip in existing_ips:
            ips_to_delete.append(existing_ips[ip])
            # REMOVE it from the dictionary so the script thinks it doesn't exist 
            # and routes it to the ips_to_create list below!
            del existing_ips[ip]
            
    if ips_to_delete:
        logger.info(f"Deleting {len(ips_to_delete)} conflicting IPs from NetBox before recreation...")
        for ip_obj in ips_to_delete:
            delete_success = _delete_netbox_obj(ip_obj)

            # Check the return function
            if not delete_success:
                logger.error(
                    f"Failed to delete conflicting IP {ip_obj.address}. "
                    "Aborting to prevent duplicate IP creation errors."
                )
                # Stop the function, not to recreate an IP that still exists
                return False

    # 5. Separate into create and update lists
    ips_to_create = []
    ips_to_update = []
    processed_ips = set()
    
    for spec in ip_specs:
        ip_address = spec['address']
        hostname = spec['hostname']
        interface_name = spec['interface_name']
        
        # Guardrail: Prevent duplicate entries in the bulk payloads
        if ip_address in processed_ips:
            logger.warning(f"Duplicate active IP {ip_address} found in specs. Skipping second instance.")
            continue
        
        interface = interface_map.get((hostname, interface_name))
        if not interface:
            logger.warning(f"Interface '{interface_name}' on '{hostname}' not found, skipping IP {ip_address}")
            continue
        
        existing_ip = existing_ips.get(ip_address)
        
        if existing_ip:
            update_payload = _process_existing_ip(nb_session, existing_ip, spec, interface, interface_map)
            if update_payload:
                ips_to_update.append(update_payload)
        else:
            create_payload = _create_new_ip(spec, interface)
            ips_to_create.append(create_payload)
            
        processed_ips.add(ip_address)
    
    # 6. Execute bulk operations
    success = True
    
    if ips_to_create:
        logger.info(f"Creating {len(ips_to_create)} new IP addresses")
        created = _bulk_create(nb_session.ipam.ip_addresses, ips_to_create, "IP address")
        if len(created) < len(ips_to_create):
            success = False
            
    if ips_to_update:
        logger.info(f"Updating {len(ips_to_update)} existing IP addresses")
        updated = _bulk_update(nb_session.ipam.ip_addresses, ips_to_update, "IP address")
        if len(updated) < len(ips_to_update):
            success = False
            
    return success

def _get_existing_ip_addresses(
    nb_session: Any,
    ip_addresses: List[str]
) -> Dict[str, Any]:
    """
    Get existing IP addresses from NetBox concurrently using a generic fetcher.
    """
    existing_ips = {}
    
    unique_ips = list(set(ip_addresses))
    chunk_size = 50 
    
    chunks = [
        unique_ips[i:i + chunk_size] 
        for i in range(0, len(unique_ips), chunk_size)
    ]
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            
            # submit() takes the function first, followed by the arguments to pass to it
            future_to_chunk = {
                executor.submit(
                    _fetch_netbox_objects, 
                    nb_session.ipam.ip_addresses,  # The endpoint
                    'address',                     # The filter_field
                    chunk                          # The chunk
                ): chunk 
                for chunk in chunks
            }
            
            for future in concurrent.futures.as_completed(future_to_chunk):
                results = future.result()
                
                # We no longer need to check for None because _fetch_netbox_objects guarantees a list
                for ip_obj in results:
                    existing_ips[str(ip_obj.address)] = ip_obj
        
        logger.debug(f"Found {len(existing_ips)} existing IP addresses")
        
    except Exception as e:
        logger.error(f"Error querying existing IP addresses: {e}", exc_info=True)
    
    return existing_ips

def _set_primary_ips_on_devices(
    nb_session: NetBoxApi,
    ip_data_list: list[dict],
    device_cache: dict[str, object]
) -> None:
    """
    Set primary_ip4 on devices based on IP assignments.
    
    Args:
        nb_session: pynetbox API session
        ip_data_list: list of IP address entries from YAML
        device_cache: dictionary of cached device objects
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
            # Get the IP address object (fresh from NetBox)
            ip_obj = nb_session.ipam.ip_addresses.get(address=primary_ip)
            
            if not ip_obj:
                logger.warning(f"IP {primary_ip} not found, skipping primary IP for {hostname}")
                continue
            
            # CRITICAL: Verify IP is actually assigned to THIS device
            if ip_obj.assigned_object_type != 'dcim.interface':
                logger.warning(
                    f"IP {primary_ip} is not assigned to an interface, "
                    f"skipping primary IP for {hostname}"
                )
                continue
            
            if not ip_obj.assigned_object_id:
                logger.warning(
                    f"IP {primary_ip} has no assigned interface, "
                    f"skipping primary IP for {hostname}"
                )
                continue
            
            # Get the interface to verify it belongs to this device
            try:
                assigned_interface = nb_session.dcim.interfaces.get(ip_obj.assigned_object_id)
                if not assigned_interface:
                    logger.warning(
                        f"Could not retrieve interface {ip_obj.assigned_object_id} "
                        f"for IP {primary_ip}, skipping primary IP for {hostname}"
                    )
                    continue
                
                if assigned_interface.device.id != device.id:
                    logger.warning(
                        f"IP {primary_ip} is assigned to device '{assigned_interface.device.name}' "
                        f"(ID {assigned_interface.device.id}), not '{hostname}' (ID {device.id}). "
                        f"This IP was likely not successfully reassigned. Skipping primary IP assignment."
                    )
                    continue
                    
            except Exception as e:
                logger.warning(
                    f"Error verifying interface assignment for IP {primary_ip}: {e}. "
                    f"Skipping primary IP for {hostname}"
                )
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
    from pynetbox_functions import _main, _debug
    _main("Update devices IPs in NetBox", ips)
    #_debug(ips)
    #_debug(_get_existing_ip_addresses, data_list = ['192.168.106.42', '134.108.95.13'])