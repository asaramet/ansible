#!/usr/bin/env python3

'''
Initialize NetBox APIs with custom session
- development - for local development server, i.e 192.168.122.140
- production - for production server
'''

import pynetbox, yaml

from pathlib import Path
from ansible.constants import DEFAULT_VAULT_ID_MATCH
from ansible.parsing.vault import VaultLib, VaultSecret

#----------------------------#
# Vault settings
#----------------------------#

vault_pass_file = Path.home() / '.ssh' / 'vault_pass_netbox'
vault_file = Path(__file__).parent.parent / 'group_vars' / 'localhost' / 'vault'

# Read vault password
with vault_pass_file.open('r') as f:
    vault_pass = f.readline().strip().encode('utf-8')   # encrypt to bytes

# Initialize VaultLib class with a vault ID
vault = VaultLib([(DEFAULT_VAULT_ID_MATCH, VaultSecret(vault_pass))])

decrypted_vault= vault.decrypt(open(vault_file).read())

vault_dict = yaml.safe_load(decrypted_vault.decode())

#----------------------------#
# Netbox  connection settings
#----------------------------#
# Development server 
NETBOX_URL_DEV = "https://192.168.122.140"
NETBOX_TOKEN_DEV = vault_dict['vault_local_token']

# Production server 
NETBOX_URL = "https://netbox-bb.hs-esslingen.de"
NETBOX_TOKEN = vault_dict['vault_hs_netbox_token']

development = pynetbox.api(NETBOX_URL_DEV, token=NETBOX_TOKEN_DEV)
production = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

if __name__ == '__main__':
    import textwrap
    print(textwrap.dedent('''
        Initialize NetBox API with custom session
            - development - for local development server, i.e 192.168.122.140
            - production - for production server
    '''))