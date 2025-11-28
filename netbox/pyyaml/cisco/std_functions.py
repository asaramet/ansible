#!/usr/bin/env python3

'''
Cisco config specific functions
'''

import logging, re

from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Some paths
script_path = Path(__file__).resolve()
cisco_dir = script_path.parent
pyyaml_dir = cisco_dir.parent
project_dir = pyyaml_dir.parent
data_folder = project_dir.joinpath('data', 'cisco')
#data_folder = pyyaml_dir.joinpath('data', 'cisco')

def _main(function: callable, data_folder: Path = data_folder, *args, **kwargs) -> None:
    """
    Parse Cisco config files and generate YAML data file.
    Args:
        function: function to execute, that should contain, as arguments, at least:
            data_folder: Data folder path. Default one is defined here already (../data/cisco)
    """
    # Configure logging
    logging.basicConfig(level = logging.INFO)

    function(data_folder, *args, **kwargs)

def get_hostname_and_stack(config_file):
    """
    Read a Cisco config file and extract hostname and stack info.
    Supports both regular stacks (2960X, 3850, 9300, etc.) and VSS (Virtual Switching System).

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        dict: Dictionary with keys:
            - hostname: str - Device hostname
            - stack: bool - True if device is in a stack (multiple switches)
            - switches: set - Set of switch numbers found in config
        Returns None if hostname not found or error occurs
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return None

    hostname = None
    stack_switches = set()
    is_vss = False

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Look for hostname line
                hostname_match = re.match(r'^hostname\s+(\S+)', line)
                if hostname_match:
                    hostname = hostname_match.group(1)

                # Pattern 1: Regular stack - "switch X provision <model>"
                switch_match = re.match(r'^switch\s+(\d+)\s+provision', line)
                if switch_match:
                    stack_switches.add(switch_match.group(1))

                # Pattern 2: VSS (Virtual Switching System) - "module provision switch X"
                vss_match = re.match(r'^module\s+provision\s+switch\s+(\d+)', line)
                if vss_match:
                    stack_switches.add(vss_match.group(1))
                    is_vss = True

                # Pattern 3: VSS indicator - "switch mode virtual"
                if re.search(r'switch\s+mode\s+virtual', line):
                    is_vss = True

        # If we found a hostname, return the result
        if hostname:
            # Stack if: more than 1 switch OR VSS configuration
            is_stack = len(stack_switches) > 1 or (len(stack_switches) > 0 and is_vss)
            result = {
                'hostname': hostname,
                'stack': is_stack,
                'switches': stack_switches
            }
            logger.debug(f"File {config_file.name}: hostname={hostname}, stack={is_stack}, switches={stack_switches}, VSS={is_vss}")
            return result
        else:
            logger.warning(f"No hostname found in {config_file.name}")
            return None

    except Exception as e:
        logger.error(f"Error reading file {config_file.name}: {e}")
        return None

# Cisco module type mapping: slot-type ID -> module model
module_type_slags = {
    404: 'WS-X45-SUP8-E',      # Sup 8-E 10GE (SFP+), 1000BaseX (SFP)
    407: 'WS-X4724-SFP-E',     # 24-port 1000BaseX SFP
    398: 'WS-X4748-UPOE+E',    # 48-port 10/100/1000BaseT UPOE E Series
    387: 'WS-X4712-SFP+E',     # 12-port 10GE SFP+
}

# Interface type mappings for Cisco devices
# Maps device models to interface characteristics (type, PoE mode, PoE type) by interface pattern
interface_type_mapping = {
    'ws-c2960x-24pd-l': {
        # 24-port PoE+ model
        r'GigabitEthernet\d+/0/([1-9]|1\d|2[0-4])$': {
            'type': '1000base-t',
            'poe_mode': 'pse',
            'poe_type': 'type2-ieee802.3at'  # PoE+ (up to 30W)
        },
        r'GigabitEthernet\d+/0/(25|26)$': {
            'type': '1000base-x-sfp',
            'poe_mode': None,
            'poe_type': None
        },
        r'TenGigabitEthernet\d+/0/[12]$': {
            'type': '10gbase-x-sfpp',
            'poe_mode': None,
            'poe_type': None
        }
    },
    'ws-c2960x-48fpd-l': {
        # 48-port PoE+ model
        r'GigabitEthernet\d+/0/([1-9]|[1-4]\d|48)$': {
            'type': '1000base-t',
            'poe_mode': 'pse',
            'poe_type': 'type2-ieee802.3at'  # PoE+ (up to 30W)
        },
        r'GigabitEthernet\d+/0/(49|5[0-2])$': {
            'type': '1000base-x-sfp',
            'poe_mode': None,
            'poe_type': None
        },
        r'TenGigabitEthernet\d+/0/[12]$': {
            'type': '10gbase-x-sfpp',
            'poe_mode': None,
            'poe_type': None
        }
    },
    'c9500-48y4c': {
        # 48x 25G + 4x 100G model
        r'TwentyFiveGigE\d+/0/([1-9]|[1-4]\d|48)$': {
            'type': '25gbase-x-sfp28',
            'poe_mode': None,
            'poe_type': None
        },
        r'HundredGigE\d+/0/(49|5[0-2])$': {
            'type': '100gbase-x-qsfp28',
            'poe_mode': None,
            'poe_type': None
        }
    },
    'c9500-40x': {
        # 40x 10G model
        r'TenGigabitEthernet\d+/0/([1-9]|[1-3]\d|40)$': {
            'type': '10gbase-x-sfpp',
            'poe_mode': None,
            'poe_type': None
        }
    },
    'c9500-32c': {
        # 32x 100G model
        r'HundredGigE\d+/0/([1-9]|[12]\d|3[0-2])$': {
            'type': '100gbase-x-qsfp28',
            'poe_mode': None,
            'poe_type': None
        }
    },
    'ws-c4506-e': {
        # Modular chassis - interfaces depend on line cards
        # Supervisor 8-E uplink ports
        r'TenGigabitEthernet\d+/1/\d+$': {
            'type': '10gbase-x-sfpp',
            'poe_mode': None,
            'poe_type': None
        },
        # WS-X4724-SFP-E: 24-port SFP (slot 2)
        r'GigabitEthernet\d+/2/([1-9]|1\d|2[0-4])$': {
            'type': '1000base-x-sfp',
            'poe_mode': None,
            'poe_type': None
        },
        # WS-X4748-UPOE+E: 48-port PoE+ (slot 3)
        r'GigabitEthernet\d+/3/([1-9]|[1-4]\d|48)$': {
            'type': '1000base-t',
            #'poe_mode': 'pse',
            #poe_type': 'type4-cisco-upoe'  # UPOE (up to 60W)
            'poe_mode': None,
            'poe_type': None
        },
        # WS-X4712-SFP+E: 12-port 10G SFP+ (slot 4)
        r'TenGigabitEthernet\d+/4/([1-9]|1[0-2])$': {
            'type': '10gbase-x-sfpp',
            'poe_mode': None,
            'poe_type': None
        }
    }
}

def get_modules(config_file):
    """
    Extract module/slot information from Cisco config file.
    Returns list of modules for modular chassis switches (e.g., Catalyst 4500 VSS).

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        list: List of dictionaries, each containing:
            - hostname: Device hostname (includes switch number for stacks: hostname-1, hostname-2)
            - switch: Switch number in stack/VSS (str)
            - slot: Slot number (str)
            - slot_type: Numeric slot-type ID from config (int)
            - module_model: Module model name (str) or None if unknown
            - base_mac: Base MAC address (str)
        Returns empty list if no modules found or error occurs

    Example:
        >>> get_modules(Path('/path/to/rgcs1234'))
        [{'hostname': 'rgcs1234-1', 'switch': '1', 'slot': '1',
          'slot_type': 404, 'module_model': 'WS-X45-SUP8-E',
          'base_mac': '80E0.1D11.1111'}, ...]
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return []

    # Get hostname and stack info first
    hostname_info = get_hostname_and_stack(config_file)
    if not hostname_info:
        logger.warning(f"Could not get hostname from {config_file.name}")
        return []

    hostname = hostname_info['hostname']
    is_stack = hostname_info['stack']

    modules = []
    current_switch = None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Match: "module provision switch X"
                switch_match = re.match(r'^module\s+provision\s+switch\s+(\d+)', line)
                if switch_match:
                    current_switch = switch_match.group(1)
                    continue

                # Match: " slot X slot-type YYY base-mac AA:BB:CC:DD:EE:FF"
                slot_match = re.match(r'^\s+slot\s+(\d+)\s+slot-type\s+(\d+)\s+base-mac\s+(\S+)', line)
                if slot_match and current_switch:
                    slot_num = slot_match.group(1)
                    slot_type_id = int(slot_match.group(2))
                    base_mac = slot_match.group(3)

                    # Get module model from mapping, or None if unknown
                    module_model = module_type_slags.get(slot_type_id)

                    # For stacks, append switch number to hostname
                    device_name = f"{hostname}-{current_switch}" if is_stack else hostname

                    modules.append({
                        'hostname': device_name,
                        'switch': current_switch,
                        'slot': slot_num,
                        'slot_type': slot_type_id,
                        'module_model': module_model,
                        'base_mac': base_mac
                    })

                    logger.debug(f"Found module: switch={current_switch}, slot={slot_num}, "
                               f"type={slot_type_id}, model={module_model}")

        if modules:
            logger.debug(f"Extracted {len(modules)} modules from {config_file.name}")
        else:
            logger.debug(f"No modules found in {config_file.name}")

        return modules

    except Exception as e:
        logger.error(f"Error extracting modules from {config_file.name}: {e}")
        return []

