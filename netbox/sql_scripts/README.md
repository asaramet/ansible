# Network Inventory Management System

A comprehensive suite of tools for managing network device inventory, synchronizing between NetBox and PostgreSQL databases, and handling device data efficiently.

---

## 📁 Project Structure

```
.
├── auto_db.py              # Automated device management from YAML files
├── backup_database.py      # Database backup and restore utilities
├── devices_db.py           # CLI for direct device table management
├── network_inventory.py    # PostgreSQL database access class
├── std_objs.py            # Standard objects and utility functions
├── netbox_to_db_sync.py   # NetBox ↔ PostgreSQL synchronization
├── pynetbox/
│   ├── nb.py              # NetBox API session initialization
│   └── pynetbox_functions.py # NetBox-specific utility functions
├── vault/                 # Ansible vault files for credentials
└── README_netbox_to_db_sync.md  # Detailed docs for sync tool
```

---

## 🎯 Core Components

### 1. **network_inventory.py** - Database Access Layer

The foundation of the system. Provides the `NetworkInventory` class for secure PostgreSQL database operations.

**Features:**
- Secure password handling (vault, env, config)
- CRUD operations for devices table
- Search and filtering capabilities

**Usage:**
```python
from network_inventory import NetworkInventory

inventory = NetworkInventory(
    host='localhost',
    password_from='vault',
    vault_file='path/to/vault',
    vault_password_file='path/to/vault_pass'
)

# Add a device
device_id = inventory.add_device(
    hostname='router1',
    serial_number='SPE123456',
    inventory_number='HB-001234',
    active=True
)

# Get all devices
all_devices = inventory.get_all_devices()
```

---

### 2. **std_objs.py** - Standard Objects & Utilities

Provides common utilities and pre-configured objects used across the project.

**Key Functions:**
- `initialize_inventory()` - Initialize database connection
- `get_inventory_connection()` - Get a new inventory connection
- `get_devices_numbers()` - Get devices as {hostname: number} dict
- `load_yaml()` - Load YAML files

---

### 3. **pynetbox/** - NetBox Integration

#### **nb.py**
Pre-configured NetBox API sessions for development and production servers.

**Usage:**
```python
from nb import development, production

nb = development  # or production
nb.http_session.verify = False  # Disable SSL verification
```

#### **pynetbox_functions.py**
Advanced NetBox utility functions for bulk operations.

**Key Functions:**
- `_cache_devices()` - Cache devices by hostname in bulk
- `_bulk_create()` - Bulk create objects with chunking
- `_bulk_update()` - Bulk update objects with chunking
- `_manufacturer()` - Get or create manufacturer
- `_resolve_or_create()` - Generic get-or-create function

---

### 4. **auto_db.py** - YAML-Based Device Management

Automates device management in the PostgreSQL database from YAML files.

**Commands:**
```bash
# Add devices from serial numbers YAML
python auto_db.py serials

# Add devices from inventory numbers YAML
python auto_db.py invs

# Sync delisted devices from YAML
python auto_db.py delist

# Add extra/unknown devices from YAML
python auto_db.py extra

# Merge duplicate entries
python auto_db.py merge

# Seed database from backup YAML
python auto_db.py seed

# Debug serial vs inventory detection
python auto_db.py debug
```

**Features:**
- Auto-detection of serial vs inventory numbers
- Conflict resolution (renames devices with different serials)
- Duplicate merging
- Dry-run support

---

### 5. **devices_db.py** - Interactive CLI for Device Management

Rich CLI interface for managing devices in the database.

**Commands:**
```bash
# List all devices
python devices_db.py list

# List active devices only
python devices_db.py list --active

# Search devices
python devices_db.py search --pattern "router"

# Get device count
python devices_db.py count

# Show devices with/without serial numbers
python devices_db.py serials [--missing]

# Show devices with/without inventory numbers
python devices_db.py invs [--missing]

# Show delisted devices
python devices_db.py delist

# Show duplicates
python devices_db.py duplicates [--serial] [--hostname]
```

**Features:**
- Rich table output with colors
- Filtering by active status
- Pattern searching
- Duplicate detection

---

### 6. **backup_database.py** - Database Backup & Restore

Handles database backup and restore operations using `pg_dump` and `pg_restore`.

**Commands:**
```bash
# Create backup (auto-named with date)
python backup_database.py backup

# Create backup to specific file
python backup_database.py backup --output my_backup.sql

# Restore from latest backup
python backup_database.py restore

# Restore from specific file
python backup_database.py restore --input my_backup.sql

# List available backups
python backup_database.py list

# Delete old backups
python backup_database.py cleanup --days 30
```

**Features:**
- Automatic backup naming with dates
- Backup directory management
- Compression support
- Retention policies

---

### 7. **netbox_to_db_sync.py** - NetBox ↔ PostgreSQL Synchronization

**The newest addition:** Synchronizes device data from NetBox to PostgreSQL database.

**Commands:**
```bash
# Test synchronization (dry run)
python netbox_to_db_sync.py sync --dry-run --verbose

# Apply synchronization
python netbox_to_db_sync.py sync

# Extract devices to YAML
python netbox_to_db_sync.py extract --output-file devices.yaml

# Compare NetBox vs PostgreSQL
python netbox_to_db_sync.py compare --show-matches
```

