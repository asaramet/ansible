#!/usr/bin/env  python3

# Standard reusable functions

import re, os, yaml
from tabulate import tabulate

this_folder = os.path.dirname(os.path.realpath(__file__))
main_folder = os.path.dirname(this_folder)
data_folder = os.path.join(main_folder, 'data')

device_type_slags = {
    'J9085A': 'hpe-procurve-2610-24',
    'J9086A': 'hpe-procurve-2610-24-12-pwr',
    'J9089A': 'hpe-procurve-2610-48-pwr',

    'J9562A': 'hpe-procurve-2915-8-poe',
    'J9565A': 'hpe-procurve-2615-8-poe',
    'J9774A': 'hpe-aruba-2530-8g-poep',
    'J9780A': 'hpe-aruba-2530-8-poep',

    'J9623A': 'hpe-aruba-2620-24',
    'J9772A': 'hpe-aruba-2530-48g-poep',
    'J9853A': 'hpe-aruba-2530-48g-poep-2sfpp',
    'J9145A': 'hpe-procurve-2910al-24g',

    'JL255A': "hpe-aruba-2930f-24g-poep-4sfpp", 
    'JL256A': "hpe-aruba-2930f-48g-poep-4sfpp",
    'JL322A': "hpe-aruba-2930m-48g-poep",
    'JL357A': "hpe-aruba-2540-48g-poep-4sfpp",

    'JL258A': "hpe-aruba-2930f-8g-poep-2sfpp",
    'JL693A': "hpe-aruba-2930f-12g-poep-2sfpp",

    'J8697A': 'hpe-procurve-5406zl',
    'J8698A': 'hpe-procurve-5412zl',
    'J8770A': 'hpe-procurve-4204vl',
    'J8773A': 'hpe-procurve-4208vl',
    'J9850A': 'hpe-5406r-zl2',
    'J9851A': 'hpe-5412r-zl2',
    'J9729A': 'hpe-aruba-2920-48g-poep',
    'J9729A_stack': 'hpe-aruba-2920-48g-poep',

    'JL256A_stack': "hpe-aruba-2930f-48g-poep-4sfpp",
    'JL075A_stack': 'hpe-aruba-3810m-16sfpp-2-slot-switch',
    'JL693A_stack': "hpe-aruba-2930f-12g-poep-2sfpp",

    'J9729A_stack': 'hpe-aruba-2920-48g-poep',

    'JL322A_module': "hpe-aruba-2930m-48g-poep",

    'JL322A_stack': 'hpe-aruba-2930m-48g-poep',

    'J9850A_stack': 'hpe-5406r-zl2', 

    'J9137A': 'hpe-procurve-2520-8-poe',
    'J9776A': 'hpe-aruba-2530-24g',
    'J9779A': 'hpe-aruba-2530-24-poep',
    'JL075A': 'hpe-aruba-3810m-16sfpp-2-slot-switch'
}

# --- Base functions ---
def search_line(expression, t_file):
    with open(t_file, "r") as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if re.search(expression, line): return line

    return None
    
# search lines in a text recursively, when line start with a pattern
def recursive_search(pattern, text, start=False):
    # base case
    if not text:
        return []

    found_lines = []
    for i, line in enumerate(text):
        if line.startswith(pattern) and start:
            found_lines.append(line.strip())

            found_lines += recursive_search(pattern, text[i+1:], True)
            break 

        if not start and pattern in line:
            found_lines.append(line.strip())

            found_lines += recursive_search(pattern, text[i+1:], False)
            break 

    return found_lines

# return a tuple (section, value), ex: (interface, interface_name), recursively from a switch config
def recursive_section_search(text, section, value):
    """
    Parses a config text block and returns a list of (section_value, value_found) tuples.
    Example: [('interface_name', 'interface_description')]
    """
    results = []
    current_section = None

    for line in text:
        stripped = line.strip()

        # Start of a section
        if stripped.startswith(section):
            parts = stripped.split(maxsplit=1)
            if len(parts) == 2:
                current_section = parts[1]
            continue
        
        # Value found inside section
        if current_section and stripped.startswith(value):
            _, val = stripped.split(' ', 1)
            results.append((current_section, val.strip('"')))
            continue

        # End of a section
        if stripped in {"exit", "!"}:
            current_section = None

    return results

