# Network Inventory PostgreSQL Database

Scripts to interact with the `network_inventory` PostgreSQL database on the NetBox server.

## Overview

This database is **separate from NetBox's main database** and is used for manual tracking of network devices with additional inventory metadata.

**Database**: `network_inventory`
**User**: `netzadmin`
**Table**: `devices`

### Schema

| Column                | Type          | Description                                   |
|-----------------------|---------------|-----------------------------------------------|
| `id`                  | SERIAL        | Primary key (auto-increment)                  |
| `hostname`            | VARCHAR(255)  | Device hostname or FQDN (unique, required)    |
| `serial_number`       | VARCHAR(100)  | Manufacturer serial number (nullable)         |
| `inventory_number`    | VARCHAR(100)  | Internal inventory tracking number (nullable) |
| `active`              | BOOLEAN       | Device active status (default: true)          |
| `created_at`          | TIMESTAMP     | Record creation timestamp                     |
| `updated_at`          | TIMESTAMP     | Last update timestamp                         |

**Note**: Empty strings (`''`) for `serial_number` and `inventory_number` are automatically converted to `NULL` by the Python script to maintain data quality. Use `NULL`/`None` to indicate unknown or missing values.

---

## Prerequisites

### For Python Script

```bash
pip install psycopg2-binary pyyaml typer
```

### For CLI Tool

- `psql` command-line tool (included with PostgreSQL client)
- `bash` shell

---

## Secure Password Handling

**IMPORTANT**: Never hardcode passwords in scripts or commit them to git!

### Recommended Methods

#### 1. Environment Variable (Default & Most Common)

Store password in environment variable `DB_PASSWORD`:

```bash
# Temporary (current session only)
export DB_PASSWORD='your_password'
python network_inventory_example.py

# Or inline
DB_PASSWORD='your_password' python network_inventory_example.py
```

**Python usage:**

```python
inv = NetworkInventory(host='localhost')  # Uses DB_PASSWORD by default
```

#### 2. Ansible Vault (Recommended - Integrates with existing setup)

Uses your existing Ansible vault configuration:

```python
inv = NetworkInventory(
    host='localhost',
    password_from='vault',
    vault_file='group_vars/local/vault',  # or group_vars/hs_netbox/vault
    vault_password_file='~/.ssh/vault_pass_netbox'  # Default location
)
```

The vault file must contain `vault_sql_inventory_pass` variable.

#### 3. Config File (With restricted permissions)

Create `db_config.yaml` from the example:

```bash
cp db_config.yaml.example db_config.yaml
chmod 600 db_config.yaml  # Restrict permissions
# Edit db_config.yaml with your password
```

**Python usage:**

```python
inv = NetworkInventory(
    password_from='config',
    config_file='sql_scripts/db_config.yaml'
)
```

**Note**: `db_config.yaml` is in `.gitignore` to prevent accidental commits.

---

## Usage Examples

### CLI Tool (`inventory_cli.sh`)

#### Available Commands

```bash
DB_PASSWORD='pass' ./inventory_cli.sh [command] [arguments]

Commands:
  connect              # Interactive database connection
  add                  # Add new device
  list                 # List all devices
  list-active          # List only active devices
  get                  # Get device by hostname
  update               # Update device field
  deactivate           # Mark device as inactive
  delete               # Delete device
  search               # Search devices by term
  count                # Show device statistics
  help                 # Show help
```

#### Examples

```bash
# List all devices
DB_PASSWORD='your_pass' ./inventory_cli.sh list

# List only active devices
DB_PASSWORD='your_pass' ./inventory_cli.sh list-active

# Add new device
DB_PASSWORD='your_pass' ./inventory_cli.sh add router01.local SN12345 INV-001 true

# Get specific device
DB_PASSWORD='your_pass' ./inventory_cli.sh get router01.local

# Update device field
DB_PASSWORD='your_pass' ./inventory_cli.sh update router01.local serial_number SN99999

# Search devices
DB_PASSWORD='your_pass' ./inventory_cli.sh search switch

# Mark device inactive (soft delete)
DB_PASSWORD='your_pass' ./inventory_cli.sh deactivate old-device.local

# Delete device permanently
DB_PASSWORD='your_pass' ./inventory_cli.sh delete old-device.local

# Show statistics
DB_PASSWORD='your_pass' ./inventory_cli.sh count

# Interactive connection
DB_PASSWORD='your_pass' ./inventory_cli.sh connect
```

