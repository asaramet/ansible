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

## Deploy a Server Certificate

- Create a `server.csr` and `server.key` with

```bash
cd /opt/certs/harica
openssl req -new -newkey rsa:2048bits -sha512 -nodes -keyout server.key -out server.csr
```

- Create a valid server certificate on [Harica CertManager](https://cm.harica.gr/).

- Download it to `src/certs`
- Run Ansible playbook `deploy_cert.yaml`

## Configure Mail server

We will be using Exim4 as a Relay Mail via External Mail Server.

You're essentially setting up Exim4 as a smart relay, which accepts local mail (e.g., from Checkmk, cron, etc.) and forwards it to a real SMTP server (e.g., your organization's mail server or a service like Gmail, Office365, etc.).

1. Install Exim4 (if not already):

    ```bash
    apt update
    apt install exim4
    ```

2. Run the configuration wizard

    ```bash
    dpkg-reconfigure exim4-config
    ```

3. During the wizard:

    - Choose: `mail sent by smarthost; no local mail`
    - System mail name: e.g., `checkmk.hs-esslingen.de`
    - IPs to listen on: `127.0.0.1 ; ::1`
    - Other destinations: leave blank or `localhost.localdomain`
    - Visible domain name for local users: `checkmk.hs-esslingen.de`
    - Mail server configuration. IP address or host name of the outgoing smarthost `mail.hs-esslingen.de`
    - Keep number of DNS-queries minimal: `No`
    - Split configuration into small files? `No`

Now checkmk will send mails to the specific users.

To verify if relay is working send a mail to a known user with:

```bash
echo -e "Subject: Test Mail\n\nHello from Ansible!" | sendmail -v knownUser@hs-esslingen.de
```

To configure Notifications on host or also services go to:
`Setup -> Notifications` and edit `Global notification rules`.

## Auto restart OMD Site with systemd

Automatically restart the OMD site if it fails by wrapping it in a `systemd` service. This allows automatic recovery, and integration with `journalctl`, `systemctl`, and other monitoring tools.

- Update the `systemd` service unit for the OMD site, with the line `Restart=on-failure`.

```bash
vim /etc/systemd/system/omd.service
```

Add the following, line `Restart=on-failure` in `Service` section:

```ini
[Unit]
Description=Checkmk Monitoring
Documentation=https://docs.checkmk.com/latest/en/
Wants=network-online.target
After=syslog.target time-sync.target network.target network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/omd start
ExecStop=/usr/bin/omd stop
ExecReload=/usr/bin/omd reload
Restart=on-failure

[Install]
WantedBy=multi-user.targe
```

- Reload `systemd` and enable the service

```bash
systemctl daemon-reexec
systemctl daemon-reload
systemctl enable omd-monitoring
systemctl start omd-monitoring
```

- If getting wired warning, try to reboot the VM.
