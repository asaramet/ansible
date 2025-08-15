# Rocky Linux Server

- `hs_23` - Former rhlx0023

## Vim Right mouse click

```bash
vim .vimrc

# add:
set mouse-=a
```

## Install and configure ufw firewall

Mention the specific host with `-l` option.

```bash
ansible-playbook playbooks/ufw.yml
```

## Disable IPv6

```bash
ansible-playbook playbooks/ipv6.yaml 
```

## Install default packages

```bash
ansible-playbook playbooks/dnf_install.yaml
```
