# Aruba Switch Network Administration with Ansible

This project provides Ansible inventory and playbooks specifically designed for network administration of Aruba switches. It is based on the [AOS-CX Ansible Collection](https://developer.arubanetworks.com/aruba-aoscx/docs/getting-started-with-ansible-and-aos-cx)

## Table of Contents

- [AOS-CX Ansible Collection](#aos-cx-ansible-collection)
- [Inventory](#inventory)
- [Playbooks](#playbooks)
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

- `6100_upload_firmware.yaml` - uploads new firmware to Aruba 6100 switches from a TFTP server.
- `collect_run-config.yaml` - collects `runing-config` files from Aruba 6100 switches and copies them to a Linux server.
- `day_0_config.yaml` - generates a standart switch configuration CLI file from a Jinja 2 template and copies it to running and startup config on the switches.
- `show.yaml` - run a list of show commands on Aruba switches

For executing a playbook, use the following command:

```bash
ansible-playbook [OPTIONS] playbook-name.yaml
```

## License

This project is licensed under the MIT License. See the LICENSE.md file for more information.

## Credits

This project uses the following third-party resources:

- [Ansible](https://www.ansible.com/) - for configuration management and automation of Aruba switches
- [GitHub](https://github.com/) - for source code hosting and collaboration tools
