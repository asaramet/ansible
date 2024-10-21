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

### Playbooks (in `playbooks` folder)

- `backup_sql.yaml` - dump the Postgresql database and back it up to local host.
- `create_admin.yaml` - create a Django superuser on the remote server
- `install.yaml` - install the required apps and start NetBox on the server
- `pip_packages.yaml` - create a local python virtual environment and download required packages
- `plugins.yaml` - install NetBox plugins on the remote server. You should then update the "PLUGINS" keyword in `configuration.py` and update NetBox by running the `install.yaml` playbook with `reboot: true` option.
- `restore_sql.yaml` - Restore PostgreSQL database from a backup dump file and archived media.

## Download a release

  [Netbox Releases](https://github.com/netbox-community/netbox/releases)

  ```bash
  cd <FOLDER>/ansible/servers/netbox/src/
  wget https://github.com/netbox-community/netbox/archive/refs/tags/v<NEW_VERSION>.tar.gz
  ```
  
## Update NetBox

As example will take NetBox version: `4.0.9`

1. Check if requirements are updated or conformed in the corresponding file.

    i.e:  `src/requirements-{version}.txt`
    Ex:   `src/requirements-4.0.9.txt`

   NB: Don't forget to add NetBox plugins into new `requirements-x.x.x.txt` file.

2. Update/Download python packages.

    Playbook: `playbooks/pip_packages.yaml`
    Update variable in the playbook: `netbox_version`
      Ex: `netbox_version: 4.0.9`

    Run the script:

    ```bash
    pyenv shell 3.11.2
    ansible-playbook playbooks/pip_packages.yaml 
    ```

3. Run the install script on development server

    Playbook: `playbooks/install.yaml`
    Update variable in the playbook: `netbox_version`
      Ex: `netbox_version: &netbox_version 4.0.9`

    Set development variables. Ex:

    ```yaml
    server: &server debian12-ansible
    production: &production false
    ```

    Run the script:

    ```bash
    ansible-playbook playbooks/install.yaml
    ```

4. Backup production server database

    Playbook: `playbooks/backup_sql.yaml`

    Run the script (you'll have to authenticate several times):

    ```bash
    ansible-playbook playbooks/backup_sql.yaml
    ```

5. Update Linux packages

    ```bash
    ssh root@rzlx8750

      apt update
      apt upgrade
      apt autoremove
      reboot
    ```

6. Update the production server

    Playbook: `playbooks/install.yaml`
    Update variable in the playbook: `netbox_version`
      Ex: `netbox_version: &netbox_version 4.0.9`

    Set development variables. Ex:

    ```yaml
    server: &server hs_netbox 
    production: &production true
    ```

    Run the script:

    ```bash
    ansible-playbook playbooks/install.yaml
    ```
