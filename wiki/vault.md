# Use Ansible Vault to use encrypted sensitive data

## Create a local super password to encrypt files in inventories

- Save vault password as text into a local file. For example in `~/.ssh/vault_pass`
- Link the inventory to the file by setting the `vault_password_file` keyword in inventory's `ansible.cfg`

  ```ini
  [defaults]
  ...
  vault_password_file = ~/.ssh/vault_pass
  ```

## Create a `vault` file in the inventory's folders with ansible-vault for saving sensitive variables

```bash
mkdir -p group_vars/group_name/  # or host_vars/host_name
ansible-vault create group_vars/group_name/vault
```

It this file, define the sensitive variables that usually are declared in `vars` file. Prepend the variable name with `vault_` to indicate that the variable is defined in a protected file.

```yaml
---
vault_ansible_become_pass: rootpassword
...
```

To edit/view the file, by automatically decrypting it, do:

```bash
ansible-vault edit group_vars/group_name/vault
ansible-vault view group_vars/group_name/vault
```

## Reference vault variables in your yaml files

```yaml
vars:
  ansible_become: true # elevate privileges on the remote machine, if necessary
  ansible_become_method: sudo
  ansible_become_pass: "{{ vault_ansible_become_pass }}"
```

## Debugging

- View ansible variable of `localhost` host

```bash
ansible -m debug -a 'var=hostvars[inventory_hostname]' localhost
```
