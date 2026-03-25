#!/usr/bin/env python3
"""
Automatically manage 'devices' table in the postgres database
"""

import typer
from pathlib import Path
from typing import Optional, List, Dict, Union

from std_objs import initialize_inventory, project_dir, load_yaml

app = typer.Typer(help = "Automatically manage 'devices' table in 'network_inventory' database")
inventory = initialize_inventory()

@app.command()
def serials():
    """Populate devices with serial numbers from a local yaml file"""
    typer.secho(f"Populating devices database", fg = typer.colors.GREEN)

    yaml_serials = project_dir / 'src' / 'serial_numbers.yaml'
    devices = load_yaml(yaml_serials)
    add_devices_from_list(devices)

@app.command()
def invs():
    """Populate devices inventory numbers from a local yaml file"""
    typer.secho(f"Populating devices database", fg = typer.colors.GREEN)

    yaml_invs = project_dir / 'src' / 'inv_numbers.yaml'
    devices = load_yaml(yaml_invs)
    add_devices_from_list(devices)

@app.command()
def merge():
    """Merge duplicate entries"""
    merge_duplicate_hostnames()

def is_likely_serial_number(value: str) -> bool:
    """
    Determine if a value is likely a serial number vs inventory number
    
    Serial numbers typically:
    - Contain mix of letters and numbers
    - Are longer (usually 10+ characters)
    - Often have specific patterns (FOC, SPE, CN, FDO prefixes)
    
    Inventory numbers typically:
    - Are purely numeric or very short
    - Usually 4-6 digits
    
    Args:
        value: String to check
    
    Returns:
        True if likely a serial number, False if likely inventory number
    """
    if not value or not isinstance(value, str):
        return False
    
    value = value.strip()
    
    # Pure numbers under 7 digits are likely inventory numbers
    if value.isdigit() and len(value) <= 6:
        return False
    
    # Common serial number prefixes
    serial_prefixes = ['FOC', 'SPE', 'CN', 'FDO', 'FCH', 'JAE', 'SAD']
    if any(value.upper().startswith(prefix) for prefix in serial_prefixes):
        return True
    
    # Serial numbers usually have letters and numbers mixed
    has_letters = any(c.isalpha() for c in value)
    has_numbers = any(c.isdigit() for c in value)
    
    # If it has both letters and numbers and is long enough, likely serial
    if has_letters and has_numbers and len(value) >= 8:
        return True
    
    # Default: if purely numeric and short, it's inventory
    if value.isdigit():
        return False
    
    # If we're unsure but it has letters, assume serial
    return has_letters


