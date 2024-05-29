# NetBox VM Server with Ansible

Create and administer a NetBox App on a remote server through ansible.

OS: Debian 12 (05.2024)

Packages:

- PostgreSQL Database
- Redis
- NetBox

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

- `src` directory - server specific data used in ansible playbooks
- `pip_packages` - temporary folder to keep last downloaded pip packages. Used by `pip_packages.yaml` script
- Playbooks (in `playbooks` folder)
  - `create_admin.yaml` - create a Django superuser on the remote server
  - `install.yaml` - install the required apps and start NetBox on the server
  - `pip_packages.yaml` - create a local python virtual environment and download required packages
  - `plugins.yaml` - install NetBox plugins on the remote server
