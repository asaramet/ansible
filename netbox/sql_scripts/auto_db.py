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

    yaml_serials = project_dir / 'src' / 'numbers' /'serial_numbers.yaml'
    devices = load_yaml(yaml_serials)
    add_devices_from_list(devices)

@app.command()
def invs():
    """Populate devices inventory numbers from a local yaml file"""
    typer.secho(f"Populating devices database", fg = typer.colors.GREEN)

    yaml_invs = project_dir / 'src' / 'numbers' / 'inv_numbers.yaml'
    devices = load_yaml(yaml_invs)
    add_devices_from_list(devices)

@app.command()
def delist():
    """Synchronize inventory delisted devices from a local yaml file"""
    typer.secho(f"Populating devices database", fg = typer.colors.GREEN)

    yaml_data = project_dir / 'src' / 'numbers' / 'delisted.yaml'
    devices = load_yaml(yaml_data)
    sync_devices(devices)

@app.command()
def extra():
    """Add extra/unknown active devices from a local yaml file"""
    typer.secho(f"Populating devices database", fg = typer.colors.GREEN)

    yaml_data = project_dir / 'src' / 'numbers' / 'extra.yaml'
    devices = load_yaml(yaml_data)
    #typer.secho(f"Devices: {devices}")
    sync_devices(devices, True)

@app.command()
def merge():
    """Merge duplicate serial number entries, then duplicate hostname entries."""
    typer.secho("\n── Serial number duplicates ──", fg=typer.colors.WHITE, bold=True)
    merge_duplicate_serials()
    typer.secho("\n── Hostname duplicates ──", fg=typer.colors.WHITE, bold=True)
    merge_duplicate_hostnames()

@app.command()
def seed():
    """Seed the database from a yaml backup file"""
    b_file = project_dir / 'data' / 'backup_db.yaml'
    device_dict = load_yaml(b_file)
    add_devices_from_dict(device_dict)

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

    # Starts with 'CU-' are likely inventory numbers
    inventory_prefixes = ['CU-', 'CV-']
    if any(value.upper().startswith(prefix) for prefix in inventory_prefixes):
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

def merge_duplicate_serials() -> None:
    """
    Find entries sharing the same serial number (possibly with different hostnames)
    and merge them into the most complete record.

    The canonical entry is chosen by preferring:
    1. The entry whose hostname differs from the serial number (i.e. has a real hostname)
    2. Otherwise the oldest (lowest ID)

    The duplicate is deleted after merging any missing fields onto the canonical.
    """

    all_devices = inventory.get_all_devices(active_only=False)

    # Group by serial number, ignoring entries with no serial
    by_serial: dict[str, list] = {}
    for device in all_devices:
        sn = device.get('serial_number')
        if sn and sn.lower() != 'none': # skip NULL and None strings
            by_serial.setdefault(sn, []).append(device)

    for serial, entries in by_serial.items():
        if len(entries) < 2:
            continue

        # Prefer entry whose hostname is not just the serial number itself
        entries_with_real_hostname = [e for e in entries if e['hostname'] != serial]
        if entries_with_real_hostname:
            canonical = entries_with_real_hostname[0]
        else:
            canonical = min(entries, key=lambda d: d['id'])

        duplicates = [e for e in entries if e['id'] != canonical['id']]

        updates = {}
        for dup in duplicates:
            if not canonical.get('inventory_number') and dup.get('inventory_number'):
                updates['inventory_number'] = dup['inventory_number']
            # Carry over active=True if any duplicate was active
            if not canonical.get('active') and dup.get('active'):
                updates['active'] = True

        if updates:
            inventory.update_device(canonical['id'], **updates)
            typer.secho(
                f"  ✓ Merged into ID {canonical['id']} ({canonical['hostname']}): {updates}",
                fg=typer.colors.GREEN
            )
        else:
            typer.secho(
                f"  • No missing fields to merge for serial {serial!r} "
                f"(kept ID {canonical['id']}, hostname {canonical['hostname']!r})",
                fg=typer.colors.BLUE, dim=True
            )

        for dup in duplicates:
            inventory.delete_device(dup['id'])
            typer.secho(
                f"  ✗ Deleted duplicate ID {dup['id']} "
                f"(hostname={dup['hostname']!r}, serial={serial!r}, "
                f"inv={dup.get('inventory_number') or '-'})",
                fg=typer.colors.YELLOW
            )