# Return a list of file paths from a folder
def config_files(data_folder):
    return [entry.path for entry in os.scandir(data_folder) if entry.is_file()]

# Convert a range string, i.e A1-A4, to a list of elements, i.e [A1,A2,A3,A4]
def convert_range(range_str):
    if '-' not in range_str:
        return [range_str]

    # Split the input string into the start and end parts
    start, end = range_str.split('-')

    prefix_start = prefix_end = ""

    if '/' in start:
        p_start, start = start.split('/')
        p_end, end = end.split('/')
        prefix_start += p_start + "/"
        prefix_end += p_end + "/"
    
    # Extract the prefix and numeric parts of the start and end
    if re.match(r'[^\d]+', start): 
        prefix_start += re.match(r'[^\d]+', start).group()
        prefix_end += re.match(r'[^\d]+', end).group()

        # Ensure the prefixes are the same
        if prefix_start != prefix_end:
            raise ValueError("Prefixes do not match")
        
        start = re.search(r'\d+', start).group()
        end = re.search(r'\d+', end).group()
        
    if prefix_start:
        # Generate the list of elements
        return [f"{prefix_start}{num}" for num in range(int(start), int(end) + 1)]
    
    return [num for num in range(int(start), int(end)+1)]

# Convert and interfaces range string, such as 'B10-B13,B15-B20,E2,E4,E6,E8,F2,F4,F6,F8'
# to a valid list of interfaces
def convert_interfaces_range(interfaces_string):
    i_list = []

    for el in interfaces_string.split(","):
        stack = '0'
        if '-' in el:
            for interface in convert_range(el):
                # convert range string to list interfaces list and save them
                if '/' in str(interface):
                    stack, _ = interface.split('/')
                i_list.append((stack,interface))
            continue

        if '/' in str(el):
            stack = el.split('/')[0]
        i_list.append((stack,el))

    return i_list

# --- Get functions ---
def get_os_version(t_file):

    if search_line("; Ver", t_file):
        return "AOS"

    os_line = search_line("!Version", t_file)
    if os_line:
        return os_line.split(' ')[1]

    return

def get_hostname(t_file):
    hostname_line = search_line("hostname", t_file)

    hostname = hostname_line.split()[1].replace('"','') if not hostname_line.isspace() else " "

    #if not search_line("stacking", t_file):
    if not search_line("member", t_file):
        # Not a stack
        return { '0': hostname}

    with open(t_file, "r") as f:
        raw_text = f.readlines()

    text = []
    for line in raw_text:
        text.append(line.strip())

    stacks = set()
    for line in recursive_search("member", text):
        line_data = line.split()

        if 'vsf' in line_data: # Aruba OS-CX switches
            stacks.add(line_data[2])
        else:
            stacks.add(line_data[1])

    hostnames = {}
    for member in stacks:
        hostnames[member] = hostname + "-" + member

    return hostnames

def site_slug(t_file):

    hostnames = get_hostname(t_file)
    hostname = hostnames['0'] if '0' in hostnames.keys() else hostnames['1']

    campuses = {
        "h": "flandernstrasse",
        "g": "gppingen",
        "s": "stadtmitte",
        "w": "weststadt"
    }

    location = get_location(t_file)
    if location:
        location, _, _ = location
        location, _ = location.split('.', 1)

    if location == 'W20':
        return "hengstenbergareal"

    return "campus-" + campuses[hostname[1]]

def get_location(file):
    location_line = search_line("location", file)

    if not location_line or location_line.isspace(): return None

    location = location_line.split()[-1].strip('"')
    rack = False

    if location.split('.')[0] == 'V':
        location = location[2:]
        rack = True

    building, room = location.split(".", 1)

    building_nr = str(int(building[1:])) # convert "01" to "1", for example
    if len(building_nr) == 1:
        # add "0" to single digit buildings
        building_nr = "0" + building_nr

    location = building[0] + building_nr + "." + room

    return (location, room, rack)

