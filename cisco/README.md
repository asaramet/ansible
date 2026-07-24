# Cisco Devices Administration with Ansible

This project provides Ansible inventory and playbooks specifically designed for network administration of Cisco devices.

## Create the "Jail" (Parser View) for `ansible` user

This view mimics exactly what we were trying to do with Privilege 10, but it executes from Privilege 15.

```cisco-ios
parser view ANSIBLE_FIRMWARE
 ! Assign a dummy secret required to initialize the view
 secret <YOUR_SECRET_PASSWORD>

 ! 1. Allow all show commands
 commands exec include all show

 ! 2. Allow file transfer, verification, and NVRAM saving
 commands exec include dir
 commands exec include write memory

 ! 3. Allow Ansible to disable terminal pagination
commands exec include terminal length
commands exec include terminal width

 ! 4. Allow upgrade commands
 ! On the Catalyst 9500
commands exec include all install 

 ! On the Catalyst 4506-E
commands exec include configure terminal
commands configure include all boot
commands exec include reload

 ! On the Catalyst 2960-X
commands exec include archive
exit
```

Now create `ansible` user with elevated privilege 15, but trapped inside the `ANSIBLE_FIRMWARE` view upon login.

```cisco-ios
username ansible privilege 15 view ANSIBLE_FIRMWARE secret <YOUR_SECRET_PASSWORD>
```

- All together

```cisco_catalyst 9500

#secret <YOUR_SECRET_PASSWORD>

conf term
parser view ANSIBLE_FIRMWARE
secret <YOUR_SECRET_PASSWORD>

commands exec include dir
commands exec include write memory
commands exec include write
commands exec include terminal width
commands exec include terminal length
commands exec include terminal
commands exec include all show
commands exec include all install
exit

username ansible privilege 15 view ANSIBLE_FIRMWARE secret <YOUR_SECRET_PASSWORD>
```

## Alternative configure privilege level on the device

By default, Cisco IOS has privilege level 1 (User EXEC) and privilege level 15 (Privileged EXEC). Levels 2–14 are custom levels you can define.

You can set up privilege level 10 (or any number between 2–14) and explicitly grant it access to the specific commands Ansible needs.

Create privilege level 10 for Ansible only required commands

```cisco-ios
configure terminal

! 1. Allow all show commands at privilege level 10

privilege exec level 10 show

! 2. Allow file operations needed to stage firmware (flash/bootflash management)

privilege exec level 10 dir
privilege exec level 10 copy
privilege exec level 10 delete
privilege exec level 10 verify
privilege exec level 10 write memory

! 3. Allow boot system configuration and reboot commands

privilege exec level 10 configure terminal
privilege configure level 10 boot system
privilege exec level 10 reload

! 4. Create the ansible user assigned directly to privilege 10

username ansible privilege 10 secret <YOUR_PASSWORD_OR_RSA_KEY>
```

## Add an ansible user with SSH-Key on the Cisco devices

SSH RSA 4096 bit key is compatible with legacy IOS switches as well as with the new IOS-XE.

- Display key string in multiple chunks

```bash
awk '{print $2}' ~/.ssh/id_rsa_ansible.pub | fold -w 150
```

- Add the key to the Cisco devices

```cisco-ios
show running-config | s pubkey-

configure terminal

! Bind the public key to the ansible user
ip ssh pubkey-chain
  username ansible
    key-string
      <PASTE_YOUR_BASE64_KEY_STRING_HERE> (Chunk 1)
      <PASTE_YOUR_BASE64_KEY_STRING_HERE> (Chunk 2)
      ...
    exit
  exit
end

write memory
```

## Update SSH config file with correct options for Cisco devices

```ini
# new Ciscos old Firmware, and Switches
Host rggw*s 
  KexAlgorithms=+diffie-hellman-group14-sha1 
  Ciphers=aes256-ctr
  HostKeyAlgorithms=+ssh-rsa 
  PubkeyAcceptedAlgorithms=+ssh-rsa
  MACs=hmac-sha1,hmac-sha1-96,hmac-sha2-256,hmac-sha2-512
  User=ansible
  IdentityFile=~/.ssh/id_rsa_ansible

Host r?cs*
  User=ansible
  IdentityFile=~/.ssh/id_rsa_ansible
```

## Copy Firmware over SCP

```bash
scp -O /tftpboot/software/cisco/cat9k_iosxe.17.15.05.SPA.bin rwcs0001:bootflash:cat9k_iosxe.17.15.05.SPA.bin
```
