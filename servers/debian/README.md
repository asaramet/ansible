# Debian Servers

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