# get flor number from room number
def get_flor_nr(room_nr):
    if not room_nr: return None

    if room_nr[0] == 'u':
        room_nr = '-' + room_nr[1:]

    flor = room_nr[0]
    flor = int(room_nr[:2]) if flor == '-' else int(flor)

    return str(flor)

# get flor name from room number
def get_flor_name(room_nr):
    flor_name = {
        "-3": "Untergeschoss 3",
        "-2": "Untergeschoss 2",
        "-1": "Untergeschoss",
        "0": "Erdgeschoss"
    }

    flor = get_flor_nr(room_nr)
    if int(flor) < 1:
        return (flor, flor_name[flor])

    return (flor, "Etage " + flor)

# get location's parent
def get_parent_location(location):
    prefixes = {
        "F": "fl",
        "G": "gp",
        "S": "sm",
        "W": "ws"
    }

    building = location.split(".")[0]
    return prefixes[building[0]] + "-" + "gebude" + "-" + building[1:]

# define floor location slug
def floor_slug(location):
    if not location: return None

    if isinstance(location, tuple):
        location = location[0]

    # ex: s01-2-etage-2
    flor_tags = {
        "-3": "untergeschoss-3",
        "-2": "untergeschoss-2",
        "-1": "untergeschoss",
        "0": "erdgeschoss"
    }
    building, room_nr = location.split(".", 1)
    flor = get_flor_nr(room_nr)
    flor_fx = str(abs(int(flor))) # string to use in the label
    flor_tag = flor_tags[flor] if int(flor) < 1 else "etage-" + flor

    return f"{building.lower()}-{flor_fx}-{flor_tag}"

def room_slug(location):
    if not location: return None

    if isinstance(location, tuple):
        location = location[0]

    # ex: s08-u105-c2
    building, room_nr = location.split(".", 1)

    # convert '-' to 'u'
    if room_nr[0] == '-':
        room_nr = f"u{room_nr[1:]}"

    # return tuple if rack number is mentioned
    if len(room_nr.split(".")) > 1:
        room_nr, rack = room_nr.split(".", 1)
        return (f"{building.lower()}-{room_nr.lower()}", rack.lower())

    return f"{building.lower()}-{room_nr.lower()}"
    

def get_device_role(t_file, hostname):
    role_code = hostname[2:4]
    if role_code == "cs":
        return "distribution-layer-switch"

    vlan_id, _, _ =  get_ip_address(t_file)

    if vlan_id in ["102", "202", "302"]:
        return "bueroswitch"

    return "access-layer-switch"

