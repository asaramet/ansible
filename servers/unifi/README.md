# Install UniFi OS Server

Dependencies:

- podman

## Get software

[Downloads](https://www.ui.com/download/software/unifi-os-server)

[executable](https://fw-download.ubnt.com/data/unifi-os-server/2f3a-linux-x64-4.3.6-be3b4ae0-6bcd-435d-b893-e93da668b9d0.6-x64)

## Install

Copy executable to a .deb format

```bash
scp 1856-linux-x64-5.0.6-33f4990f-6c68-4e72-9d9c-477496c22450.6-x64 root@rzlx8752:install.deb
```

Run executable

```bash
chmod u+x install.deb
./install.deb
```

## Output

```stdout
!!! INSTALLATION COMPLETE !!!

To grant permission for a user to run 'uosserver' commands:
-> Add the user to the 'uosserver' group:
   usermod -aG uosserver <username>
-> Then log out and log back in for the changes to take effect.

To get started with available commands, run:
   uosserver help

UOS Server is running at: https://192.168.111.195:11443/
```

## Add `admin` user

```bash
adduser admin
usermod -aG uosserver admin

uosserver stop
uosserver start
```

## Start the app in the browser

[URL](https://192.168.111.195:11443)

## Delete service and container

```bash
uosserver-purge
```
