# Linux Servers automated configuration with Ansible

Ansible playbooks and tools for different types of Linux servers.

## Folders

- `debian` - general Debian Linux server configuration.
- `netbox` - NetBox host server, with integrated Postgres Database.

## Handling

- When starting a KVM guest the following error may occur:

    ```error
    Error starting domain: Requested operation is not valid: network 'default' is not active
    ```

    To solve it, activate the `default` network for KVM:

    ```bash
    sudo virsh net-start default 
    ```