def get_lags(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    lags = []
    os_version = get_os_version(t_file)

    if os_version == 'ArubaOS-CX':
        # Parse OS_CX format: interface lag <number> and interface blocks with lag commands
        # Get all interfaces assigned to LAGs
        lag_interfaces = recursive_section_search(text, 'interface', 'lag ')

        # Group interfaces by LAG
        lag_dict = {}
        for interface, lag_number in lag_interfaces:
            # Skip LAG interface definitions themselves
            if interface.startswith('lag '):
                continue

            # Extract just the last part of interface number (e.g., '1' from '1/1/1')
            interface_num = interface.split('/')[-1]

            if lag_number not in lag_dict:
                lag_dict[lag_number] = []
            lag_dict[lag_number].append(interface_num)

        # Build the lags list
        for lag_num, interfaces in lag_dict.items():
            lags.append({
                "name": f"lag {lag_num}",
                'interfaces': ','.join(interfaces)
            })
    else:
        # Parse Aruba iOS format: trunk 9-10 trk1 lacp
        for line in recursive_search("trunk", text, True):
            line_data = line.split()
            lags.append({"name": line_data[2], 'interfaces': line_data[1]})

    return lags

def get_lag_stack(t_file):
    lags = []

    for lag_dict in get_lags(t_file):
        for interface in lag_dict['interfaces'].split(','):
            interface = interface.split('/')[0]
            lags.append((lag_dict['name'].title(), interface))

    return lags

def get_interface_names(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    names = recursive_section_search(text, 'interface', 'name')
    names += recursive_section_search(text, 'interface', 'description')

    return names

def get_vlans(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    vlans = set(recursive_section_search(text, 'vlan', 'name '))
    vlans.add(('1', 'DEFAULT_VLAN'))
    return vlans

def get_vlans_names(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    vlans = {}
    for vlan_id, vlan_name in recursive_section_search(text, 'vlan', 'name '):
        vlans[vlan_id] = vlan_name
    return vlans

def get_untagged_vlans(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    untagged = []

    # --- Aruba OS-style untagged VLANs ---
    untagged_sets = recursive_section_search(text, 'vlan', 'untagged')
    if untagged_sets:
        # Aruba-style configs: (vlan_id, interface_range)
        untagged.extend((vlan, v_range, None) for vlan, v_range in untagged_sets)
        return untagged

    # --- Access VLANs ---
    access_vlan_map = {}
    for interface, vlan in recursive_section_search(text, 'interface', 'vlan access'):
        _, vlan_id = vlan.split(' ', 1)  # Get just the vlan ID
        access_vlan_map.setdefault(vlan_id, []).append(interface)

    for vlan_id, interfaces in access_vlan_map.items():
        untagged.append((vlan_id, ','.join(interfaces), False))

    # --- lag Native VLANs ---
    native_vlan_map = {}
    for interface, vlan_line in recursive_section_search(text, 'interface', 'vlan trunk'):
        parts = vlan_line.split()
        if len(parts) >= 3 and parts[1] == 'native':
            vlan_id = parts[2]
            native_vlan_map.setdefault(vlan_id, []).append(interface)

    for vlan_id, interfaces in native_vlan_map.items():
        untagged.append((vlan_id, ','.join(interfaces), True))

    return untagged

def get_tagged_vlans(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    os_version = get_os_version(t_file)

    if os_version == 'ArubaOS-CX':
        # Parse OS_CX format: interface with "vlan trunk allowed" commands
        # Get all defined VLANs
        all_vlans = set()
        for vlan_id, _ in recursive_section_search(text, 'vlan', 'name'):
            all_vlans.add(vlan_id)

        # Also add VLANs without names (just "vlan X" declarations)
        for line in text:
            stripped = line.strip()
            if stripped.startswith('vlan ') and not stripped.startswith('vlan access') and not stripped.startswith('vlan trunk'):
                parts = stripped.split()
                if len(parts) == 2 and parts[1].isdigit():
                    all_vlans.add(parts[1])

        # Get interfaces with trunk configuration
        trunk_interfaces = {}
        native_vlans = {}

        # Find trunk interfaces and their native VLANs
        current_interface = None
        for line in text:
            stripped = line.strip()

            if stripped.startswith('interface ') and not stripped.startswith('interface vlan'):
                parts = stripped.split(maxsplit=1)
                if len(parts) == 2:
                    current_interface = parts[1]

            if current_interface and stripped.startswith('vlan trunk allowed'):
                if 'all' in stripped:
                    trunk_interfaces[current_interface] = list(all_vlans)
                else:
                    # Parse specific VLAN list
                    vlan_list = stripped.replace('vlan trunk allowed', '').strip()
                    trunk_interfaces[current_interface] = vlan_list.split(',')

            if current_interface and stripped.startswith('vlan trunk native'):
                native_vlan = stripped.split()[-1]
                native_vlans[current_interface] = native_vlan

        # Build result: (vlan_id, interface_string) for each tagged VLAN
        vlan_to_interfaces = {}
        for interface, vlans in trunk_interfaces.items():
            native = native_vlans.get(interface)
            for vlan_id in vlans:
                # Skip native VLAN (it's untagged)
                if vlan_id == native:
                    continue

                # Extract interface identifier
                if interface.startswith('lag '):
                    # Capitalize LAG name to match format (e.g., "Lag 20")
                    interface_id = interface.replace('lag ', 'Lag ')
                else:
                    # For physical interfaces, keep the full format (e.g., '1/1/13')
                    interface_id = interface

                if vlan_id not in vlan_to_interfaces:
                    vlan_to_interfaces[vlan_id] = []
                vlan_to_interfaces[vlan_id].append(interface_id)

        # Convert to list of tuples
        result = []
        for vlan_id, interfaces in vlan_to_interfaces.items():
            result.append((vlan_id, ','.join(interfaces)))

        return result
    else:
        # Parse Aruba iOS format: vlan sections with "tagged" keyword
        return recursive_section_search(text, 'vlan', 'tagged')

def extract_ip_from_mgmt(text):
    result = recursive_section_search(text, 'interface mgmt', 'ip static')
    if result:
        return result[0][1].split()[1]  # 'static 1.2.3.4'
    return None

def extract_ip_from_aoscx_vlan(text):
    result = recursive_section_search(text, 'interface vlan', 'ip address')
    if result:
        vlan_id = result[0][0].split()[1]  # 'vlan 101'
        ip = result[0][1].split()[1]       # 'address 1.2.3.4/24'
        return vlan_id, ip
    return None

def extract_ip_from_aruba_vlan(text):
    result = recursive_section_search(text, 'vlan', 'ip address')
    if result:
        vlan_id, ip_string = result[0]
        _, ip, netmask = ip_string.split()  # 'address 1.2.3.4 255.255.254.0'
        prefix = sum(bin(int(octet)).count('1') for octet in netmask.split('.'))
        return vlan_id, f'{ip}/{prefix}'
    return None

def get_ip_address(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    # Try management interface first
    mgmt_ip = extract_ip_from_mgmt(text)
    if mgmt_ip:
        return None, None, mgmt_ip

    # Try AOS_CX VLAN interfaces
    vlan_info = extract_ip_from_aoscx_vlan(text)
    if not vlan_info:
        vlan_info = extract_ip_from_aruba_vlan(text)

    vlan_id, ip = vlan_info
    vlan_name = get_vlans_names(t_file).get(vlan_id, "UNKNOWN")

    return vlan_id, vlan_name, ip

def get_modules(t_file):
    modules = []

    stacks_dict = {
        '1': 'A', '2': 'B', '3': 'C', '4': 'D', '5': 'E', '6': 'F',
        '7': 'G', '8': 'H', '9': 'I', '10': 'J', '11': 'K', '12': 'L'
    }

    hostnames = get_hostname(t_file)
    stack = '0'

    with open(t_file, "r") as f:
        text = f.readlines()

    if '0' in hostnames.keys():
        clean_hostname = hostnames['0']
    else:
        clean_hostname, _ = hostnames['1'].split('-')

    # Modules for Aruba 2920 stacks
    module_2920 = {
        'rggw1004sp': [('1', 'A', 'j9729a'), ('1', 'B', 'j9729a')],
        'rsgw7009p': [('1', 'A', 'j9731a'), ('1', 'B', 'j9731a')],
        'rsgw5313sp': [('1', 'A', 'j9731a'), ('2', 'A', 'j9731a'), ('3', 'A', 'j9731a')], # ('1', 'STK', 'j9733a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a')
        'rsgw10118sp': [('1', 'A', 'j9731a'), ('2', 'A', 'j9731a')], #('1', 'STK', 'j9733a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a') ], 
        'rsgw1u140sp': [('1', 'A', 'j9731a'), ('2', 'A', 'j9731a')], #('1', 'STK', 'j9733a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a') ],
        'rsgw12205sp': [('1', 'A', 'j9731a'), ('2', 'A', 'j9731a')], #('1', 'STK', 'j9733a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a') ],
        'rsgw2112sp': [('1', 'A', 'j9731a'), ('2', 'A', 'j9731a'), ('3', 'A', 'j9731a')], #('1', 'STK', 'j9733a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a') ],
        'rsgw9108sp': [('1', 'A', 'j9731a'), ('2', 'A', 'j9731a')], #('1', 'STK', 'j9733a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a') ],
        'rggw3102p': [('1', 'A', 'j9731a')]
    }

    names_2920 = {
        'A': 'Module A',
        'B': 'Module B',
        'STK': 'Stacking Module'
    }

    if clean_hostname in module_2920.keys():
        for stack, module, m_type in module_2920[clean_hostname]:
            if '0' in hostnames.keys(): stack = '0'
            modules.append({'hostname': hostnames[stack], 'module': module, 'type': m_type, 'name': names_2920[module], 'stack': stack})
        return modules

    # Modules for Aruba Modular stacks
    module_chassis = {
        'rscs0007': [
            ('1', 'A', 'j9993a'), ('1', 'B', 'j9993a'), ('1', 'C', 'j9993a'), ('1', 'D', 'j9993a'), ('1', 'E', 'j9988a'), ('1', 'F', 'j9996a'),
            ('2', 'A', 'j9993a'), ('2', 'B', 'j9993a'), ('2', 'C', 'j9993a'), ('2', 'D', 'j9993a'), ('2', 'E', 'j9988a'), ('2', 'F', 'j9996a') 
            #('1', 'MM1', 'j9827a'), ('2', 'MM1', 'j9827a'), 
         ]
    }

    if clean_hostname in module_chassis.keys():
        for stack, module, m_type in module_chassis[clean_hostname]:
            modules.append({'hostname': hostnames[stack], 'module': module, 'type': m_type, 'name': module, 'stack': stack})
        return modules

    # ProCurve 2910al
    module_2910al = {
        'rsgw2u127ap': [('A', 'j9008a')],
        'rsgw2u127bp': [('A', 'j9008a')]
    }

    if clean_hostname in module_2910al.keys():
        for module, m_type in module_2910al[clean_hostname]:
            modules.append({'hostname': clean_hostname, 'module': module, 'type': m_type})
        return modules

    # HPE OS
    flexible_modules = recursive_search("flexible-module", text)
    if len(flexible_modules) > 0:
        for line in flexible_modules:
            m_list = line.split()

            module = m_list[1] if len(m_list) == 4 else m_list[3]
            m_type = m_list[-1]

            if m_list[1] in stacks_dict.keys():
                stack = m_list[1]

            modules.append({'hostname': hostnames[stack], 'module': module, 'type': m_type, 'name': 'Uplink', 'stack': stack})
        return modules

    # Aruba-OS 
    not_modular = ["jl255a", "jl256a", "jl258a", "jl322a", "jl357a", "jl693a"]
    for line in recursive_search("module", text, True):
        m_list = line.split()
        if m_list[3] in not_modular: return modules

        module = m_list[1]
        if '0' not in hostnames:
            stack = module

        if '/' in stack:
            stack, module = stack.split('/')

        if module in stacks_dict.keys():
            module = stacks_dict[module]

        modules.append({'hostname': hostnames[stack], 'module': module, 'type': m_list[3], 'name': 'Uplink', 'stack': stack})

    return modules

# --- Additional function ---
# Return a list of devices serial numbers from the yaml file
def serial_numbers():
    yaml_file = main_folder + "/src/serial_numbers.yaml"

    s_dict = {}
    with open(yaml_file, 'r') as f:
        for v_dict in yaml.safe_load(f):
            for key, value in v_dict.items():
                s_dict[key] = value

    return s_dict 

# Return a list of devices dictionary
def devices():
    yaml_file = main_folder + "/src/devices.yaml"

    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)

    return None

# Return device type for a given hostname
def device_type(hostname):
    for device_type, d_list in devices().items():
        if hostname in d_list:
            return device_type

    return None

# Return a interfaces dictionary from a yaml file
def interfaces_dict():
    yaml_file = main_folder + "/src/interfaces.yaml"

    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)

    return None

# Return a module types dictionary from a yaml file
def module_types_dict():
    yaml_file = main_folder + "/src/module_types.yaml"

    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)

    return None

# Convert interfaces ranges from 'A' prefix to any other
def convert_prefix(range_str, new_prefix):
    prefix = range_str[0]

    if prefix == "A":

        if '-' in range_str:
            start, end = range_str.split('-')
            range_str = new_prefix + start[1:] + '-' + new_prefix + end[1:]

            return range_str

        return new_prefix + range_str[1:]

    return range_str

# Return a modules interfaces types dictionary from a yaml file
def modules_interfaces(model, stack_prefix = "A"):
    model = model.lower()

    yaml_file = main_folder + "/src/modules_interfaces.yaml"

    with open(yaml_file, 'r') as f:
        modules = yaml.safe_load(f)

    data = {'types': {}, 'poe_mode': {}, 'poe_types': {}}

    for key in modules['types'][model]:
        converted_key = convert_prefix(key, stack_prefix)
        data['types'][converted_key] = modules['types'][model][key]
        
        data['poe_mode'][converted_key] = None if key not in modules['poe_mode'] else modules['poe_mode'][model][key] 
        data['poe_types'][converted_key] = None if key not in modules['poe_types'] else modules['poe_types'][model][key] 

    return data

#----- Debugging -------
def debug_config_files(data_folder):
    table = []
    headers = ["File name", "Path"]
    for f in config_files(data_folder):
        table.append([ os.path.basename(f), f ])
    print(tabulate(table, headers, "github"))

def debug_convert_range():
    print("\n== Converting ranges to list of elements (convert_range) ==")

    ranges = [
        'B10-B13', 'B15-B20', 
        '1/1-1/14', '2/1-2/12',
        '2/A2-2/A4', 'A21'
    ]

    table = []
    headers = ["String", "Converted"]
    for value in ranges:
        table.append([value, convert_range(value)])
    print(tabulate(table, headers, "github"))

def debug_convert_interfaces_range():
    print("\n== Converting interface ranges strings to list of interfaces (convert_interfaces_range) ==")

    i_strings = [
        'B10-B13,B15-B17,E2,E4,,F2,F8',
        'A2-A3,A12,A15-A17,A23,B13-B14',
        'A1,B17,B20-B22,E3,F7,Trk20-Trk22,Trk30',
        '16-26,28', '50,52,55', '50',
        '1/2-1/4,1/16,2/1-2/4,2/16',
        '1/1,Trk1-Trk2',
        'Trk20-Trk23,1/1-1/4,Trk48',
        '2/A2-2/A4,5/A1-5/A3,6/A3,8/47-8/48'
    ] 

    table = []
    headers = ["String", "Converted"]
    for value in i_strings:
        table.append([value, convert_interfaces_range(value)])
    print(tabulate(table, headers, "github"))

def debug_get_os_version(data_folder):
    table = []
    headers = ["File name", "OS"]
    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_os_version(f) ])
    print("\n== Debug: get_os_version ==")
    print(tabulate(table, headers, "github"))

def debug_get_hostname(data_folder):
    table = []
    headers = ["File name", "Hostname"]
    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_hostname(f) ])
    print("\n== Debug: get_hostname ==")
    print(tabulate(table, headers, "github"))