def merge_duplicate_hostnames() -> None:
    """
    Find hostnames with multiple DB entries and merge or separate them.

    Rules when an active and inactive entry share a hostname:
    - Inactive SN matches active SN (or inactive has no SN) → merge into active, keep active
    - Active has no SN, inactive has SN → merge SN onto active, set active = False
    - Both have different SNs → keep active as-is, rename inactive hostname to its serial number

    For duplicate entries with no active/inactive conflict → standard merge onto canonical.
    """

    all_devices = inventory.get_all_devices(active_only=False)

    # Group by hostname
    by_hostname: dict[str, list] = {}
    for device in all_devices:
        by_hostname.setdefault(device['hostname'], []).append(device)

    for hostname, entries in by_hostname.items():
        if len(entries) < 2:
            continue

        active_entries   = [e for e in entries if e.get('active')]
        inactive_entries = [e for e in entries if not e.get('active')]

        # --- Case: one active, one or more inactive → apply conflict rules ---
        if active_entries and inactive_entries:
            active = active_entries[0]  # there should only ever be one active per hostname

            for inactive in inactive_entries:
                active_sn   = active.get('serial_number')
                inactive_sn = inactive.get('serial_number')

                if active_sn and inactive_sn and active_sn != inactive_sn:
                    # Different SNs → genuine replacement, rename inactive to its serial number
                    new_hostname = inactive_sn
                    inventory.update_device(inactive['id'], hostname=new_hostname)
                    typer.secho(
                        f"  ↷ Renamed inactive ID {inactive['id']} hostname "
                        f"{hostname!r} → {new_hostname!r} (different SN, likely replaced device)",
                        fg=typer.colors.CYAN
                    )

                elif not active_sn and inactive_sn:
                    # Active missing SN, inactive has one → merge SN onto active, set inactive
                    updates = {'serial_number': inactive_sn, 'active': False}
                    if not active.get('inventory_number') and inactive.get('inventory_number'):
                        updates['inventory_number'] = inactive['inventory_number']
                    inventory.update_device(active['id'], **updates)
                    inventory.delete_device(inactive['id'])
                    typer.secho(
                        f"  ✓ Merged SN {inactive_sn!r} onto active ID {active['id']} "
                        f"({hostname}), set to inactive, deleted duplicate ID {inactive['id']}",
                        fg=typer.colors.GREEN
                    )

                else:
                    # Inactive SN matches active SN, or inactive has no SN → simple merge
                    updates = {}
                    if not active.get('inventory_number') and inactive.get('inventory_number'):
                        updates['inventory_number'] = inactive['inventory_number']
                    if updates:
                        inventory.update_device(active['id'], **updates)
                        typer.secho(
                            f"  ✓ Merged fields into active ID {active['id']} ({hostname}): {updates}",
                            fg=typer.colors.GREEN
                        )
                    else:
                        typer.secho(
                            f"  • No missing fields to merge for {hostname} (ID {active['id']})",
                            fg=typer.colors.BLUE, dim=True
                        )
                    inventory.delete_device(inactive['id'])
                    typer.secho(
                        f"  ✗ Deleted duplicate ID {inactive['id']} ({hostname}) "
                        f"serial = {inactive_sn or '-'}, "
                        f"inv = {inactive.get('inventory_number') or '-'}",
                        fg=typer.colors.YELLOW
                    )
            continue

        # --- Case: all same active status → standard merge onto canonical ---
        entries_with_serial = [e for e in entries if e.get('serial_number')]
        canonical = entries_with_serial[0] if entries_with_serial else min(entries, key=lambda d: d['id'])
        duplicates = [e for e in entries if e['id'] != canonical['id']]

        updates = {}
        for dup in duplicates:
            if not canonical.get('serial_number') and dup.get('serial_number'):
                updates['serial_number'] = dup['serial_number']
            if not canonical.get('inventory_number') and dup.get('inventory_number'):
                updates['inventory_number'] = dup['inventory_number']

        if updates:
            inventory.update_device(canonical['id'], **updates)
            typer.secho(
                f"  ✓ Merged into ID {canonical['id']} ({hostname}): {updates}",
                fg=typer.colors.GREEN
            )
        else:
            typer.secho(
                f"  • No missing fields to merge for {hostname} (ID {canonical['id']})",
                fg=typer.colors.BLUE, dim=True
            )

        for dup in duplicates:
            inventory.delete_device(dup['id'])
            typer.secho(
                f"  ✗ Deleted duplicate ID {dup['id']} ({hostname}) "
                f"serial = {dup.get('serial_number') or '-'}, "
                f"inv = {dup.get('inventory_number') or '-'}",
                fg=typer.colors.YELLOW
            )

def sync_devices(device_list: List[Dict], active: bool = False) -> Dict[str, int]:
    """
    Sync a list of devices into the inventory, setting their active status.

    For each device:
    - If serial number exists in DB → update active flag
    - If not found → insert new record with given active flag

    Args:
        device_list: List of dicts like [{'SERIAL': [inventory_number_or_str, hostname_or_str]}, ...]
                     'None' strings are treated as NULL.
        active:      Active flag to set for all devices (default: False)

    Returns:
        Summary dict with counts: {'updated': n, 'added': n, 'errors': n}
    """
    summary = {'updated': 0, 'added': 0, 'errors': 0}

    for entry in device_list:
        for serial, (inv_raw, host_raw) in entry.items():
            try:
                def normalize(val) -> Optional[str]:
                    if val is None:
                        return None
                    s = str(val).strip()
                    return None if s.lower() == 'none' else s

                serial_norm    = normalize(serial)
                inventory_norm = normalize(inv_raw)
                hostname_norm  = normalize(host_raw)

                results = inventory.search_devices(serial_norm)
                match = next(
                    (d for d in results if d.get('serial_number') == serial_norm),
                    None
                )

                if match:
                    inventory.update_device(match['id'], active=active)
                    summary['updated'] += 1
                else:
                    inventory.add_device(
                        hostname=hostname_norm or serial_norm,
                        serial_number=serial_norm,
                        inventory_number=inventory_norm,
                        active=active
                    )
                    summary['added'] += 1

            except Exception as e:
                typer.secho(f"\u2717 Error processing entry {entry}: {e}", fg=typer.colors.RED, err=True)
                summary['errors'] += 1

    typer.secho(f"\n\u2713 Sync complete → updated: {summary['updated']}, "
          f"added: {summary['added']}, errors: {summary['errors']}", fg=typer.colors.GREEN)
    return summary

