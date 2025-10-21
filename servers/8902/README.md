# Debian Linux

- `vm` - rzlx8902

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

## Install/update default packages

```bash
ansible-playbook playbooks/install.yaml
```
