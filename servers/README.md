# Linux Servers automated configuration with Ansible

Ansible playbooks and tools for different types of Linux servers.

## Folders

- `debian` - general Debian Linux server configuration.
- `netbox` - NetBox host server, with integrated Postgres Database.
- `checkmk` - Checkmk server
- `unifi` - UniFi management server

## Handling

- When starting a KVM guest the following error may occur:

    ```error
    Error starting domain: Requested operation is not valid: network 'default' is not active
    ```

    To solve it, activate the `default` network for KVM:

    ```bash
    sudo virsh net-start default 
    ```

    Or let it start automatically:

    ```bash
    sudo virsh net-autostart default
    sudo virsh net-list
    ```

## Debian Servers

- `hs_netbox` - Production NetBox Server
- `hs_checkmk` - Production Checkmk Server
- `local` - Development local server

## Clean install requirements

### SSH Server

```bash
apt update
apt install openssh-server
systemctl status sshd
```

Copy the ssh keys ( you may need to allow Vim right mouse click to copy in insert mode).
Usually it won't allow to login as root.

After the keys are copied allow login as root only over ssh-keys.

```bash
vim /etc/ssh/sshd_config

# Uncomment
PermitRootLogin prohibit-password

systemctl restart sshd
```

### Vim Right mouse click

```bash
vim .vimrc

# add:
set mouse-=a
```

### Install and configure ufw firewall

Mention the specific host with `-l` option.

```bash
ansible-playbook playbooks/ufw.yml -l hs_checkmk
```

### Disable IPv6

```bash
ansible-playbook playbooks/ipv6.yaml -l hs_checkmk
```

### Install default packages

```bash
ansible-playbook playbooks/apt_install.yaml -l hs_checkmk
```