def add_devices_from_dict(devices_dict: Dict[str, List]) -> Dict[str, any]:
    """
    Add/update multiple devices from a dict of {hostname: [serial_number, inventory_number, status]}
    Only processes switch hostnames starting with 'rs', 'rh', 'rg', or 'rw'.
    
    Args:
        devices_dict: Dict mapping hostname to [serial_number, inventory_number, status]
        Examples:
            {'rgcs0006-1': ['SG42LMP0R2', '28411', 'active']}
            {'rggw1004sp-1': ['', None, 'active']}
            {'_V.G04.121.2_42': ['', None, 'inventory']}  → skipped (not a switch)
    
    Returns:
        Dictionary with statistics: {added, updated, reactivated, skipped, errors, details}
    """
    SWITCH_PREFIXES = ('rs', 'rh', 'rg', 'rw')

    results = {
        'added': 0,
        'updated': 0,
        'reactivated': 0,
        'skipped': 0,
        'errors': 0,
        'details': []
    }

    for hostname, values in devices_dict.items():
        # Only process switch hostnames
        if not hostname.lower().startswith(SWITCH_PREFIXES):
            results['skipped'] += 1
            results['details'].append({
                'hostname': hostname,
                'status': 'skipped',
                'reason': 'not a switch hostname'
            })
            continue

        # Unpack values, treating empty string as None
        serial_number   = values[0] if len(values) > 0 and values[0] != '' else None
        inventory_number = str(values[1]) if len(values) > 1 and values[1] is not None else None
        device_status   = values[2] if len(values) > 2 else 'offline'
        #is_active       = device_status != 'offline'
        is_active       = device_status == 'active'

        try:
            devices = inventory.get_devices_by_hostname(hostname, active_only=False)
            existing = devices[0] if devices else None

            if existing:
                needs_update = False
                updates = {}

                # Reactivate if currently inactive but shouldn't be
                if existing['active'] != is_active:
                    updates['active'] = is_active
                    needs_update = True

                # Update serial number if provided and different
                if serial_number and existing['serial_number'] != serial_number:
                    updates['serial_number'] = serial_number
                    needs_update = True

                # Update inventory number if provided and different
                if inventory_number and existing['inventory_number'] != inventory_number:
                    updates['inventory_number'] = inventory_number
                    needs_update = True

                if needs_update:
                    inventory.update_device(existing['id'], **updates)
                    was_reactivated = 'active' in updates and updates['active']
                    status = 'reactivated' if was_reactivated else 'updated'
                    results['reactivated' if was_reactivated else 'updated'] += 1
                    results['details'].append({
                        'hostname': hostname,
                        'serial_number': serial_number,
                        'inventory_number': inventory_number,
                        'status': status,
                        'changes': list(updates.keys()),
                        'id': existing['id']
                    })
                    color = typer.colors.CYAN if was_reactivated else typer.colors.YELLOW
                    #typer.secho(f"  ✓ {status.capitalize()}: {hostname} (ID: {existing['id']}, changes: {', '.join(updates.keys())})",
                    #            fg=color)
                    typer.secho(f"  ✓ {status.capitalize()}: {hostname} (ID: {existing['id']}, changes: {', '.join(f'{k}={v}' for k, v in updates.items())})",
                                fg=color)
                else:
                    results['skipped'] += 1
                    results['details'].append({
                        'hostname': hostname,
                        'status': 'already_exists',
                        'id': existing['id']
                    })
                    typer.secho(f"  • Skipped: {hostname} - already up to date",
                                fg=typer.colors.BLUE, dim=True)

            else:
                # Only add if we have at least some identifying data
                device_id = inventory.add_device(
                    hostname=hostname,
                    serial_number=serial_number,
                    inventory_number=inventory_number,
                    active=is_active
                )
                results['added'] += 1
                results['details'].append({
                    'hostname': hostname,
                    'serial_number': serial_number,
                    'inventory_number': inventory_number,
                    'status': 'added',
                    'id': device_id
                })
                typer.secho(f"  ✓ Added: {hostname} (Serial: {serial_number}, Inv: {inventory_number}, ID: {device_id})",
                            fg=typer.colors.GREEN)

        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                'hostname': hostname,
                'status': 'error',
                'error': str(e)
            })
            typer.secho(f"  ✗ Error processing {hostname}: {e}",
                        fg=typer.colors.RED, err=True)

    return results

if __name__ == "__main__":
    app()