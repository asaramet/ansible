# Cisco Devices Administration with Ansible

This project provides Ansible inventory and playbooks specifically designed for network administration of Cisco devices.

## Add an admin user with SSH-Key on the Cisco devices

SSH RSA 4096 bit key is compatible with legacy IOS switches as well as with the new IOS-XE.

- Display key string in multiple chunks

```bash
awk '{print $2}' ~/.ssh/id_rsa.pub | fold -w 150
```

- Add the key to the Cisco devices

```cisco-ios
configure terminal

! Create the local user with full administrative privileges
username ansible privilege 15

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
```
