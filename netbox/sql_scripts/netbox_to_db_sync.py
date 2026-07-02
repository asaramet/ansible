#!/usr/bin/env python3
"""
NetBox to PostgreSQL Database Synchronization

Extract devices data from NetBox platform and synchronize with PostgreSQL database.
Handles device matching by hostname, serial number, and inventory number.
"""

import logging
import typer
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

import sys, os
main_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pynetbox_folder = os.path.join(main_folder, "pynetbox")
sys.path.insert(0, pynetbox_folder)

# Import existing functions from pynetbox_functions
from pynetbox_functions import _cache_devices
from pynetbox.core.api import Api as NetBoxApi
from pynetbox.models.dcim import Devices
from pynetbox.core.response import Record
from network_inventory import NetworkInventory

from std_objs import get_inventory_connection, project_dir, vault_file, vault_password_file, host

# Configure logging
logger = logging.getLogger(__name__)

app = typer.Typer(
    help="Extract devices from NetBox and synchronize with PostgreSQL database"
)

# Main folder structure
this_folder = Path(__file__).resolve().parent
main_folder = this_folder.parent

def extract_netbox_devices_bulk(nb_session: NetBoxApi, 
                              active_only: bool = True) -> Dict[str, Dict[str, Any]]:
    """
    Extract all devices from NetBox in a SINGLE bulk request and return as a dictionary.
    Optimized to minimize HTTP requests by fetching all devices at once.
    
    Note: 
    - Devices with hostnames starting with capital letters or underscore are automatically
      filtered out as they are not devices that should be monitored.
    - In NetBox, inventory_number is mapped from the 'asset_tag' field.
    - To properly sync the Active flag to PostgreSQL, use active_only=False to include
      all devices (active, offline, decommissioning, etc.)
    
    Args:
        nb_session: Active NetBox API session
        active_only: If True, only extract devices with status='active' from NetBox.
                     Set to False to extract all devices regardless of status (default: True)
        
    Returns:
        Dictionary with structure:
        {
            "hostname": {
                "hostname": device_hostname,
                "id": netbox_device_id,
                "serial_number": device_serial_number,
                "inventory_number": device_asset_tag,  # from NetBox asset_tag field
                "status": device_status  # from NetBox status field
            },
            ...
        }
    """
    devices_dict = {}
    
    try:
        # Fetch ALL devices in one go - pynetbox handles pagination automatically
        # Using .all() returns a list with a single API call (or minimal calls for pagination)
        if active_only:
            devices = list(nb_session.dcim.devices.filter(status="active"))
        else:
            devices = list(nb_session.dcim.devices.all())
        
        logger.info(f"Fetched {len(devices)} devices from NetBox in bulk")
        
        # Process all devices from the cached/preloaded list - NO additional HTTP requests
        for device in devices:
            hostname = device.name
            if not hostname:
                logger.warning(f"Device without hostname found (ID: {device.id}), skipping")
                continue
            
            # Ignore devices with hostnames starting with capital letters or underscore
            # (they are not devices that should be monitored)
            if hostname and (hostname[0].isupper() or hostname.startswith('_')):
                logger.debug(f"Skipping device {hostname} (starts with capital letter or underscore)")
                continue
            
            # Access only the fields we need - these are in the initial response
            serial_number = str(device.serial) if device.serial else None
            
            # In NetBox, inventory number is stored as 'asset_tag', not in custom_fields
            inventory_number = str(device.asset_tag) if hasattr(device, 'asset_tag') and device.asset_tag else None
            
            # Get device status from NetBox
            # status can be a Record object with .value attribute or a plain string
            if device.status:
                device_status = device.status.value if hasattr(device.status, 'value') else str(device.status)
            else:
                device_status = None
            
            devices_dict[hostname] = {
                'hostname': hostname,
                'id': device.id,
                'serial_number': serial_number,
                'inventory_number': inventory_number,
                'status': device_status,
            }
        
        logger.info(f"Extracted {len(devices_dict)} devices with valid hostnames")
        
    except Exception as e:
        logger.error(f"Error extracting devices from NetBox: {e}", exc_info=True)
        raise
    
    return devices_dict


