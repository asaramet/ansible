# Issues encountered building Ansible AOX platform

## Wrong HTTP hostname

While trying to update firmware with the a playbook using a aoscx collection and `aoscx_upload_firmware` module the following warning prevented it:

```txt
[WARNING]: The "arubanetworks.aoscx.aoscx" connection plugin has an improperly configured remote target value, forcing "inventory_hostname" templated value instead of the
string
```

Fond the following suggestion:

```txt
If you're experiencing a warning please ensure your ansible_host variable is defined - if you design your inventory such that the inventory_hostname is the DNS entry, you can programmatically define the ansible_host variable like so:

all:
  hosts:
    edge-sw.dns-entry.com:    # inventory hostname is set to DNS value
      ansible_host: "{{inventory_hostname}}"     # accessing variable programmatically 
      ansible_user: admin
      ansible_password: password
      ansible_network_os: arubanetworks.aoscx.aoscx
      ansible_connection: arubanetworks.aoscx.aoscx  # REST API via pyaoscx connection method
      ansible_aoscx_validate_certs: False
      ansible_aoscx_use_proxy: False
      ansible_acx_no_proxy: True
```

### Solution

Adding `ansible_host: "{{inventory_hostname}}"` variable and some extra connection variables helped. An example of a playlist variables will be:

```yaml
- name: Update firmware on Aruba 6100 switches
  hosts: new_6100
  gather_facts: false
  collections:
    - arubanetworks.aoscx
  vars: 
    ansible_network_os: arubanetworks.aoscx.aoscx
    ansible_connection: arubanetworks.aoscx.aoscx # REST API via pyaoscx connection method
    ansible_host: "{{ inventory_hostname }}" # accessing variable programmatically
    ansible_aoscx_validate_certs: false # When ansible_connection=arubanetworks.aoscx.aoscx
    ansible_aoscx_use_proxy: false
    ansible_acx_no_proxy: true
```