# Device type mapping: boot system image name -> actual chassis model
# Used when "switch X provision" is not available (VSS, older switches)
device_type_mapping = {
    'cat4500es8': 'ws-c4506-e',    # Catalyst 4500 Supervisor 8-E chassis
}

def get_lags(config_file):
    """
    Extract LAG (Port-channel) information from Cisco config file.
    Returns list of Port-channel names found in the configuration.

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        list: List of dictionaries, each containing:
            - name: Port-channel name (e.g., 'Port-channel1', 'Port-channel15')
        Returns empty list if no port-channels found or error occurs

    Example:
        >>> get_lags(Path('/path/to/config'))
        [{'name': 'Port-channel1'}, {'name': 'Port-channel2'}]
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return []

    lags = []

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Match: "interface Port-channel<number>"
                po_match = re.match(r'^interface\s+(Port-channel\d+)', line, re.IGNORECASE)
                if po_match:
                    lag_name = po_match.group(1)
                    lags.append({'name': lag_name})
                    logger.debug(f"Found LAG: {lag_name}")

        if lags:
            logger.debug(f"Extracted {len(lags)} LAGs from {config_file.name}")
        else:
            logger.debug(f"No LAGs found in {config_file.name}")

        return lags

    except Exception as e:
        logger.error(f"Error extracting LAGs from {config_file.name}: {e}")
        return []

def get_vlans(config_file):
    """
    Extract VLAN definitions from Cisco config file.
    Returns set of tuples containing VLAN ID and name.

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        set: Set of tuples (vlan_id, vlan_name), e.g., {('10', 'ADMIN'), ('20', 'USERS')}
             Returns empty set if no VLANs found or error occurs

    Example:
        >>> get_vlans(Path('/path/to/config'))
        {('10', 'ADMIN'), ('20', 'USERS'), ('40', 'BE')}
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return set()

    vlans = set()
    current_vlan_id = None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Match: "vlan <ID>"
                vlan_match = re.match(r'^vlan\s+(\d+)\s*$', line)
                if vlan_match:
                    current_vlan_id = vlan_match.group(1)
                    continue

                # Match: " name <NAME>" (must have current_vlan_id set)
                if current_vlan_id:
                    name_match = re.match(r'^\s+name\s+(.+?)\s*$', line)
                    if name_match:
                        vlan_name = name_match.group(1)
                        vlans.add((current_vlan_id, vlan_name))
                        logger.debug(f"Found VLAN: ID={current_vlan_id}, Name={vlan_name}")
                        current_vlan_id = None  # Reset after finding name
                        continue

                # If we hit a line that's not indented and we had a vlan_id, reset it
                # (VLAN without a name, or moved to next section)
                if current_vlan_id and not line.startswith(' ') and not line.startswith('\t'):
                    current_vlan_id = None

        if vlans:
            logger.debug(f"Extracted {len(vlans)} VLANs from {config_file.name}")
        else:
            logger.debug(f"No VLANs found in {config_file.name}")

        return vlans

    except Exception as e:
        logger.error(f"Error extracting VLANs from {config_file.name}: {e}")
        return set()

