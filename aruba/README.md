# Aruba Switch Network Administration with Ansible

This project provides Ansible inventory and playbooks specifically designed for network administration of Aruba switches. It is based on the [AOS-CX Ansible Collection](https://developer.arubanetworks.com/aruba-aoscx/docs/getting-started-with-ansible-and-aos-cx)

## Table of Contents

- [AOS-CX Ansible Collection](#aos-cx-ansible-collection)
- [Inventory](#inventory)
- [Playbooks](#playbooks)
  - [Backup switch configuration](#backup-switch-configuration)
  - [Day zero switch configuration](#day-0-switch-configuration)
  - [Show commands on switch](#show-commands)
  - [Upload switch firmware](#upload-switch-firmware)
- [License](#license)
- [Credits](#credits)

## AOS-CX Ansible Collection

In Ansible, collections are designed to build up and distribute content that can include playbooks, roles, modules, and plugins. Standard and user collections can be installed through a distribution server such as Ansible Galaxy.

Official Aruba Ansible AOS-CX modules are packed in [AOS-CX Ansible Collection](https://developer.arubanetworks.com/aruba-aoscx/docs/using-the-aos-cx-ansible-collection) and hosted on a [GitHub public repository](https://github.com/aruba/aoscx-ansible-collection)

The Ansible Galaxy distribution server will be a nice tool to install an maintain the collection.

### Install the AOS-CX Collection with Ansible Galaxy distribution tool

1. Check the right path to `collections` folder

    ```bash
    ansible-galaxy collection list

    # /opt/ansible/lib/python3.9/site-packages/ansible_collections
    Collection                    Version
    ----------------------------- -------
    ....
    ```

2. Install the collection

    ```bash
    ansible-galaxy collection install arubanetworks.aoscx -p /opt/ansible/lib/python3.9/site-packages/ansible_collections 
    ```

3. Update the collection

    ```bash
    ansible-galaxy collection install -U arubanetworks.aoscx -p /opt/ansible/lib/python3.9/site-packages/ansible_collections 
    ```

## Inventory

This Ansible inventory contains switches grouped into `sm_6100` and `hze_6100` -> `aruba_6100` -> `aruba groups`. Linux manager servers are in the `linux` group. Sensitive data such as passwords are stored with `ansible-vault` in `host_vars/host/vault`.

To view the inventory, use the following command:

```bash
ansible-inventory --graph
```

For a more detailed output, with variables, use:

```bash
ansible-inventory --graph --vars
```

## Playbooks

Ansible Playbooks allows repeatable execution of predefined Ansible commands over multiple hosts, therefore offering a simple-configuration multi-machine management, maintenance and deployment system.

The following playbooks are included in this repository:

For executing a playbook, use the following command:

```bash
ansible-playbook [OPTIONS] playbook-name.yaml

# For example to run show.yaml playbook in this inventory:
ansible-playbook playbooks/show.yaml
```

### Backup switch configuration

File: `playbooks/backup_config.yaml`

This Ansible playbook file is designed to perform two main tasks: backup the running configuration of Aruba switches specified under the `aruba` host group, and copy the resulting config files to a remote machine specified under the `rhlx99` host group.

The first task, titled `Backup 'running-config' into a local folder`, is executed on the `aruba` hosts and utilizes the Aruba Networks AOS-CX collection. The playbook creates a new subfolder within a specified work directory, named after the group to which each switch belongs. It then backs up the running configuration of each switch into its corresponding group subfolder.

The second task, titled `Copy config files to rhlx99`, is executed on the `rhlx99` host and involves copying the previously backed-up config files from the local directory to the remote machine's `tftpboot/` directory. The playbook uses the `copy` module to accomplish this, and sets the necessary file permissions and ownerships.

Overall, this playbook can be used to streamline network configuration management tasks by automating the backup and transfer of configuration files across multiple Aruba switches and a remote machine.

### Day 0 switch configuration

File: `playbooks/day_0_config.yaml`

This playbook has three main sections:

1. Set global variables: This section defines a global variable `work_dir` which is set to `/opt/ansible/inventories/aruba/` using a YAML anchor and alias. It runs on the `localhost` host.

2. Generate config file for Aruba 6100 switches from Jinja template: This section runs on the `new_6100` hosts and generates a configuration file from a Jinja2 template. It creates a subfolder in `work_dir` for each group of hosts and saves the generated file in that subfolder with the hostname as the filename.

3. Copy generated config files to a Linux server and Upload configuration to switches: These two sections run on the `rhlx99` and `new_6100` hosts, respectively. The `rhlx99` section copies the generated config files to the `/tftpboot/` directory on the `rhlx99` host, and the `new_6100` section uploads the configuration file to each `new_6100` host using the `aoscx_config` module from the `arubanetworks.aoscx` collection.

Overall, this playbook generates configuration files for Aruba 6100 switches, copies them to a Linux server, and then uploads them to the appropriate switches.

### Show commands

File: `playbooks/show.yaml`

This Ansible playbook file is designed to run a series of `show` commands on all Aruba switches specified under the `aruba` host group. The playbook utilizes the Aruba Networks AOS-CX collection, and sets the `ansible_connection` variable to `network_cli`. The playbook then executes, as an example, the `show vlan` command on the switch, and registers the output to a variable called `show_vlan_output`. Finally, the playbook displays the registered standard output using the `debug` module and the `show_vlan_output.stdout` variable.

Overall, this playbook can be used to quickly retrieve information about the VLAN configuration on multiple Aruba switches, streamlining network management and troubleshooting tasks.

### Upload switch firmware

File: `playbooks/6100_upload_firmware.yaml`

This playbook is designed for updating firmware on Aruba 6100 switches through CLI commands. Here's a breakdown of the different tasks:

1. Create group subfolder: This task creates a subfolder for the switches in the inventory group if it doesn't already exist.

2. Backup and save current running configs to startup-config: This task uses the `aoscx_config` module to backup the current running config to the `startup-config` file.

3. Upload firmware to primary partition: This task uploads the firmware file to the primary partition using the `aoscx_config` module. The before section of the module is used to backup the primary partition to the secondary partition before the firmware upload.

4. Boot into primary partition: This task boots the switch into the primary partition using the `aoscx_boot_firmware` module.

Overall, this playbook should work as intended for updating the firmware on Aruba 6100 switches.

## License

This project is licensed under the MIT License. See the LICENSE.md file for more information.

## Credits

This project uses the following third-party resources:

- [Ansible](https://www.ansible.com/) - for configuration management and automation of Aruba switches
- [GitHub](https://github.com/) - for source code hosting and collaboration tools