def get_postgresql_devices(inventory: NetworkInventory, 
                          active_only: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all devices from PostgreSQL database organized by hostname.
    
    Args:
        inventory: NetworkInventory instance connected to PostgreSQL
        active_only: If True, only get active devices (default: False)
        
    Returns:
        Dictionary with structure:
        {
            "hostname": [
                {
                    "id": db_device_id,
                    "hostname": hostname,
                    "serial_number": db_serial_number,
                    "inventory_number": db_inventory_number,
                    "active": db_active_status
                },
                ...
            ],
            ...
        }
    """
    devices_dict = {}
    
    try:
        db_devices = inventory.get_all_devices(active_only=active_only)
        
        logger.info(f"Found {len(db_devices)} devices in PostgreSQL database")
        
        for device in db_devices:
            hostname = device.get('hostname')
            if not hostname:
                logger.warning(f"Device without hostname found in DB (ID: {device.get('id')}), skipping")
                continue
            
            if hostname not in devices_dict:
                devices_dict[hostname] = []
            
            devices_dict[hostname].append({
                'id': device.get('id'),
                'hostname': hostname,
                'serial_number': device.get('serial_number'),
                'inventory_number': device.get('inventory_number'),
                'active': device.get('active', True)
            })
        
    except Exception as e:
        logger.error(f"Error getting devices from PostgreSQL: {e}", exc_info=True)
        raise
    
    return devices_dict


def find_matching_device(db_devices: List[Dict[str, Any]], 
                        hostname: str, 
                        serial_number: Optional[str] = None,
                        inventory_number: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Find matching device in PostgreSQL database based on multiple criteria.
    
    Matching rules (in order of priority):
    1. Exact match: hostname + serial_number + inventory_number
    2. hostname + serial_number (inventory_number may differ)
    3. hostname + inventory_number (serial_number may differ)
    4. hostname only (if serial and inventory are None in new data)
    
    Args:
        db_devices: List of database devices for a specific hostname
        hostname: Device hostname
        serial_number: Device serial number (may be None)
        inventory_number: Device inventory number (may be None)
        
    Returns:
        Tuple of (best_match_device, conflicting_devices)
    """
    # Rule 1: Exact match (hostname + serial + inventory)
    for device in db_devices:
        if (device['serial_number'] == serial_number and 
            device['inventory_number'] == inventory_number):
            return device, []
    
    # Rule 2: Match by hostname + serial_number
    serial_matches = [d for d in db_devices if d['serial_number'] == serial_number]
    
    if len(serial_matches) == 1:
        return serial_matches[0], []
    elif len(serial_matches) > 1:
        return serial_matches[0], serial_matches[1:]
    
    # Rule 3: Match by hostname + inventory_number
    inv_matches = [d for d in db_devices if d['inventory_number'] == inventory_number]
    
    if len(inv_matches) == 1:
        return inv_matches[0], []
    elif len(inv_matches) > 1:
        return inv_matches[0], inv_matches[1:]
    
    # Rule 4: Match by hostname only (if new data has no serial or inventory)
    if serial_number is None and inventory_number is None:
        active_devices = [d for d in db_devices if d.get('active')]
        if active_devices:
            return active_devices[0], []
        elif db_devices:
            return db_devices[0], []
    
    # No match found
    return None, []


def needs_update(db_device: Dict[str, Any], 
                nb_device: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    """
    Check if a database device needs to be updated with NetBox data.
    
    Only updates when NetBox has a non-None value. If NetBox has None,
    the database value is preserved (not overwritten with None).
    
    Args:
        db_device: Device from PostgreSQL database
        nb_device: Device from NetBox
        
    Returns:
        Dictionary of fields that need updating with (old_value, new_value) tuples
    """
    updates = {}
    
    db_serial = db_device.get('serial_number')
    nb_serial = nb_device.get('serial_number')
    # Only update if NetBox has a serial number (not None)
    if nb_serial is not None and db_serial != nb_serial:
        updates['serial_number'] = (db_serial, nb_serial)
    
    db_inv = db_device.get('inventory_number')
    nb_inv = nb_device.get('inventory_number')
    # Only update if NetBox has an inventory number (not None)
    if nb_inv is not None and db_inv != nb_inv:
        updates['inventory_number'] = (db_inv, nb_inv)
    
    # Check if Active flag needs updating based on NetBox status
    nb_status = nb_device.get('status')
    if nb_status is not None:
        # Device is active in NetBox if status.lower() is 'active' or 'commissioned'
        # All other statuses (decommissioning, decomissioning, offline, staged, etc.) are considered inactive
        nb_active = nb_status.lower() in ['active', 'commissioned']
        db_active = db_device.get('active', False)
        
        # Only update if the active status differs between NetBox and DB
        if db_active != nb_active:
            updates['active'] = (db_active, nb_active)
    
    return updates


def handle_device_conflict(db_devices: List[Dict[str, Any]], 
                          new_device: Dict[str, Any],
                          inventory: NetworkInventory) -> Dict[str, Any]:
    """
    Handle device conflicts where hostname matches but serial/inventory differ.
    
    Implements logic where if hostname is same but serial number is different,
    they are probably 2 different devices. Old one is renamed (using its serial
    number as hostname) and marked as inactive.
    
    Args:
        db_devices: List of existing database devices with same hostname
        new_device: New device data from NetBox
        inventory: NetworkInventory instance
        
    Returns:
        The new device data to be added
    """
    new_hostname = new_device['hostname']
    new_serial = new_device['serial_number']
    
    for db_device in db_devices:
        db_serial = db_device['serial_number']
        db_id = db_device['id']
        
        if db_serial and new_serial and db_serial != new_serial:
            new_hostname_for_old = db_serial
            
            existing_with_new_name = inventory.get_devices_by_hostname(
                new_hostname_for_old, active_only=False
            )
            
            if existing_with_new_name:
                new_hostname_for_old = f"{db_serial}_old_{db_id}"
                logger.info(f"Renaming device {new_hostname} (ID: {db_id}) to {new_hostname_for_old} to avoid conflict")
            else:
                logger.info(f"Renaming device {new_hostname} (ID: {db_id}) to {new_hostname_for_old}")
            
            inventory.update_device(
                db_id,
                hostname=new_hostname_for_old,
                active=False
            )
            logger.info(f"Old device {new_hostname} renamed to {new_hostname_for_old} and deactivated")
    
    return new_device


def synchronize_devices(nb_devices: Dict[str, Dict[str, Any]], 
                       db_devices_by_hostname: Dict[str, List[Dict[str, Any]]],
                       inventory: NetworkInventory,
                       dry_run: bool = False) -> Dict[str, Any]:
    """
    Synchronize devices from NetBox to PostgreSQL database.
    
    For each device in NetBox:
    - Check if it exists in PostgreSQL
    - If exists and data differs, update PostgreSQL
    - If exists but serial/inventory differ significantly, handle conflict
    - If doesn't exist, add to PostgreSQL
    
    Args:
        nb_devices: Dictionary of devices from NetBox
        db_devices_by_hostname: Dictionary of PostgreSQL devices by hostname
        inventory: NetworkInventory instance
        dry_run: If True, only report changes without making them
        
    Returns:
        Dictionary with synchronization statistics
    """
    stats = {
        'total_netbox': len(nb_devices),
        'total_db': sum(len(devices) for devices in db_devices_by_hostname.values()),
        'added': 0,
        'updated': 0,
        'conflicts_resolved': 0,
        'skipped': 0,
        'errors': 0,
        'details': []
    }
    
    for hostname, nb_device in nb_devices.items():
        try:
            logger.debug(f"Processing device: {hostname}")
            
            db_devices = db_devices_by_hostname.get(hostname, [])
            
            if not db_devices:
                # Device doesn't exist in database - add it
                # Determine active status from NetBox status
                nb_status = nb_device.get('status')
                is_active = nb_status.lower() in ['active', 'commissioned'] if nb_status else False
                
                if dry_run:
                    stats['details'].append({
                        'hostname': hostname,
                        'action': 'add',
                        'serial_number': nb_device['serial_number'],
                        'inventory_number': nb_device['inventory_number'],
                        'active': is_active
                    })
                    logger.info(f"[DRY RUN] Would add: {hostname} (active={is_active})")
                else:
                    device_id = inventory.add_device(
                        hostname=hostname,
                        serial_number=nb_device['serial_number'],
                        inventory_number=nb_device['inventory_number'],
                        active=is_active
                    )
                    stats['added'] += 1
                    stats['details'].append({
                        'hostname': hostname,
                        'action': 'add',
                        'device_id': device_id,
                        'serial_number': nb_device['serial_number'],
                        'inventory_number': nb_device['inventory_number']
                    })
                    logger.info(f"Added device: {hostname} (ID: {device_id})")
            else:
                best_match, conflicts = find_matching_device(
                    db_devices, hostname,
                    nb_device['serial_number'],
                    nb_device['inventory_number']
                )
                
                if best_match:
                    updates = needs_update(best_match, nb_device)
                    
                    if updates:
                        if dry_run:
                            update_desc = ", ".join([f"{k}: {v[0]} -> {v[1]}" for k, v in updates.items()])
                            stats['details'].append({
                                'hostname': hostname,
                                'action': 'update',
                                'device_id': best_match['id'],
                                'updates': update_desc
                            })
                            logger.info(f"[DRY RUN] Would update: {hostname} - {update_desc}")
                        else:
                            update_kwargs = {}
                            for field, (old_val, new_val) in updates.items():
                                update_kwargs[field] = new_val
                            
                            success = inventory.update_device(best_match['id'], **update_kwargs)
                            if success:
                                stats['updated'] += 1
                                update_desc = ", ".join([f"{k}: {v[0]} -> {v[1]}" for k, v in updates.items()])
                                stats['details'].append({
                                    'hostname': hostname,
                                    'action': 'update',
                                    'device_id': best_match['id'],
                                    'updates': update_desc
                                })
                                logger.info(f"Updated device: {hostname} (ID: {best_match['id']}) - {update_desc}")
                            else:
                                stats['errors'] += 1
                                logger.error(f"Failed to update device: {hostname} (ID: {best_match['id']})")
                    else:
                        stats['skipped'] += 1
                        logger.debug(f"Skipped: {hostname} - no changes needed")
                elif conflicts:
                    stats['conflicts_resolved'] += 1
                    new_device_data = handle_device_conflict(db_devices, nb_device, inventory)
                    
                    # Determine active status from NetBox status
                    nb_status = nb_device.get('status')
                    is_active = nb_status.lower() in ['active', 'commissioned'] if nb_status else False
                    
                    if dry_run:
                        stats['details'].append({
                            'hostname': hostname,
                            'action': 'conflict_resolved_and_add',
                            'serial_number': new_device_data['serial_number'],
                            'inventory_number': new_device_data['inventory_number'],
                            'active': is_active
                        })
                        logger.info(f"[DRY RUN] Would resolve conflict and add: {hostname} (active={is_active})")
                    else:
                        device_id = inventory.add_device(
                            hostname=hostname,
                            serial_number=new_device_data['serial_number'],
                            inventory_number=new_device_data['inventory_number'],
                            active=is_active
                        )
                        stats['added'] += 1
                        stats['details'].append({
                            'hostname': hostname,
                            'action': 'conflict_resolved_and_add',
                            'device_id': device_id,
                            'serial_number': new_device_data['serial_number'],
                            'inventory_number': new_device_data['inventory_number']
                        })
                        logger.info(f"Resolved conflict and added device: {hostname} (ID: {device_id})")
                else:
                    existing_serials = {d['serial_number'] for d in db_devices if d['serial_number']}
                    existing_invs = {d['inventory_number'] for d in db_devices if d['inventory_number']}
                    new_serial = nb_device['serial_number']
                    new_inv = nb_device['inventory_number']
                    
                    if ((new_serial and new_serial not in existing_serials) or
                        (new_inv and new_inv not in existing_invs)):
                        # Determine active status from NetBox status
                        nb_status = nb_device.get('status')
                        is_active = nb_status.lower() in ['active', 'commissioned'] if nb_status else False
                        
                        if dry_run:
                            stats['details'].append({
                                'hostname': hostname,
                                'action': 'add_new_variant',
                                'serial_number': new_serial,
                                'inventory_number': new_inv,
                                'active': is_active
                            })
                            logger.info(f"[DRY RUN] Would add new variant: {hostname} (active={is_active})")
                        else:
                            device_id = inventory.add_device(
                                hostname=hostname,
                                serial_number=new_serial,
                                inventory_number=new_inv,
                                active=is_active
                            )
                            stats['added'] += 1
                            stats['details'].append({
                                'hostname': hostname,
                                'action': 'add_new_variant',
                                'device_id': device_id,
                                'serial_number': new_serial,
                                'inventory_number': new_inv
                            })
                            logger.info(f"Added new device variant: {hostname} (ID: {device_id})")
                    else:
                        stats['skipped'] += 1
                        logger.debug(f"Skipped: {hostname} - data already exists in database")
        except Exception as e:
            stats['errors'] += 1
            stats['details'].append({
                'hostname': hostname,
                'action': 'error',
                'error': str(e)
            })
            logger.error(f"Error processing device {hostname}: {e}", exc_info=True)
    
    return stats


def get_netbox_session(server: str = "development") -> NetBoxApi:
    """
    Get a NetBox API session.
    
    Args:
        server: NetBox server to connect to ("development" or "production")
        
    Returns:
        NetBox API session
    """
    from nb import development, production
    
    if server == "development":
        nb_session = development
    elif server == "production":
        nb_session = production
    else:
        raise ValueError(f"Unknown server: {server}. Use 'development' or 'production'")
    
    nb_session.http_session.verify = False
    
    return nb_session


@app.command()
def sync(
    server: str = "development",
    db_host: str = host,
    active_only: bool = False,
    dry_run: bool = False,
    verbose: bool = False
):
    """
    Synchronize devices from NetBox to PostgreSQL database.
    
    Args:
        server: NetBox server to connect to (development or production)
        db_host: PostgreSQL database host
        active_only: If True, only sync active devices from NetBox (default: False to sync all devices including offline/decommissioning)
        dry_run: If True, only show what would be changed
        verbose: Enable verbose logging
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    typer.echo("Starting NetBox to PostgreSQL synchronization...")
    
    try:
        typer.echo(f"Connecting to NetBox server: {server}")
        nb_session = get_netbox_session(server)
        
        typer.echo("Extracting devices from NetBox...")
        nb_devices = extract_netbox_devices_bulk(nb_session, active_only=active_only)
        typer.echo(f"Found {len(nb_devices)} devices in NetBox")
        
        typer.echo(f"Connecting to PostgreSQL database on {db_host}")
        inventory = get_inventory_connection(db_host, vault_file, vault_password_file)
        
        typer.echo("Extracting devices from PostgreSQL...")
        db_devices_by_hostname = get_postgresql_devices(inventory, active_only=False)
        total_db_devices = sum(len(devices) for devices in db_devices_by_hostname.values())
        typer.echo(f"Found {total_db_devices} devices in PostgreSQL database")
        
        typer.echo("Starting synchronization...")
        stats = synchronize_devices(
            nb_devices, 
            db_devices_by_hostname, 
            inventory,
            dry_run=dry_run
        )
        
        typer.echo("\n" + "="*60)
        typer.echo("SYNCHRONIZATION SUMMARY")
        typer.echo("="*60)
        
        mode = "DRY RUN - " if dry_run else ""
        typer.echo(f"Mode: {mode}")
        typer.echo(f"NetBox devices:     {stats['total_netbox']}")
        typer.echo(f"PostgreSQL devices: {stats['total_db']}")
        typer.echo(f"Added:               {stats['added']}")
        typer.echo(f"Updated:             {stats['updated']}")
        typer.echo(f"Conflicts resolved:  {stats['conflicts_resolved']}")
        typer.echo(f"Skipped:             {stats['skipped']}")
        typer.echo(f"Errors:              {stats['errors']}")
        
        if dry_run and (stats['added'] > 0 or stats['updated'] > 0 or stats['conflicts_resolved'] > 0):
            typer.echo("\nRun without --dry-run to apply these changes")
        
        typer.echo("="*60)
        
        if stats['errors'] > 0:
            raise typer.Exit(code=1)
        
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        if verbose:
            logger.exception("Full error details:")
        raise typer.Exit(code=1)


@app.command()
def extract(
    server: str = "development",
    output_file: Optional[str] = None,
    active_only: bool = False,
    verbose: bool = False
):
    """
    Extract devices from NetBox and save to dictionary (optionally to file).
    
    Args:
        server: NetBox server to connect to
        output_file: If provided, save extracted data to this YAML file
        active_only: If True, only extract active devices (default: False to extract all)
        verbose: Enable verbose logging
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level)
    
    try:
        typer.echo(f"Connecting to NetBox server: {server}")
        nb_session = get_netbox_session(server)
        
        typer.echo("Extracting devices from NetBox...")
        nb_devices = extract_netbox_devices_bulk(nb_session, active_only=active_only)
        
        typer.echo(f"Extracted {len(nb_devices)} devices")
        
        if output_file:
            output_path = Path(output_file)
            import yaml
            with open(output_path, 'w') as f:
                yaml.dump(nb_devices, f, default_flow_style=False)
            typer.echo(f"Saved devices to: {output_path}")
        else:
            sample_hostname = next(iter(nb_devices.keys())) if nb_devices else None
            if sample_hostname:
                sample_device = nb_devices[sample_hostname]
                typer.echo("\nSample device data:")
                typer.echo(f"Hostname: {sample_device['hostname']}")
                typer.echo(f"  Serial: {sample_device['serial_number']}")
                typer.echo(f"  Inventory: {sample_device['inventory_number']}")
                typer.echo(f"  NetBox ID: {sample_device['id']}")
                typer.echo(f"  ... ({len(nb_devices)} devices total)")
        
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command()
def compare(
    server: str = "development",
    db_host: str = host,
    active_only: bool = False,
    show_matches: bool = False,
    verbose: bool = False
):
    """
    Compare devices between NetBox and PostgreSQL without making changes.
    
    Args:
        server: NetBox server to connect to
        db_host: PostgreSQL database host
        active_only: If True, only compare active devices from NetBox (default: False to compare all)
        show_matches: Show devices that match (default: only show differences)
        verbose: Enable verbose logging
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level)
    
    try:
        typer.echo(f"Connecting to NetBox server: {server}")
        nb_session = get_netbox_session(server)
        
        typer.echo("Extracting devices from NetBox...")
        nb_devices = extract_netbox_devices_bulk(nb_session, active_only=active_only)
        
        typer.echo(f"Connecting to PostgreSQL database on {db_host}")
        inventory = get_inventory_connection(db_host, vault_file, vault_password_file)
        
        typer.echo("Extracting devices from PostgreSQL...")
        db_devices_by_hostname = get_postgresql_devices(inventory, active_only=False)
        
        typer.echo("\n" + "="*60)
        typer.echo("COMPARISON RESULTS")
        typer.echo("="*60)
        
        netbox_hostnames = set(nb_devices.keys())
        db_hostnames = set(db_devices_by_hostname.keys())
        
        only_in_netbox = netbox_hostnames - db_hostnames
        typer.echo(f"Only in NetBox:        {len(only_in_netbox)}")
        if only_in_netbox:
            for hostname in sorted(only_in_netbox):
                device = nb_devices[hostname]
                serial = device['serial_number'] or 'None'
                inv = device['inventory_number'] or 'None'
                typer.echo(f"  - {hostname} (serial: {serial}, inv: {inv})")
        
        only_in_db = db_hostnames - netbox_hostnames
        typer.echo(f"Only in PostgreSQL:    {len(only_in_db)}")
        if only_in_db:
            for hostname in sorted(only_in_db):
                devices = db_devices_by_hostname[hostname]
                for device in devices:
                    serial = device['serial_number'] or 'None'
                    inv = device['inventory_number'] or 'None'
                    typer.echo(f"  - {hostname} (serial: {serial}, inv: {inv}, ID: {device['id']})")
        
        in_both = netbox_hostnames & db_hostnames
        typer.echo(f"In both:              {len(in_both)}")
        
        differences = 0
        matches = 0
        
        for hostname in sorted(in_both):
            nb_device = nb_devices[hostname]
            db_devices = db_devices_by_hostname[hostname]
            
            has_match = False
            has_diff = False
            
            for db_device in db_devices:
                db_serial = db_device['serial_number']
                db_inv = db_device['inventory_number']
                nb_serial = nb_device['serial_number']
                nb_inv = nb_device['inventory_number']
                
                if db_serial == nb_serial and db_inv == nb_inv:
                    has_match = True
                
                if db_serial != nb_serial or db_inv != nb_inv:
                    has_diff = True
            
            if has_match and not has_diff:
                matches += 1
            elif has_diff:
                differences += 1
        
        typer.echo(f"Matching:             {matches}")
        typer.echo(f"Differences:          {differences}")
        
        if show_matches:
            typer.echo("\nDetailed comparison:")
            for hostname in sorted(in_both):
                nb_device = nb_devices[hostname]
                db_devices = db_devices_by_hostname[hostname]
                typer.echo(f"\n{hostname}:")
                typer.echo(f"  NetBox: serial={nb_device['serial_number']}, inv={nb_device['inventory_number']}")
                for i, db_device in enumerate(db_devices):
                    typer.echo(f"  DB[{i}]:   serial={db_device['serial_number']}, inv={db_device['inventory_number']}, ID={db_device['id']}, active={db_device['active']}")
        
        typer.echo("="*60)
        
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


# Public functions for programmatic use
def create_device_dict_from_netbox(nb_session: NetBoxApi, 
                                   active_only: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Public function to create device dictionary from NetBox.
    
    Args:
        nb_session: Active NetBox API session
        active_only: If True, only extract active devices (default: False to extract all)
        
    Returns:
        Dictionary with structure: {hostname: device_data_dict}
    """
    return extract_netbox_devices_bulk(nb_session, active_only=active_only)


def sync_with_database(nb_session: NetBoxApi,
                       inventory: NetworkInventory,
                       active_only: bool = False,
                       dry_run: bool = False) -> Dict[str, Any]:
    """
    Public function to synchronize NetBox devices with PostgreSQL database.
    
    Args:
        nb_session: Active NetBox API session
        inventory: NetworkInventory instance
        active_only: If True, only sync active devices from NetBox (default: False to sync all)
        dry_run: Only report changes without applying them
        
    Returns:
        Dictionary with synchronization statistics and details
    """
    nb_devices = extract_netbox_devices_bulk(nb_session, active_only=active_only)
    db_devices_by_hostname = get_postgresql_devices(inventory, active_only=False)
    return synchronize_devices(nb_devices, db_devices_by_hostname, inventory, dry_run=dry_run)


if __name__ == "__main__":
    app()