def get_interfaces(config_file):
    """
    Extract interface configurations from Cisco config file.
    Returns list of interface dictionaries with name, description, VLAN, LAG, and PoE info.

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        list: List of dictionaries, each containing:
            - interface: Interface name (e.g., 'GigabitEthernet1/0/1')
            - description: Interface description (str or None)
            - vlan_id: Access VLAN ID (str or None)
            - channel_group: LAG/Port-channel number (str or None)
            - power_inline: PoE configuration (str or None) - 'never', 'auto', or 'static'
            - power_inline_max: Max PoE wattage in milliwatts (int or None)
        Returns empty list if no interfaces found or error occurs

    Example:
        >>> get_interfaces(Path('/path/to/config'))
        [{'interface': 'GigabitEthernet1/0/1', 'description': 'Uplink to core',
          'vlan_id': None, 'channel_group': '1', 'power_inline': None, 'power_inline_max': None},
         {'interface': 'GigabitEthernet1/0/5', 'description': 'Access port',
          'vlan_id': '100', 'channel_group': None, 'power_inline': 'auto', 'power_inline_max': 30000}]
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return []

    interfaces = []
    current_interface = None
    current_data = {}

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Match: "interface <type><number>"
                # Physical: GigabitEthernet, TenGigabitEthernet, TwentyFiveGigE, FortyGigE, HundredGigE
                # Virtual: Vlan interfaces (SVIs - Switch Virtual Interfaces)
                # Skip: Loopback, Port-channel, AppGigabit, FastEthernet0 (mgmt)
                interface_match = re.match(r'^interface\s+((?:(?:TwentyFive|Forty|Hundred|Ten)?Gig(?:abit)?(?:Ethernet|E)\d+/\d+/\d+)|(?:Vlan\d+))(?:\s|$)', line)

                if interface_match:
                    # Save previous interface if exists
                    if current_interface:
                        interfaces.append({
                            'interface': current_interface,
                            'description': current_data.get('description'),
                            'vlan_id': current_data.get('vlan_id'),
                            'channel_group': current_data.get('channel_group'),
                            'power_inline': current_data.get('power_inline'),
                            'power_inline_max': current_data.get('power_inline_max')
                        })

                    # Start new interface
                    current_interface = interface_match.group(1)
                    current_data = {}
                    logger.debug(f"Found interface: {current_interface}")
                    continue

                # If we're in an interface block, parse its configuration
                if current_interface:
                    # Check if we've left the interface block (non-indented line)
                    if line and not line.startswith((' ', '\t', '!')):
                        # Save current interface and reset
                        interfaces.append({
                            'interface': current_interface,
                            'description': current_data.get('description'),
                            'vlan_id': current_data.get('vlan_id'),
                            'channel_group': current_data.get('channel_group'),
                            'power_inline': current_data.get('power_inline'),
                            'power_inline_max': current_data.get('power_inline_max')
                        })
                        current_interface = None
                        current_data = {}
                        continue

                    # Parse description
                    desc_match = re.match(r'^\s+description\s+(.+?)\s*$', line)
                    if desc_match:
                        current_data['description'] = desc_match.group(1)
                        continue

                    # Parse access VLAN
                    vlan_match = re.match(r'^\s+switchport\s+access\s+vlan\s+(\d+)', line)
                    if vlan_match:
                        current_data['vlan_id'] = vlan_match.group(1)
                        continue

                    # Parse channel-group (LAG membership)
                    lag_match = re.match(r'^\s+channel-group\s+(\d+)\s+mode', line)
                    if lag_match:
                        current_data['channel_group'] = lag_match.group(1)
                        continue

                    # Parse power inline
                    # Pattern 1: "power inline never"
                    poe_never_match = re.match(r'^\s+power\s+inline\s+never', line)
                    if poe_never_match:
                        current_data['power_inline'] = 'never'
                        continue

                    # Pattern 2: "power inline auto max <milliwatts>"
                    poe_auto_match = re.match(r'^\s+power\s+inline\s+(auto|static)(?:\s+max\s+(\d+))?', line)
                    if poe_auto_match:
                        current_data['power_inline'] = poe_auto_match.group(1)
                        if poe_auto_match.group(2):
                            current_data['power_inline_max'] = int(poe_auto_match.group(2))
                        continue

        # Don't forget the last interface
        if current_interface:
            interfaces.append({
                'interface': current_interface,
                'description': current_data.get('description'),
                'vlan_id': current_data.get('vlan_id'),
                'channel_group': current_data.get('channel_group'),
                'power_inline': current_data.get('power_inline'),
                'power_inline_max': current_data.get('power_inline_max')
            })

        if interfaces:
            logger.debug(f"Extracted {len(interfaces)} interfaces from {config_file.name}")
        else:
            logger.debug(f"No interfaces found in {config_file.name}")

        return interfaces

    except Exception as e:
        logger.error(f"Error extracting interfaces from {config_file.name}: {e}")
        return []

def subnet_mask_to_cidr(subnet_mask):
    """
    Convert subnet mask to CIDR prefix length.

    Args:
        subnet_mask: Subnet mask string (e.g., '255.255.255.0', '255.255.255.248')

    Returns:
        int: CIDR prefix length (e.g., 24, 29)
        Returns None if invalid subnet mask

    Example:
        >>> subnet_mask_to_cidr('255.255.255.0')
        24
        >>> subnet_mask_to_cidr('255.255.255.248')
        29
    """
    try:
        # Convert subnet mask to binary and count 1s
        octets = subnet_mask.split('.')
        binary = ''.join([bin(int(octet))[2:].zfill(8) for octet in octets])
        return binary.count('1')
    except Exception as e:
        logger.error(f"Error converting subnet mask '{subnet_mask}' to CIDR: {e}")
        return None

def get_ip_addresses(config_file):
    """
    Extract IP address configurations from Cisco config file.
    Returns list of IP address dictionaries with interface and IP info.

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        list: List of dictionaries, each containing:
            - interface: Interface name (e.g., 'Vlan802', 'Loopback0')
            - ip: IP address with CIDR notation (e.g., '192.168.198.252/24')
            - description: Interface description (str or None)
        Returns empty list if no IP addresses found or error occurs

    Example:
        >>> get_ip_addresses(Path('/path/to/config'))
        [{'interface': 'Vlan802', 'ip': '192.168.198.2/24', 'description': 'NAS-VIR'},
         {'interface': 'Vlan870', 'ip': '192.168.219.6/29', 'description': 'TF-VIR'}]
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return []

    ip_addresses = []
    current_interface = None
    current_description = None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Match: "interface <type><number>"
                # Focus on VLAN interfaces (SVIs) and Loopback interfaces
                interface_match = re.match(r'^interface\s+(Vlan\d+|Loopback\d+)(?:\s|$)', line)

                if interface_match:
                    # Start new interface
                    current_interface = interface_match.group(1)
                    current_description = None
                    logger.debug(f"Found IP interface: {current_interface}")
                    continue

                # If we're in an interface block, parse its configuration
                if current_interface:
                    # Check if we've left the interface block (non-indented line)
                    if line and not line.startswith((' ', '\t', '!')):
                        current_interface = None
                        current_description = None
                        continue

                    # Parse description
                    desc_match = re.match(r'^\s+description\s+(.+?)\s*$', line)
                    if desc_match:
                        current_description = desc_match.group(1)
                        continue

                    # Parse IP address: "ip address 192.168.198.252 255.255.255.0"
                    ip_match = re.match(r'^\s+ip\s+address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)', line)
                    if ip_match:
                        ip_addr = ip_match.group(1)
                        subnet_mask = ip_match.group(2)

                        # Convert subnet mask to CIDR
                        cidr_prefix = subnet_mask_to_cidr(subnet_mask)
                        if cidr_prefix is not None:
                            ip_with_cidr = f"{ip_addr}/{cidr_prefix}"

                            ip_addresses.append({
                                'interface': current_interface,
                                'ip': ip_with_cidr,
                                'description': current_description
                            })

                            logger.debug(f"Found IP on {current_interface}: {ip_with_cidr}")

        if ip_addresses:
            logger.debug(f"Extracted {len(ip_addresses)} IP addresses from {config_file.name}")
        else:
            logger.debug(f"No IP addresses found in {config_file.name}")

        return ip_addresses

    except Exception as e:
        logger.error(f"Error extracting IP addresses from {config_file.name}: {e}")
        return []

