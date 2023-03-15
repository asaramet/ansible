# Ansible inventory and playbooks specifically designed for network administration of Aruba switches

Ansible inventory and playbooks designed specifically for network administration of Aruba switches. The inventory contains switches grouped into sm_6100 and hze_6100 -> aruba_6100 -> aruba groups, and Linux manager servers in the linux group. Sensitive data such as passwords is stored using ansible-vault in host_vars/host/vault.

## Inventory

The Ansible inventory contains switches grouped into `sm_6100` and `hze_6100` -> `aruba_6100` -> `aruba groups`. Linux manager servers are in the `linux` group. Sensitive data such as passwords are stored with `ansible-vault` in `host_vars/host/vault`.

To view the inventory, use the following command:

```bash
ansible-inventory --graph
```

For a more detailed output, with variables, use:

```bash
ansible-inventory --graph --vars
```

## Playbooks

The following playbooks are included in this collection:

- `collect_run-config.yaml` - collects `runing-config` files from Aruba 6100 switches and copies them to a Linux server.
- `day_0_config.yaml` - generates a standart switch configuration CLI file from the template in `templates/new_6100.j2` file and copies it to running and startup config on the switches.
- `show.yaml` - run different show commands on Aruba switches

## License

This project is licensed under the MIT License. See the LICENSE.md file for more information.

## Credits

This project uses the following third-party resources:

- [Ansible](https://www.ansible.com/) - for configuration management and automation of Aruba switches
- [GitHub](https://github.com/) - for source code hosting and collaboration tools
