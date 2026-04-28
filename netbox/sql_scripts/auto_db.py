#!/usr/bin/env python3
"""
Automatically manage 'devices' table in 'network_inventory' database
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

#@app.command()
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
    
    if not b_file.exists():
        typer.secho(f"✗ Backup file not found: {b_file}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    
    device_dict = load_yaml(b_file)
    
    typer.secho(f"\nSeeding database from {b_file.name}...", fg=typer.colors.CYAN, bold=True)
    typer.secho(f"Found {len(device_dict)} devices to process\n", fg=typer.colors.CYAN)
    
    results = add_devices_from_dict(device_dict)
    
    # Show summary
    typer.echo("\n" + "="*50)
    typer.secho("Seed Summary:", fg=typer.colors.CYAN, bold=True)
    typer.secho(f"  ✓ Added:      {results['added']}", fg=typer.colors.GREEN)
    typer.secho(f"  ↻ Updated:    {results['updated']}", fg=typer.colors.CYAN)
    typer.secho(f"  • Skipped:    {results['skipped']}", fg=typer.colors.BLUE)
    typer.secho(f"  ✗ Errors:     {results['errors']}", fg=typer.colors.RED)
    typer.echo("="*50)

def is_likely_serial_number(value: str) -> bool:
    """
    Determine if a value is likely a serial number vs inventory number
    
    Serial numbers typically:
    - Contain mix of letters and numbers
    - Are longer (usually 10+ characters)
    - Have specific vendor prefixes (FOC, SPE, CN, FDO, etc.)
    
    Inventory numbers typically:
    - Shorter format codes (HB-001199, CU-230327)
    - Have dashes or structured patterns
    - Pure numbers (12345)
    - Institution-specific prefixes
    
    Args:
        value: String to check
    
    Returns:
        True if likely a serial number, False if likely inventory number
    """
    if not value or not isinstance(value, str):
        return False
    
    value = value.strip()
    
    # Empty after strip
    if not value:
        return False
    
    # Pure numbers under 7 digits are likely inventory numbers
    if value.isdigit() and len(value) <= 6:
        return False
    
    # Common vendor serial number prefixes (definitive indicators)
    serial_prefixes = ['FOC', 'SPE', 'CN', 'FDO', 'FCH', 'JAE', 'SAD', 'CZ']
    if any(value.upper().startswith(prefix) for prefix in serial_prefixes):
        return True
    
    # Common inventory number patterns (institution-specific)
    # Format: 2-3 letters, dash, numbers (HB-001199, CU-230327)
    import re
    inventory_pattern = r'^[A-Z]{2,3}-\d+$'
    if re.match(inventory_pattern, value.upper()):
        return False
    
    # Serial numbers usually have letters and numbers mixed
    has_letters = any(c.isalpha() for c in value)
    has_numbers = any(c.isdigit() for c in value)
    
    # If it has both letters and numbers and is long enough, likely serial
    # Serial numbers are typically 10+ characters
    if has_letters and has_numbers and len(value) >= 10:
        return True
    
    # Shorter alphanumeric strings (less than 10 chars) are likely inventory
    if has_letters and has_numbers and len(value) < 10:
        return False
    
    # Default: if purely numeric, it's inventory
    if value.isdigit():
        return False
    
    # If we're unsure but it has letters, assume serial (conservative)
    return has_letters

def add_devices_from_dict(device_dict: Dict[str, List]) -> Dict[str, any]:
    """
    Add devices from a dictionary where keys are hostnames and values are [serial, inventory, state]
    """
    results = {
        'added': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'details': []
    }
    
    for hostname, values in device_dict.items():
        if not hostname.startswith('r'):
            results['skipped'] += 1
            typer.secho(
                f"  • Skipped: {hostname} - it is not a network device.",
                fg=typer.colors.BLUE, dim=True
            )
            continue

        try:
            # Parse values
            serial_number = values[0] if values[0] else None
            inventory_number = values[1] if len(values) > 1 and values[1] else None
            state = values[2] if len(values) > 2 else 'active'
            
            # Convert empty strings to None
            if serial_number == '':
                serial_number = None
            if inventory_number == '':
                inventory_number = None
            
            # Determine active status
            active = state.lower() in ['active', 'commissioned']
            
            # Smart duplicate checking
            if serial_number:
                # Check by hostname AND serial
                existing = inventory.get_device(hostname, serial_number, active_only=False)
            else:
                # No serial - check by hostname only
                hostname_devices = inventory.get_devices_by_hostname(hostname, active_only=False)
                existing = hostname_devices[0] if hostname_devices else None
            
            if existing:
                # Device exists - check if we need to update
                needs_update = False
                updates = {}
                update_details = []
                
                if existing['serial_number'] != serial_number:
                    updates['serial_number'] = serial_number
                    update_details.append(f"serial: {existing['serial_number']} → {serial_number}")
                    needs_update = True
                
                if existing['inventory_number'] != inventory_number:
                    updates['inventory_number'] = inventory_number
                    old_inv = existing['inventory_number'] or 'null'
                    new_inv = inventory_number or 'null'
                    update_details.append(f"inventory: {old_inv} → {new_inv}")
                    needs_update = True
                
                if existing['active'] != active:
                    updates['active'] = active
                    update_details.append(f"state: {existing['active']} → {active}")
                    needs_update = True
                
                if needs_update:
                    inventory.update_device(existing['id'], **updates)
                    results['updated'] += 1
                    changes = ", ".join(update_details)
                    typer.secho(
                        f"  ✓ Updated: {hostname} ({changes})",
                        fg=typer.colors.CYAN
                    )
                else:
                    results['skipped'] += 1
                    typer.secho(
                        f"  • Skipped: {hostname} - no changes needed",
                        fg=typer.colors.BLUE, dim=True
                    )
            else:
                # Device doesn't exist - add it
                device_id = inventory.add_device(
                    hostname=hostname,
                    serial_number=serial_number,
                    inventory_number=inventory_number,
                    active=active
                )
                results['added'] += 1
                
                status_emoji = "✓" if active else "○"
                status_text = "active" if active else "inactive"
                serial_display = serial_number if serial_number else "no serial"
                inv_display = inventory_number if inventory_number else "no inv"
                
                typer.secho(
                    f"  {status_emoji} Added: {hostname} ({serial_display}, {inv_display}, {status_text}, ID: {device_id})",
                    fg=typer.colors.GREEN if active else typer.colors.BLUE
                )
        
        except Exception as e:
            # Check if it's a duplicate key error
            error_str = str(e)
            if 'duplicate key' in error_str.lower() or 'already exists' in error_str.lower():
                results['skipped'] += 1
                typer.secho(
                    f"  • Skipped: {hostname} - already exists in database",
                    fg=typer.colors.BLUE, dim=True
                )
            else:
                results['errors'] += 1
                results['details'].append({
                    'hostname': hostname,
                    'status': 'error',
                    'error': str(e)
                })
                typer.secho(
                    f"  ✗ Error processing {hostname}: {e}",
                    fg=typer.colors.RED, err=True
                )
    
    return results

def add_devices_from_list(devices_list: List[Dict[str, str]]) -> Dict[str, any]:
    """
    Add multiple devices from a list of {hostname: value} dictionaries
    Auto-detects if value is serial_number or inventory_number
    
    Args:
        devices_list: List of dicts, each with one key-value pair {hostname: value}
    
    Returns:
        Dictionary with statistics
    """
    results = {
        'added': 0,
        'renamed': 0,
        'updated': 0,
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
        
        # Convert value to string if it's not already
        value_str = str(value) if value is not None else None
        
        # Determine if value is serial number or inventory number
        is_serial = is_likely_serial_number(value_str) if value_str else False
        
        if is_serial:
            serial_number = value_str
            inventory_number = None
            field_type = "Serial"
        else:
            serial_number = None
            inventory_number = value_str
            field_type = "Inventory"
        
        try:
            # Get all devices with this hostname
            hostname_devices = inventory.get_devices_by_hostname(hostname, active_only=False)
            
            if is_serial:
                # For serial numbers: check if exact match exists
                exact_match = inventory.get_device(hostname, serial_number, active_only=False)
                
                if exact_match:
                    # Exact match exists - just reactivate if needed
                    if not exact_match['active']:
                        inventory.update_device(exact_match['id'], active=True)
                        results['reactivated'] += 1
                        typer.secho(f"  ✓ Reactivated: {hostname} (Serial: {value_str})", 
                                   fg=typer.colors.YELLOW)
                    else:
                        results['skipped'] += 1
                        typer.secho(f"  • Skipped: {hostname} (Serial: {value_str}) - already exists", 
                                   fg=typer.colors.BLUE, dim=True)
                else:
                    # Different serial - need to handle old device(s)
                    if hostname_devices:
                        for old_device in hostname_devices:
                            old_serial = old_device['serial_number']
                            
                            if old_serial:
                                new_hostname = old_serial
                                
                                # Check if the new hostname already exists
                                existing_with_new_hostname = inventory.get_devices_by_hostname(
                                    new_hostname, active_only=False
                                )
                                
                                if existing_with_new_hostname:
                                    # Target hostname already exists
                                    # Check if it's the same device (same serial)
                                    same_device = any(
                                        d['serial_number'] == old_serial 
                                        for d in existing_with_new_hostname
                                    )
                                    
                                    if same_device:
                                        # It's already renamed, just mark as inactive
                                        typer.secho(
                                            f"  • Device already renamed: {hostname} → {new_hostname} (marking old as inactive)",
                                            fg=typer.colors.BLUE, dim=True
                                        )
                                        inventory.update_device(old_device['id'], active=False)
                                    else:
                                        # Different device exists with that hostname, need unique name
                                        new_hostname = f"{old_serial}_old_{old_device['id']}"
                                        typer.secho(
                                            f"  ⚠ Renaming: {hostname} → {new_hostname} (conflict resolved)",
                                            fg=typer.colors.MAGENTA
                                        )
                                        inventory.update_device(
                                            old_device['id'], 
                                            hostname=new_hostname,
                                            active=False
                                        )
                                        results['renamed'] += 1
                                else:
                                    # No conflict, rename as planned
                                    typer.secho(
                                        f"  ⚠ Renaming: {hostname} → {new_hostname} (preserving old serial)",
                                        fg=typer.colors.MAGENTA
                                    )
                                    inventory.update_device(
                                        old_device['id'], 
                                        hostname=new_hostname,
                                        active=False
                                    )
                                    results['renamed'] += 1
                            else:
                                # No serial - use ID suffix
                                new_hostname = f"{hostname}_old_{old_device['id']}"
                                typer.secho(
                                    f"  ⚠ Renaming: {hostname} → {new_hostname}",
                                    fg=typer.colors.MAGENTA
                                )
                                inventory.update_device(
                                    old_device['id'], 
                                    hostname=new_hostname,
                                    active=False
                                )
                                results['renamed'] += 1
                    
                    # Add new device
                    device_id = inventory.add_device(
                        hostname=hostname,
                        serial_number=serial_number,
                        active=True
                    )
                    results['added'] += 1
                    typer.secho(f"  ✓ Added: {hostname} (Serial: {value_str}, ID: {device_id})", 
                               fg=typer.colors.GREEN)
            
            else:
                # For inventory numbers: update existing device or add new
                if hostname_devices:
                    # Device exists - update inventory number
                    device = hostname_devices[0]  # Take first match
                    
                    if device['inventory_number'] != inventory_number:
                        inventory.update_device(device['id'], inventory_number=inventory_number)
                        results['updated'] += 1
                        typer.secho(f"  ✓ Updated: {hostname} (Inventory: {value_str})", 
                                   fg=typer.colors.CYAN)
                    else:
                        results['skipped'] += 1
                        typer.secho(f"  • Skipped: {hostname} (Inventory: {value_str}) - unchanged", 
                                   fg=typer.colors.BLUE, dim=True)
                else:
                    # No device exists - add new with inventory number
                    device_id = inventory.add_device(
                        hostname=hostname,
                        inventory_number=inventory_number,
                        active=True
                    )
                    results['added'] += 1
                    typer.secho(f"  ✓ Added: {hostname} (Inventory: {value_str}, ID: {device_id})", 
                               fg=typer.colors.GREEN)
                
        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                'hostname': hostname,
                field_type.lower(): value_str,
                'status': 'error',
                'error': str(e)
            })
            typer.secho(f"  ✗ Error processing {hostname}: {e}", 
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
    - If serial number exists in DB → update active flag and inventory number if different
    - If not found → insert new record with given active flag

    Args:
        device_list: List of dicts like [{'SERIAL': [inventory_number_or_str, hostname_or_str]}, ...]
                     'None' strings are treated as NULL.
        active:      Active flag to set for all devices (default: False)

    Returns:
        Summary dict with counts: {'updated': n, 'added': n, 'errors': n}
    """
    summary = {'updated': 0, 'added': 0, 'skipped': 0, 'errors': 0, 'inventory_updated': 0}

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

                # Search for device by serial number
                results = inventory.search_devices(serial_norm)
                match = next(
                    (d for d in results if d.get('serial_number') == serial_norm),
                    None
                )

                if match:
                    # Device exists - check what needs updating
                    updates = {}
                    update_msgs = []
                    
                    # Always update active flag
                    if match['active'] != active:
                        updates['active'] = active
                        update_msgs.append(f"active: {match['active']} → {active}")
                    
                    # Update inventory number if:
                    # 1. New inventory is provided (not None)
                    # 2. AND it's different from existing
                    if inventory_norm is not None:
                        existing_inv = match.get('inventory_number')
                        if existing_inv != inventory_norm:
                            updates['inventory_number'] = inventory_norm
                            old_inv_display = existing_inv if existing_inv else 'null'
                            update_msgs.append(f"inventory: {old_inv_display} → {inventory_norm}")
                            summary['inventory_updated'] += 1
                    
                    # Update hostname if provided and different
                    if hostname_norm is not None and hostname_norm != match['hostname']:
                        updates['hostname'] = hostname_norm
                        update_msgs.append(f"hostname: {match['hostname']} → {hostname_norm}")
                    
                    # Perform update if there are changes
                    if updates:
                        inventory.update_device(match['id'], **updates)
                        summary['updated'] += 1
                        
                        if update_msgs:
                            changes = ", ".join(update_msgs)
                            typer.secho(
                                f"  ✓ Updated: {match['hostname']} (Serial: {serial_norm}) - {changes}",
                                fg=typer.colors.CYAN
                            )
                        else:
                            typer.secho(
                                f"  ✓ Updated: {match['hostname']} (Serial: {serial_norm})",
                                fg=typer.colors.CYAN
                            )
                    else:
                        summary['skipped'] += 1
                        typer.secho(
                            f"  • Skipped: {match['hostname']} (Serial: {serial_norm}) - no changes",
                            fg=typer.colors.BLUE, dim=True
                        )
                else:
                    # Device not found - need to add it
                    # But first check if hostname=serial already exists to avoid duplicate
                    fallback_hostname = hostname_norm or serial_norm
                    
                    # Check if this exact hostname+serial combo exists
                    existing_with_hostname = std_app.inventory.get_device(
                        fallback_hostname, 
                        serial_norm, 
                        active_only=False
                    )
                    
                    if existing_with_hostname:
                        # This exact combo already exists - just update it
                        updates = {}
                        update_msgs = []
                        
                        if existing_with_hostname['active'] != active:
                            updates['active'] = active
                            update_msgs.append(f"active: {existing_with_hostname['active']} → {active}")
                        
                        if inventory_norm is not None:
                            existing_inv = existing_with_hostname.get('inventory_number')
                            if existing_inv != inventory_norm:
                                updates['inventory_number'] = inventory_norm
                                old_inv_display = existing_inv if existing_inv else 'null'
                                update_msgs.append(f"inventory: {old_inv_display} → {inventory_norm}")
                                summary['inventory_updated'] += 1
                        
                        if updates:
                            inventory.update_device(existing_with_hostname['id'], **updates)
                            summary['updated'] += 1
                            changes = ", ".join(update_msgs)
                            typer.secho(
                                f"  ✓ Updated existing: {fallback_hostname} (Serial: {serial_norm}) - {changes}",
                                fg=typer.colors.CYAN
                            )
                        else:
                            summary['skipped'] += 1
                            typer.secho(
                                f"  • Skipped: {fallback_hostname} (Serial: {serial_norm}) - already exists, no changes",
                                fg=typer.colors.BLUE, dim=True
                            )
                    else:
                        # Truly new device - add it
                        inventory.add_device(
                            hostname=fallback_hostname,
                            serial_number=serial_norm,
                            inventory_number=inventory_norm,
                            active=active
                        )
                        summary['added'] += 1
                        
                        inv_display = inventory_norm if inventory_norm else 'no inv'
                        typer.secho(
                            f"  ✓ Added: {fallback_hostname} (Serial: {serial_norm}, Inv: {inv_display})",
                            fg=typer.colors.GREEN
                        )

            except Exception as e:
                typer.secho(f"✗ Error processing entry {entry}: {e}", fg=typer.colors.RED, err=True)
                summary['errors'] += 1

    # Show summary
    typer.echo("\n" + "="*50)
    typer.secho("Sync Summary:", fg=typer.colors.CYAN, bold=True)
    typer.secho(f"  ✓ Updated:             {summary['updated']}", fg=typer.colors.CYAN)
    typer.secho(f"  ✓ Added:               {summary['added']}", fg=typer.colors.GREEN)
    typer.secho(f"  • Skipped:             {summary['skipped']}", fg=typer.colors.BLUE)
    typer.secho(f"  ↻ Inventory updated:   {summary['inventory_updated']}", fg=typer.colors.YELLOW)
    typer.secho(f"  ✗ Errors:              {summary['errors']}", fg=typer.colors.RED)
    typer.echo("="*50)
    
    return summary

def test_detection():
    """Test serial vs inventory detection"""
    test_cases = [
        # Serial numbers
        ('SPE192400AA', True, 'Serial'),
        ('FOC1749S09J', True, 'Serial'),
        ('FDO2433087X', True, 'Serial'),
        ('CN14KNN1VZ', True, 'Serial'),
        ('CN0BHKX2CM', True, 'Serial'),
        ('CZ00001', True, 'Serial'),
        ('ABC123DEF456', True, 'Serial'),
        
        # Inventory numbers
        ('HB-001199', False, 'Inventory'),
        ('CU-230327', False, 'Inventory'),
        ('18128', False, 'Inventory'),
        ('20059', False, 'Inventory'),
        ('123456', False, 'Inventory'),
        ('AB-12345', False, 'Inventory'),
        ('XYZ-999', False, 'Inventory'),
    ]
    
    print("Detection Tests:")
    print("-" * 60)
    for value, expected, label in test_cases:
        result = is_likely_serial_number(value)
        status = "✓" if result == expected else "✗"
        detected = "Serial" if result else "Inventory"
        print(f"{status} {value:20} → {detected:10} (expected: {label})")

@app.command()
def debug():
    "Run test cases for debugging"
    test_detection()

if __name__ == "__main__":
    app()