def get_device_type(config_file):
    """
    Extract device type from a Cisco configuration file.
    Supports both regular stacks and VSS/older switches.

    For VSS/older switches without provision commands, boot system image names
    are mapped to actual chassis types using device_type_mapping dictionary.

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        str: Device type (e.g., 'ws-c2960x-24pd-l', 'c9500-48y4c', 'ws-c4506-e')
             Returns None if no device type found

    Example:
        >>> get_device_type(Path('/path/to/config'))
        'ws-c2960x-24pd-l'
        >>> get_device_type(Path('/path/to/vss-config'))  # boot system has cat4500es8
        'ws-c4506-e'  # mapped from cat4500es8
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return None

    boot_system_type = None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Pattern 1: Regular stack - "switch 1 provision <device-type>"
                provision_match = re.match(r'^switch\s+\d+\s+provision\s+(\S+)', line)
                if provision_match:
                    device_type = provision_match.group(1)
                    logger.debug(f"Found device type '{device_type}' via provision in {config_file.name}")
                    return device_type

                # Pattern 2: VSS/older switches - extract from boot system command
                # Example: "boot system flash bootflash:cat4500es8-universalk9.SPA.03.11.04.E.152-7.E4.bin"
                boot_match = re.match(r'^boot\s+system\s+.*?:(cat\d+\w*|ws-c\d+\w*-\w+)', line, re.IGNORECASE)
                if boot_match:
                    boot_system_type = boot_match.group(1).lower()
                    logger.debug(f"Found potential device type '{boot_system_type}' in boot system command")

        # If we found device type from boot system, check if it needs mapping
        if boot_system_type:
            # Map boot system type to actual device type if mapping exists
            mapped_type = device_type_mapping.get(boot_system_type, boot_system_type)
            if mapped_type != boot_system_type:
                logger.debug(f"Mapped '{boot_system_type}' to '{mapped_type}' for {config_file.name}")
            logger.debug(f"Using device type '{mapped_type}' from boot system in {config_file.name}")
            return mapped_type

        logger.warning(f"No device type found in {config_file.name}")
        return None

    except Exception as e:
        logger.error(f"Error reading config file {config_file.name}: {e}")
        return None

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from functions import _debug

    data_path = Path(data_folder)
    if data_path.exists():
        for file_path in sorted(data_path.iterdir()):
            if file_path.is_file():
                _debug(get_interfaces, file_path)