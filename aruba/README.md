# Ansible inventory and playbooks specifically designed for network administration of Aruba switches

Ansible inventory and playbooks designed specifically for network administration of Aruba switches. The inventory contains switches grouped into sm_6100 and hze_6100 -> aruba_6100 -> aruba groups, and Linux manager servers in the linux group. Sensitive data such as passwords is stored using ansible-vault in host_vars/host/vault.

## Inventory

The Ansible inventory contains switches grouped into `sm_6100` and `hze_6100` -> `aruba_6100` -> `aruba groups`. Linux manager servers are in the `linux` group. Sensitive data such as passwords are stored with `ansible-vault` in `host_vars/host/vault`.

To view the inventroy, use the following command:

```bash
ansible-inventory --graph
```

For a more detailed output, with variables, use:

```bash
ansible-inventory --graph --vars
```

## Playbooks

The following playbooks are included in this collection:

- `copy_running-config.yaml` - copies `runing-config` files generated with `get_running-config.yaml` playbook to the Linux manager server
- `get_running-config.yaml` - get the `running-config` from all Aruba switches and save them to their respective subgroup folders
- `show_vlan_debug.yaml` - shows configured VLANs on Aruba switches

## License

This project is licensed under the MIT License. See the LICENSE.md file for more information.

## Credits

This project uses the following third-party resources:

- [Ansible](https://www.ansible.com/) - for configuration management and automation of Aruba switches
- [GitHub](https://github.com/) - for source code hosting and collaboration tools
