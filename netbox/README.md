# NetBox Automation

Requirements:

1. API key from NetBox, found under `Admin` -> `API Tokens`.
2. Ansible NetBox collection:

    ```bash
    ansible-galaxy collection install netbox.netbox
    ```

3. Python packages

- pynetbox
- packaging
- tabulate

Install everything in a virtual environment:

```bash
#Create python venv
python -m venv venv
. venv/bin/activate

# install packages
pip install ansible
pip install pynetbox packaging tabulate
```

Or install globally on an Arch Linux:

```bash
sudo pacman -Syu python-pynetbox python-packaging
```

## Files and Folders

- Ansible inventory files:
  - `ansible.cfg` - ansible inventory configs
  - `hosts.ini` - hosts and host groups
  - `group_vars` - default group variables
  - `group_vars/xx/vault` - encrypted group variables
  - `~/.ssh/vault_pass_netbox` - password used to decrypt vault data, i.e:

    ```bash
    # view encrypted file content in plain text
    ansible-vault view group_vars/local/vault 

    # edit encrypted file
    ansible-vault edit group_vars/local/vault 
    ```

### Playbooks (in `playbooks` folder)

- `sync_data.yaml` - gather and distribute data. Config files mostly.
- `aruba_6xxx.yaml` - add Aruba 6100 and 6300 switches from config files to a NetBox platform.
- `hp_switches.yaml` - add HP switches to the NetBox platform.
- `stacks.yaml` - add Aruba stacked switches to the NetBox platform.
- `cisco.yaml` - add Cisco devices to the NetBox platform.

### Python scripts

- `pynetbox` - populate a NetBox server with the help of `pynetbox` library
  - `add_locations.py` - add collected locations data
  - `interfaces.py` - synchronize interfaces
  - `ips.py` - IP Address management functions
  - `lags.py` - LAG (Link Aggregation Group) management functions
  - `modules.py` - process modules
  - `nb.py` - in house `pynetbox` API session initialization
  - `pynetbox_functions.py` - project specific functions for `pynetbox` based apps
  - `switches.py` - process switches
  - `update_data.py` - populate the server
  - `vlans.py` - synchronize VLANs
- `pyyaml` - processing raw data
  - `sort_data.py` - Sort collected running config files according to the switch type
  - `aruba` - Collect Aruba devices data from config files and generate a yaml data file.
    - `extra_functions.py` - more functions used in multiple python scripts
    - `json_functions.py` - functions to return JSON objects for Aruba OS switches
    - `std_functions.py` - standard functions used in multiple python scripts
    - `yamerate.py` - Collect data from config files and generate the yaml data file.
  - `cisco` - Collect Cisco devices data from config files and generate a yaml data file.
    - `yamerate.py` - Collect data from config files and generate the yaml data file.
- `sql_scripts` - Manage devices Postgres database as well as the interaction with the NetBox data.
  - `devices_db.py` - Interact with 'devices' table in the Postgres database, over CLI.
  - `network_inventory.py` - NetworkInventory class to interact with the network_inventory PostgreSQL database.
