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

Install everything in a virtual environment:

```bash
#Create python venv
python -m venv venv
. venv/bin/activate

# install packages
pip install ansible
pip install pynetbox packaging
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
  - `~/.ssh/vault_pass` - password used to decrypt vault data, i.e:

    ```bash
    # view encrypted file content in plain text
    ansible-vault view group_vars/local/vault 

    # edit encrypted file
    ansible-vault edit group_vars/local/vault 
    ```

### Playbooks (in `playbooks` folder)

- `sync_data.yaml` - gather and distribute data. Config files mostly.
- `aruba_6100.yaml` - add aruba 6100 switches from config files to a NetBox platform.
- `hp_switches.yaml` - add HP switches to a NetBox platform.

### Python scripts

- `std_functions.py` - standard functions used in multiple python scripts.
- `yaml_aruba_6100.py` - Collect Aruba 6100 data from config files and generate a yaml data file.
- `yaml_procurve.py` - Collect ProCurve and old HP modular and single switches data from config files and generate a yaml data file.
