# Ansible collection

A collection of Ansible inventories, playbooks, and tools designed to simplify network administration. It also includes some in-house developed Ansible tools and instructions for various tasks.

## Content

- `aruba` - an Ansible inventory and playbooks specifically designed for network administration of Aruba switches
- `netbox` - collect data from running-config files and upload it to a NetBox server, over Ansible.
- `servers` - playbooks for various Linux servers administration
- `tools` - some in-house developed Ansible tools that may be useful for network administrators
- `wiki` - instructions and how-to guides on various topics related to network administration with Ansible
- `yaml` - Testing YAML

## Update python virtual environment

```bash
sudo apt install python3.10-venv
cd /opt/ansible/
rm bin/ lib*
python3 -m venv /opt/ansible
ansible-init
```

## Update Ansible over pip

```bash
pip freeze | sed 's/==.*//' > requirements.txt
pip uninstall -r requirements.txt -y
pip cache purge
pip install -r requirements.txt --upgrade #&& rm requirements.txt
```

## Update Ansible collections with `ansible-galaxy`

- First generate the `requirements.yaml` file, by listing installed collections:

```bash
ansible-galaxy collection list | awk 'BEGIN{print "collections:"} NR>2 && NF==2 {print "  - name: "$1}' > requirements.yml
```

- Manually clean some redundant lines it creates.

Also check the collections path with:

```bash
ansible-galaxy collection list
```

It may be: `/opt/ansible/lib/python3.10/site-packages/ansible_collections`

Add it to a temporary variable `$a_path`

```bash
a_path='/opt/ansible/lib/python3.10/site-packages/ansible_collections'
```

- Install collections and dependencies to the right folder

```bash
ansible-galaxy collection install -r requirements.yml --upgrade -p $a_path && rm requirements.yml
```
