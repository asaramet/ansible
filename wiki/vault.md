# Use Ansible Vault to use encrypted sensitive data

- Save vault password into a local file. For example in `~/.ssh/vault_pass`
- Set vault password file link into invetrorie's `ansible.cfg`

  ```ini
  [defaults]
  ...
  vault_password_file = ~/.ssh/vault_pass
  ```

- Move sensitive variables into Ansible Vault

  ```bash
  mkdir -p group_vars/group_name/  # or host_vars/host_name
  ansible-vault create group_vars/group_name/vault
  ```

  It this file, define the sensitive variables that usually are declared in `vars` file. Prepend the variable name with `vault_` to indicate that the variable is defined in a protected file.

  ```yaml
  ---
  vault_ansible_become_pass: supersecretpassword
  ...
  ```

- Reference vault variables in your yaml files

  ```yaml
  vars:
    ansible_become: true # elevate privileges on the remote machine, if necessary
    ansible_become_method: sudo
    ansible_become_pass: "{{ vault_ansible_become_pass }}"
  ```