def add_devices_from_list(devices_list: List[Dict[str, str]]) -> Dict[str, any]:
    """
    Add multiple devices from a list of {hostname: value} dictionaries
    Auto-detects if value is serial_number or inventory_number
    
    Args:
        devices_list: List of dicts, each with one key-value pair {hostname: value}
        Examples:
            [{'rsgw10118sp-1': '18128'}]  → Detected as inventory_number
            [{'rgcs0003-1': 'SPE192400AA'}]  → Detected as serial_number
    
    Returns:
        Dictionary with statistics: {added: int, skipped: int, errors: int, details: list}
    """
    results = {
        'added': 0,
        'skipped': 0,
        'reactivated': 0,
        'skipped': 0,
        'errors': 0,
        'details': []
    }
    
    for device_dict in devices_list:
        # Extract hostname and value from dict
        if not device_dict:
            continue
        
        hostname, value = next(iter(device_dict.items()))
        
        # Determine if value is serial number or inventory number
        is_serial = is_likely_serial_number(value)
        
        if is_serial:
            serial_number = value
            inventory_number = None
            field_type = "Serial"
        else:
            serial_number = None
            inventory_number = str(value)
            field_type = "Inventory"
        
        try:
            # Check if device already exists
            devices = inventory.get_devices_by_hostname(hostname, active_only=False)
            existing = devices[0] if devices else None
            
            if existing:
                # Device exists - check if we need to update it
                needs_update = False
                updates = {}
                
                if not existing['active']:
                    updates['active'] = True
                    needs_update = True
                
                # Update the field that was provided
                if is_serial and existing['serial_number'] != serial_number:
                    updates['serial_number'] = serial_number
                    needs_update = True
                elif not is_serial and existing['inventory_number'] != inventory_number:
                    updates['inventory_number'] = inventory_number
                    needs_update = True
                
                if needs_update:
                    inventory.update_device(existing['id'], **updates)
                    status = 'reactivated' if 'active' in updates else 'updated'
                    results['reactivated'] += 1 if status == 'reactivated' else 0
                    results['details'].append({
                        'hostname': hostname,
                        field_type.lower(): value,
                        'status': status,
                        'id': existing['id']
                    })
                    typer.secho(f"  \u2713 Updated: {hostname} ({field_type}: {value})", 
                               fg=typer.colors.YELLOW)
                else:
                    results['skipped'] += 1
                    results['details'].append({
                        'hostname': hostname,
                        field_type.lower(): value,
                        'status': 'already_exists',
                        'id': existing['id']
                    })
                    typer.secho(f"  \u2022 Skipped: {hostname} ({field_type}: {value}) - already exists", 
                               fg=typer.colors.BLUE, dim=True)
            else:
                # Device doesn't exist - add it
                device_id = inventory.add_device(
                    hostname=hostname,
                    serial_number=serial_number,
                    inventory_number=inventory_number,
                    active=True
                )
                results['added'] += 1
                results['details'].append({
                    'hostname': hostname,
                    field_type.lower(): value,
                    'status': 'added',
                    'id': device_id
                })
                typer.secho(f"  \u2713 Added: {hostname} ({field_type}: {value}, ID: {device_id})", 
                           fg=typer.colors.GREEN)
                
        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                'hostname': hostname,
                field_type.lower(): value,
                'status': 'error',
                'error': str(e)
            })
            typer.secho(f"  \u2717 Error adding {hostname}: {e}", 
                       fg=typer.colors.RED, err=True)
    
    return results

def merge_duplicate_hostnames() -> None:
    """
    Find hostname with multiple DB entries, merge onto the entry that has a 
    serial number (to avoid unique constraint violations), then delete the duplicates.
    """

    all_devices = inventory.get_all_devices(active_only = False)

    # Group by hostname
    by_hostname: dict[str, list] = {}
    for device in all_devices:
        by_hostname.setdefault(device['hostname'], []).append(device)

    for hostname, entries in by_hostname.items():
        if len(entries) < 2:
            continue

        # Prefer the entry with a serial number as canonical,
        # fall back to the oldest (lowest ID) if none have a serial
        entries_with_serial = [e for e in entries if e.get('serial_number')]
        if entries_with_serial:
            canonical = entries_with_serial[0]
        else:
            canonical = min(entries, key = lambda d: d['id'])

        duplicates = [e for e in entries if e['id'] != canonical['id']]

        # Merge all non-empty fields onto canonical
        updates = {}
        for dup in duplicates:
            if not canonical.get('serial_number') and dup.get('serial_number'):
                updates['serial_number'] = dup['serial_number']
            if not canonical.get('inventory_number') and dup.get('inventory_number'):
                updates['inventory_number'] = dup['inventory_number']

        if updates:
            inventory.update_device(canonical['id'], **updates)
            typer.secho(
                f"  \u2713 Merged into ID {canonical['id']} ({hostname}): {updates}",
                fg=typer.colors.GREEN
            )
        else:
            typer.secho(
                f"  \u2022 No missing fields to merge for {hostname} (ID {canonical['id']})",
                fg=typer.colors.BLUE, dim=True
            )

        # Delete duplicates
        for dup in duplicates:
            inventory.delete_device(dup['id'])
            typer.secho(
                f"  \u2717 Deleted duplicate ID {dup['id']} ({hostname}) "
                f"serial = {dup.get('serial_number') or '-'}, "
                f"inv = {dup.get('inventory_number') or '-'}",
                fg=typer.colors.YELLOW
            )

if __name__ == "__main__":
    app()
