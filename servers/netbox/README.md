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
- `plugins.yaml` - install NetBox plugins on the remote server. You should then update the "PLUGINS" keyword in `configuration.py` and update NetBox by running the `install.yaml` playbook with `reboot: true` option.
- `restore_sql.yaml` - Restore PostgreSQL database from a backup dump file and archived media.
- `update_packages.yaml` - Update NetBox version and required Python packages locally.
- `update_server.yaml` - Debian server full system update & cleanup.

## Managing Python Versions with `pyenv`  

The server is based on **Debian 12**, which comes with **Python 3.11.2** by default. However, other distributions, such as **Arch Linux**, may have a newer version. Some required project dependencies may not be backward-compatible with older Python versions.  

To address this, we use **`pyenv`** to manage Python versions. This allows us to:  

1. Install **Python 3.11** within a controlled environment.  

    ```bash
    pyenv install -h 
    pyenv install -l # List all available versions to install
    pyenv install 3.11.2

    pyenv versions # Lists all versions available on the system
    ```

2. Set it as the default version for a specific directory where **Ansible update tasks** will run.  

### Useful `pyenv` Commands  

```bash
# Show available Python versions managed by pyenv
pyenv versions  

# Set a specific Python version for the current shell session
pyenv shell 3.11.2  

# Set a specific Python version for the current project directory (creates a .python-version file)
pyenv local 3.11.2  
```

By using **`pyenv local`**, the selected Python version will be automatically activated whenever you enter the designated project directory.  

## Fresh server install with Ansible

Development server, i.e `debian`. For production server, add `-e production=true` option.

1. Update Debian packages

    ```bash
    ansible-playbook playbooks/update_server.yaml
    ```

2. Collect required pip packages into a local repository

    ```bash
    ansible-playbook playbooks/update_repository.yaml
    ```

3. Install NetBox

    ```bash
    ansible-playbook playbooks/install.yaml
    ```

4. Create `admin` user on the NetBox platform

    ```bash
    ansible-playbook playbooks/create_admin.yaml
    ```

5. Restore SQL database.

    Specify the dump file date in `dump_file_date` variable in `restore_sql.yaml` playbook. And run:

    ```bash
    ansible-playbook playbooks/restore_sql.yaml
    
    # Usually a new install will require to copy the dump file from local machine
    ansible-playbook playbooks/restore_sql.yaml - e from_local=true
    ```

## Update NetBox

1. Download a new release and new Python packages locally

    [Netbox Releases](https://github.com/netbox-community/netbox/releases)

    Set the NetBox version in `host_vars/localhost/vars.yaml`

    Run the playbook that will download the specified version, create the requirements file and download pip packages:

    ```bash
    ansible-playbook playbooks/update_packages.yaml
    ```

2. Update the development server

    Playbook: `playbooks/install.yaml`

    ```bash
    ansible-playbook playbooks/update_server.yaml
    ansible-playbook playbooks/install.yaml
    ```

3. Backup production server database

    Playbook: `playbooks/backup_sql.yaml`

    Run the script (you'll have to authenticate several times):

    ```bash
    ansible-playbook playbooks/backup_sql.yaml
    ```

4. Update the production server

    Run the script:

    ```bash
    ansible-playbook playbooks/update_server.yaml -e production=true
    ansible-playbook playbooks/install.yaml -e production=true
    ```

5. All in one

```bash
ansible-playbook playbooks/update_repository.yaml
ansible-playbook playbooks/update_server.yaml
ansible-playbook playbooks/install.yaml

ansible-playbook playbooks/backup_sql.yaml
ansible-playbook playbooks/update_server.yaml -e production=true
ansible-playbook playbooks/install.yaml -e production=true
```