---

### Python Script (`network_inventory_example.py`)

#### Basic Usage with Secure Password

**Method 1: Environment Variable (Recommended)**

```bash
# Run with environment variable
DB_PASSWORD='your_password' python network_inventory_example.py
```

```python
from network_inventory_example import NetworkInventory

# Initialize connection (uses DB_PASSWORD environment variable)
inv = NetworkInventory(host='localhost')

# Add devices
inv.add_device('switch01.local', serial_number='SN67890',
               inventory_number='INV-001', active=True)

# Get all active devices
devices = inv.get_all_devices(active_only=True)
for device in devices:
    print(f"{device['hostname']}: {device['serial_number']}")

# Get specific device
device = inv.get_device('switch01.local')

# Update device
inv.update_device('switch01.local', inventory_number='INV-999')

# Search devices
results = inv.search_devices('switch')

# Mark inactive
inv.mark_inactive('old-device.local')

# Delete device
inv.delete_device('old-device.local')
```

**Method 2: Ansible Vault**

```python
# Uses existing Ansible vault
inv = NetworkInventory(
    host='localhost',
    password_from='vault',
    vault_file='group_vars/local/vault'
)
```

**Method 3: Config File**

```python
# Uses YAML config file
inv = NetworkInventory(
    password_from='config',
    config_file='sql_scripts/db_config.yaml'
)
```

#### Remote Connection

```python
# Connect to remote server (with environment variable)
inv = NetworkInventory(
    host='netbox.example.com',
    port=5432
)

# Or with Ansible vault
inv = NetworkInventory(
    host='netbox.example.com',
    port=5432,
    password_from='vault',
    vault_file='group_vars/hs_netbox/vault'
)
```

---

### Direct SQL Access

```bash
# Interactive connection
PGPASSWORD='your_pass' psql -h localhost -U network_inventory -d network_inventory

# Execute single query
PGPASSWORD='your_pass' psql -h localhost -U network_inventory -d network_inventory \
  -c "SELECT * FROM devices WHERE active = TRUE;"

# Remote connection
PGPASSWORD='your_pass' psql -h netbox.example.com -p 5432 -U network_inventory -d network_inventory
```

#### Common SQL Queries

```sql
-- List all devices
SELECT * FROM devices ORDER BY hostname;

-- Active devices only
SELECT * FROM devices WHERE active = TRUE;

-- Count devices
SELECT COUNT(*) FROM devices;

-- Search by hostname pattern
SELECT * FROM devices WHERE hostname LIKE '%switch%';

-- Recently added devices
SELECT * FROM devices ORDER BY created_at DESC LIMIT 10;

-- Recently updated devices
SELECT * FROM devices ORDER BY updated_at DESC LIMIT 10;
```

---

## Remote Access

To access the database from a remote machine, ensure:

1. PostgreSQL allows remote connections (configured in `postgresql.conf` and `pg_hba.conf`)
2. Firewall allows traffic on PostgreSQL port (default: 5432)
3. Use the server's hostname/IP in connection parameters

```bash
# Example remote connection
DB_PASSWORD='pass' psql -h netbox-server.example.com -p 5432 -U network_inventory -d network_inventory
```

---

## Security Notes

- Store passwords securely (use environment variables or secrets management)
- The `network_inventory` user has access **only** to the `network_inventory` database
- This database is completely isolated from NetBox's `netbox` database
- Use strong passwords stored in Ansible vault for server deployments