def debug_site_slug(data_folder):
    table = []
    headers = ["File Name", "Location", "Site"]
    for f in config_files(data_folder):
        hostname = os.path.basename(f)
        table.append([ hostname, get_location(f), site_slug(f) ])
    print("\n== Debug: site_slug ==")
    print(tabulate(table, headers, "github"))

def debug_get_location(data_folder):
    table = []
    headers = ["File Name", "Location"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_location(f)])
    print("\n== Debug: get_location() ==")
    print(tabulate(table, headers))

def debug_get_room_location(data_folder):
    table = []
    headers = ["File Name", "Room Location"]

    for f in config_files(data_folder):
        location = get_location(f)

        if location:
            location, _ = location

        table.append([os.path.basename(f), get_room_location(location)])
    print("\n== Debug: get_room_location() ==")
    print(tabulate(table, headers))

def debug_get_flor_nr(data_folder):
    table = []
    headers = ["File Name", "Location", "Flor number"]

    for f in config_files(data_folder):
        location = get_location(f)
        room = None

        if location:
            location , room = location

        table.append([os.path.basename(f), location, get_flor_nr(room)])
    print("\n== Debug: get_flor_nr() ==")
    print(tabulate(table, headers))

def debug_get_device_role(data_folder):
    table = []
    headers = ["File name", "Device role"]

    for f in config_files(data_folder):
        hostname = os.path.basename(f)
        table.append([os.path.basename(f), get_device_role(f, hostname)])
    print("\n== Debug: get_device_role ==")
    print(tabulate(table, headers, "github"))

