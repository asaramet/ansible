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

## Update DNS resolver

```bash
ansible-playbook playbooks/dns.yaml 
```

## Install default packages

```bash
ansible-playbook playbooks/dnf_install.yaml
```

## Install extra packages

The host has no Internet connection, so no access to repositories outside official EPEL and Rocky that he get's from local mirror. So packages will have to be downloaded on the local machine, uploaded to the server and installed there.

- Install Bareos (Backup & Recovery Open Source Software)

```bash
ansible-playbook playbooks/bareos_install.yaml
```

- Configure postfix mail messanger to send emails for system notifications

```bash
ansible-playbook playbooks/postfix.yaml
```

- Configure chrony service - NTP handler

```bash
ansible-playbook playbooks/chrony.yaml
```
