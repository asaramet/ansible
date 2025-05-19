# Checkmk

## Install with Ansible

Update the version that has to be downloaded and the sha256 checksum in `playbooks/install.yaml`.

[Download Site](https://checkmk.com/download)

```bash
ansible-playbook playbooks/install.yaml
```

This will install checkmk on `rzlx8753` server.

## Create a Checkmk monitoring site on the server

As `root`:

```bash
omd create monitoring
omd start monitoring
```

This will create a monitoring site, will start it and create an admin user with the id - `cmkadmin` and a self generated password.

Change the password:

```bash
# Enter omd command line mode
omd su monitoring

# Change the password
OMD[monitoring]:~$ cmk-passwd cmkadmin
hG...8753
```

## Extra cmds

- OMD status

```bash
omd status
```

- Scan the whole network

```bash
nmap -T5 -sn 192.168.105.0-255
```

## SNMP connection

On the the switch SNMP should be enabled and the server allowed:

```aruba_os
config

ip authorized-managers 192.168.111.196 255.255.255.255 access manager access-method snmp

snmp enable
snmp-server community "pubno" operator
```

On the server ICMP and UDP ports 161 and 162 have to be opened. Take care in the ACLs UDP 161,162 from the server to the switch has to be allowed and all UDP traffic from the switch to the server too.

Check snmp responces on the server over SNMP version 2c:

```bash
apt install snmp
snmpwalk -v2c -c pubno <HOSTNAME OR IP> 1.3.6.1.2.1.1
snmpwalk -v3 -a MD5 -u checkmk -l authNoPriv -A <PASSPHRASE> <HOSTNAME OR IP> 1.3.6.1.2.1.1
```

## Redirect FQDN

Redirect FQDN so when you point in the browser `https://<checkmd fqdn>` it will point to `https://<checmd_fqdn>/monitoring`

```bash
# Update the main apache2 conf
vim /etc/apache2/apache2.conf

# Add the following line
RedirectMatch ^/$ /monitoring/
```