**Features:**
- Bulk extraction with minimal HTTP requests
- Smart device matching (hostname + serial + inventory)
- Conflict resolution (renames devices with different serials)
- Field mapping (NetBox `asset_tag` → SQL `inventory_number`)
- Automatic filtering (capital letter hostnames, None values)

**Matching Priority:**
1. Exact: hostname + serial + inventory
2. Serial: hostname + serial
3. Inventory: hostname + inventory
4. Hostname only

See [README_netbox_to_db_sync.md](README_netbox_to_db_sync.md) for detailed documentation.

---

## 🔧 Setup & Configuration

### Prerequisites

```bash
# Install required packages
pip install psycopg-binary pyyaml pynetbox typer rich

# For PostgreSQL (system package)
sudo pacman -Sy postgresql  # Arch Linux
sudo apt install postgresql-client  # Debian/Ubuntu
```

### NetBox API Token

Create an API token in NetBox with read access to devices, then add it to your vault file.

### Database Credentials

Configure database credentials in one of these ways:
1. **Vault (recommended)**: Add to `group_vars/localhost/vault`
2. **Environment**: `export DB_PASSWORD='your_password'`
3. **Config file**: Create a YAML config file

---

## 📊 Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   NetBox        │────▶│ netbox_to_db_   │────▶│   PostgreSQL    │
│   Platform      │     │   sync.py       │     │   Database      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
       ▲                   ▲   ▲   ▲                     ▲
       │                   │   │   └─────────────────────┘
       │                   │   │
       │                   │   └────── YAML files
       │                   │
       │                   └────── auto_db.py
       │
       └────────────────────────────── pynetbox_functions.py

YAML Files:
├── data/yaml/
│   ├── serial_numbers.yaml
│   ├── inv_numbers.yaml
│   ├── delisted.yaml
│   ├── extra.yaml
│   └── backup_db.yaml
└── src/numbers/
    ├── serial_numbers.yaml
    └── inv_numbers.yaml
```

---

## 🚀 Quick Start

### 1. Initialize and Test

```bash
# Test database connection
python -c "from network_inventory import NetworkInventory; print('DB OK')"

# Test NetBox connection
python -c "from nb import development; print(list(development.dcim.devices.all())[:5])"
```

### 2. Extract from NetBox

```bash
# Dry run first
python netbox_to_db_sync.py sync --dry-run --verbose

# Apply changes
python netbox_to_db_sync.py sync
```

### 3. Import from YAML

```bash
# Add serial numbers
python auto_db.py serials

# Add inventory numbers
python auto_db.py invs
```

### 4. Verify

```bash
# List all devices
python devices_db.py list

# Check for duplicates
python devices_db.py duplicates
```

---

## 🔒 Security Notes

- **SSL Verification**: Disabled for NetBox connections (configure in `nb.py`)
- **Passwords**: Stored in Ansible vault, never in plain text
- **Database**: Uses `psycopg` with secure connection handling
- **API Tokens**: Read-only tokens recommended for NetBox access

---

## 📝 File Formats

### YAML Device Format (for auto_db.py)

```yaml
# serial_numbers.yaml - {hostname: serial_number}
router1: SPE123456
switch2: FOC789012

# inv_numbers.yaml - {hostname: inventory_number}
router1: HB-001234
switch2: CU-230327

# delisted.yaml - [{serial: [inventory, hostname, state]}, ...]
SPE123456: [HB-001234, router1, delisted]

# backup_db.yaml - {hostname: [serial, inventory, state]}
router1: [SPE123456, HB-001234, active]
```

---

## 🐛 Troubleshooting

### Common Issues

**"Cannot reach host"**
- Check NetBox server URL in `nb.py`
- Verify network connectivity
- Check SSL verification settings

**"Connection refused" (PostgreSQL)**
- Verify database is running
- Check host/port in `network_inventory.py`
- Verify credentials

**"AttributeError" on device fields**
- Some NetBox fields may be None
- Use `hasattr()` or `getattr()` with defaults

**Slow performance**
- Use bulk operations (`_bulk_create`, `_bulk_update`)
- Avoid N+1 queries
- Use `--active-only` flag to reduce data

---

## 📞 Support & Contribution

This is an internal tool suite for network inventory management. For issues or feature requests, contact the development team.

---

## 📄 License

Internal use only. Do not distribute outside the organization.

---

## 🎯 Quick Reference Table

| Task | Command |
|------|---------|
| Sync NetBox → DB | `python netbox_to_db_sync.py sync` |
| Dry run sync | `python netbox_to_db_sync.py sync --dry-run` |
| List devices | `python devices_db.py list` |
| Add serials from YAML | `python auto_db.py serials` |
| Add invs from YAML | `python auto_db.py invs` |
| Backup DB | `python backup_database.py backup` |
| Restore DB | `python backup_database.py restore` |
| Check duplicates | `python devices_db.py duplicates` |
| Merge duplicates | `python auto_db.py merge` |
