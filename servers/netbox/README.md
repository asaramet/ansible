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
- `debug.yaml` - Some debugging and testing
- `deploy_cert.yaml` - Deploy a TTL/SSL server certificate
- `install_postgresql.yaml` - install and init PostgreSQL on the server
- `install.yaml` - install the required apps and start NetBox on the server
- `network_inventory.yaml` - create the NetBox inventory database used for managing manually inserted data
- `pgadmin_config.yaml` - Configure installed pgAdmin 4 web server
- `pgadmin_install.yaml` - Install pgAdmin 4 web server
- `plugins.yaml` - install NetBox plugins on the remote server. You should then update the "PLUGINS" keyword in `configuration.py` and update NetBox by running the `install.yaml` playbook with `reboot: true` option.
- `restore_sql.yaml` - Restore PostgreSQL database from a backup dump file and archived media.
- `update_packages.yaml` - Update NetBox version and required Python packages locally.
- `update_server.yaml` - Debian server full system update & cleanup.

## Managing Python Versions with `pyenv`  

The server is based on **Debian 12**, which comes with **Python 3.11.2** by default. However, other distributions, such as **Arch Linux**, may have a newer version. Some required project dependencies may not be backward-compatible with older Python versions.  

To address this, we use **`pyenv`** to manage Python versions. This allows us to:  

1. Install **Python 3.13** within a controlled environment.  

    ```bash
    pyenv install -h 
    pyenv install -l # List all available versions to install
    pyenv install 3.13

    pyenv versions # Lists all versions available on the system
    ```

2. Set it as the default version for a specific directory where **Ansible update tasks** will run.  

### Useful `pyenv` Commands  

```bash
# Show available Python versions managed by pyenv
pyenv versions  

# Set a specific Python version for the current shell session
pyenv shell 3.13

# Set a specific Python version for the current project directory (creates a .python-version file)
pyenv local 3.13
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

## Install and configure pgAdmin on the same server

Install pgAdmin packages:

```bash
ansible-playbook playbooks/pgadmin_install.yaml # for the local, dev server
ansible-playbook playbooks/pgadmin_install.yaml -e production=true
```

Configure and init pgAdmin service, database and admin user

You will have to init the database, with the admin user credentials, manually:

```bash
sudo -u www-data HOME=/tmp /usr/pgadmin4/venv/bin/python3 /usr/pgadmin4/web/setup.py setup-db
```

```bash
ansible-playbook playbooks/pgadmin_config.yaml # for the local, dev server
ansible-playbook playbooks/pgadmin_config.yaml -e production=true
```

## Update to a new PostgreSQL version

For example from 15 to 17. On the server both versions are already installed:

```bash
apt list -i | grep post

WARNING: apt does not have a stable CLI interface. Use with caution in scripts.

postgresql-15/now 15.14-0+deb12u1 amd64 [installed,local]
postgresql-17/stable,now 17.7-0+deb13u1 amd64 [installed,automatic]
postgresql-client-15/now 15.14-0+deb12u1 amd64 [installed,local]
postgresql-client-17/stable,now 17.7-0+deb13u1 amd64 [installed,automatic]
postgresql-client-common/stable,now 278 all [installed,automatic]
postgresql-common-dev/stable,now 278 all [installed,automatic]
postgresql-common/stable,now 278 all [installed,automatic]
postgresql/stable,now 17+278 all [installed]
```

But only cluster v 15 is active:

```bash
pg_lsclusters
Ver Cluster Port Status Owner    Data directory              Log file
15  main    5432 online postgres /var/lib/postgresql/15/main /var/log/postgresql/postgresql-15-main.log
```

0. Stop the service

    ```bash
    systemctl status postgresql
    systemctl stop postgresql
    ```

1. Upgrade the cluster from 15 to 17

    ```bash
    pg_upgradecluster 15 main
    ```

    This will:

    - Create a new PostgreSQL 17 cluster
    - Migrate all data, users, and databases from version 15 to 17
    - The new cluster may use port 5433 by default (since 5432 is ocupied by the old cluster)
    - Stop the old version 15 cluster

2. Verify both clusters exist:

    ```bash
    pg_lsclusters 
    Ver Cluster Port Status Owner    Data directory              Log file
    15  main    5433 down   postgres /var/lib/postgresql/15/main /var/log/postgresql/postgresql-15-main.log
    17  main    5432 online postgres /var/lib/postgresql/17/main /var/log/postgresql/postgresql-17-main.log
    ```

3. Drop the old version 15 cluster

    ```bash
    pg_dropcluster 15 main
    ```

4. Change PostgreSQL 17 to use port 5432

    ```bash
    pg_ctlcluster 17 main stop
    sed -i 's/port = 5433/port = 5432/' /etc/postgresql/17/main/postgresql.conf
    pg_ctlcluster 17 main start
    ```

5. Remove PostgreSQL 15 packages

    ```bash
    apt purge postgresql-15 postgresql-client-15
    apt autoremove
    ```

6. Starte posgresql service

    ```bash
    systemctl start postgresql
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