def debug_get_lags(data_folder):
    table = []
    headers = ["File Name", "lags"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_lags(f)])
    print("\n== Debug: get_lags ==")
    print(tabulate(table, headers))

def debug_get_lag_stack(data_folder):
    table = []
    headers = ["File Name", "lags sets"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_lag_stack(f)])
    print("\n== Debug: get_lags ==")
    print(tabulate(table, headers))

def debug_get_interface_names(data_folder):
    print("\n== Debug: get_interface_names ==")
    for f in config_files(data_folder):
        print(os.path.basename(f), '---> ', get_interface_names(f))

def debug_get_vlans(data_folder):
    print("\n== Debug: get_vlans ==")
    for f in config_files(data_folder):
        print(os.path.basename(f), '---> ', get_vlans(f))

def debug_get_vlans_names(data_folder):
    print("\n== Debug: get_vlans_names ==")
    for f in config_files(data_folder):
        print(os.path.basename(f), '---> ', get_vlans_names(f))

def debug_get_untagged_vlans(data_folder):
    print("\n== Collect interfaces ranges for untagged vlans ==")
    for f in config_files(data_folder):
        print(os.path.basename(f), '---> ', get_untagged_vlans(f))
    print('\n')

def debug_get_ip_address(data_folder):
    table = []
    headers = ["File Name", "IP"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_ip_address(f)])
    print("\n== Debug: get_ip_address ==")
    print(tabulate(table, headers))

def debug_get_modules(data_folder):
    table = []
    headers = ["File Name", "Modules"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_modules(f)])
    print("\n== Debug: get_modules ==")
    print(tabulate(table, headers))

def debug_device_type(data_folder):
    table = []
    headers = ["File Name", "Device Type"]
    for f in config_files(data_folder):
        hostname = get_hostname(f)
        table.append([hostname, device_type(hostname)])
    print("\n== Debug: device_type ==")
    print(tabulate(table, headers))

def debug_floor_slug(data_folder):
    table = []
    headers = ["File name", "Location", "Slug"]

    for f in config_files(data_folder):
        hostname = os.path.basename(f)
        location = get_location(f)
        slug = floor_slug(location)
        table.append([hostname, location, slug])
    print("\n== Debug: floor_slug ==")
    print(tabulate(table, headers, "github"))

def debug_room_slug(data_folder):
    table = []
    headers = ["File name", "Location", "Slug"]

    for f in config_files(data_folder):
        hostname = os.path.basename(f)
        location = get_location(f)
        slug = room_slug(location)
        table.append([hostname, location, slug])
    print("\n== Debug: room_slug ==")
    print(tabulate(table, headers, "github"))

if __name__ == "__main__":
    print("\n=== Debuging ===")

    data_folders = [
        #"/data/aruba-8-ports/",
        #"/data/aruba-12-ports/",
        # "/data/aruba-48-ports/",
        #"/data/hpe-8-ports/",
        # "/data/hpe-24-ports/",
        # "/data/aruba-stack/",
         "/data/aruba-stack-2920/",
        # "/data/aruba-stack-2930/",
        # "/data/aruba-modular/",
        # "/data/aruba-modular-stack/",
        # "/data/procurve-single/",
        # "/data/procurve-modular/",
        #"/data/aruba_6100/",
        #"/data/aruba_6300/"
    ]

    for folder in data_folders:
        data_folder = main_folder + folder

        print("\n Folder: ", data_folder)
        #debug_get_hostname(data_folder)
        #debug_site_slug(data_folder)
        #debug_config_files(data_folder)
        #debug_get_os_version(data_folder)
        #debug_get_device_role(data_folder)
        #debug_site_slug(data_folder)
        debug_get_lags(data_folder)
        #debug_get_interface_names(data_folder)
        #debug_get_vlans(data_folder)
        #debug_get_vlans_names(data_folder)
        debug_get_untagged_vlans(data_folder)
        #debug_get_ip_address(data_folder)
        #debug_device_type(data_folder)
        #debug_get_modules(data_folder)
        #debug_get_location(data_folder)
        #debug_floor_slug(data_folder)
        #debug_room_slug(data_folder)

    #print("\n=== No files functions ===")
    #debug_convert_range()
    #debug_convert_interfaces_range()

    #print(yaml.dump(interfaces_dict()))
    #print(yaml.dump(module_types_dict()))
    #print(yaml.dump(modules_interfaces("J9537A")))
    #print(yaml.dump(modules_interfaces("J9537a", "B")))
    #debug_get_interface_names(data_folder)
