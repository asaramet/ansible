#!/usr/bin/env  python3

# Standard reusable functions

import re, os, yaml
from tabulate import tabulate

this_folder = os.path.dirname(os.path.realpath(__file__))
main_folder = os.path.dirname(this_folder)

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
    # Base case
    if not text:
        return []

    names_tuple = []
    for i, line in enumerate(text):

        if line.startswith(section):
            # Found a section line
            section_value = line.split()[1]

            # Collect lines until 'exit' is found
            j = i + 1
            while j < len(text) and not text[j].strip().startswith('exit'):
                next_line = text[j].strip()
                if next_line.startswith(value):
                    found_value = next_line.split(' ', 1)[1].strip('"')
                    names_tuple.append((section_value, found_value))
                j += 1

            # Recur from the line after the 'exit' line
            names_tuple += recursive_section_search(text[j + 1:], section, value)
            break

    return names_tuple

# Return a list of file paths from a folder
def config_files(data_folder):
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    return files

# Convert a range string, i.e A1-A4, to a list of elements, i.e [A1,A2,A3,A4]
def convert_range(range_str):
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
            stack, _ = el.split('/')
        i_list.append((stack,el))

    return i_list

# --- Get functions ---
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
    for line in recursive_search("member", text, True):
        line_data = line.split()
        stacks.add(line_data[1])

    hostnames = {}
    for member in stacks:
        hostnames[member] = hostname + "-" + member
    return hostnames


def get_site(hostname):
    campuses = {
        "h": "flandernstrasse",
        "g": "gppingen",
        "s": "stadtmitte",
        "w": "weststadt"
    }
    return "campus-" + campuses[hostname[1]]

def get_device_role(t_file, hostname):
    role_code = hostname[2:4]
    if role_code == "cs":
        return "distribution-layer-switch"

    vlan_id, _, _ =  get_ip_address(t_file)

    if vlan_id in ["102", "202", "302"]:
        return "bueroswitch"

    return "access-layer-switch"

def get_trunks(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    trunks = []
    for line in recursive_search("trunk", text, True):
        line_data = line.split()
        trunks.append({"name": line_data[2], 'interfaces': line_data[1]})

    return trunks

def get_trunk_stack(t_file):
    trunks = []

    for trunk_dict in get_trunks(t_file):
        for interface in trunk_dict['interfaces'].split(','):
            interface = interface.split('/')[0]
            trunks.append((trunk_dict['name'].title(), interface))

    return trunks

def get_interface_names(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    return recursive_section_search(text, 'interface', 'name')

def get_vlans(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    return recursive_section_search(text, 'vlan', 'name')

def get_vlans_names(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    vlans = {}
    for vlan_id, vlan_name in recursive_section_search(text, 'vlan', 'name'):
        vlans[vlan_id] = vlan_name
    return vlans

def get_untagged_vlans(t_file, pattern = 'untagged'):
    with open(t_file, "r") as f:
        text = f.readlines()

    return recursive_section_search(text, 'vlan', pattern)

def get_ip_address(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    vlan_id, ip_string = recursive_section_search(text, 'vlan', 'ip address')[0]
    vlan_name = get_vlans_names(t_file)[vlan_id]

    _, ip, netmask = ip_string.split(' ')

    # count 1-bits in the binary representation of the netmask
    ip_bits = sum(bin(int(x)).count('1') for x in netmask.split('.'))

    return vlan_id, vlan_name, ip + '/' + str(ip_bits)

# --- Additional function ---
# Return a list of devices serial numbers from the yaml file
def serial_numbers():
    yaml_file = main_folder + "/data/src/serial_numbers.yaml"

    s_dict = {}
    with open(yaml_file, 'r') as f:
        for v_dict in yaml.safe_load(f):
            for key, value in v_dict.items():
                s_dict[key] = value

    return s_dict

# Return a list of devices dictionary
def devices():
    yaml_file = main_folder + "/data/src/devices.yaml"

    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)

    return None

# Return device type for a given hostname
def device_type(hostname):
    for device_type, d_list in devices().items():
        if hostname in d_list:
            return device_type

    return None

#----- Return JSON Objects -----#

# return the devices json object
# Input: 
# 1. device type slags dict, for example:
# device_type_slags = { 
#     'J8697A': 'hpe-procurve-5406zl',
#     'J8698A': 'hpe-procurve-5412zl',
#     'J8770A': 'hpe-procurve-4204vl',
#     'J8773A': 'hpe-procurve-4208vl',
#     'J9850A': 'hpe-5406r-zl2',
#     'J9851A': 'hpe-5412r-zl2'
# }
# 2. General tags, for example:
# tags = "switch"
# tags = ["switch", "modular_switch"]
def devices_json(config_files, device_type_slags, tags):
    #data = {'devices':[]}
    data = {'devices':[], 'chassis':[]}
    for t_file in config_files:
        hostname = get_hostname(t_file)

        # update data for single switches 
        if '0' in hostname.keys():
            hostname = hostname['0']

            d_label = device_type_slags[device_type(hostname)]
            data['devices'].append({'name': hostname, 'device_role': get_device_role(t_file, hostname), 'device_type': d_label,
                'site': get_site(hostname), 'tags': tags, 'serial':serial_numbers()[hostname]})
            continue

        # update data for stacks 
        clean_name = hostname['1'][:-2]
        d_label = device_type_slags[device_type(clean_name)]

        master = hostname['1']

        data['chassis'].append({'name': clean_name, 'master': master})

        for h_name in hostname.values(): 
            vc_position = int(h_name[-1])
            vc_priority = 255 if vc_position == 1 else 128
            data['devices'].append({'name': h_name, 'device_role': get_device_role(t_file, clean_name), 'device_type': d_label, 
                'site': get_site(clean_name), 'tags': tags, 'serial':serial_numbers()[h_name],
                'virtual_chassis': clean_name, 'vc_position': vc_position, 'vc_priority': vc_priority
            })

    return data

# return trunks and interfaces json objects
def trunks_json(config_files):
    data = {'trunks':[], 'trunk_interfaces':[]}

    for t_file in config_files:
        hostnames = get_hostname(t_file)
        trk_lists = get_trunks(t_file)

        if '0' in hostnames.keys(): # single switch
            hostname = hostnames['0']
        else:
            hostname = hostnames['1']

        for trunk in trk_lists:
            if trunk == []: continue
            trk_name = trunk['name'].title()

            interfaces = trunk['interfaces'].replace('-', ',').split(',')

            for interface in interfaces:
                if {'hostname': hostname, 'name': trk_name} not in data['trunks']:
                    data['trunks'].append({'hostname': hostname, 'name': trk_name})

                data['trunk_interfaces'].append({'hostname': hostname, 'interface': interface, 'trunk_name': trk_name})

    return data

def interface_names_json(config_files):
    data = {'interface_names':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)

        for i_tuple in get_interface_names(t_file):
            interface, name = i_tuple

            if '0' in hostname.keys():
                stack_hostname = hostname['0']

            else:
                stack_nr, _ = interface.split('/')
                stack_hostname = hostname[stack_nr]

            if {'hostname': stack_hostname, 'interface': interface, 'name': name} not in data['interface_names']:
                data['interface_names'].append({'hostname': stack_hostname, 'interface': interface, 'name': name})

    return data

def vlans_json(config_files):
    # collect unique vlans
    vlans = set()

    for t_file in config_files:
        for vlan in get_vlans(t_file):
            vlans.add(vlan)

    # save them to a json dict
    data = {'vlans':[]}
    for vlan in vlans:
        data['vlans'].append({'name': vlan[1], 'id': vlan[0]})

    return data

def untagged_vlans_json(config_files):
    data = {'untagged_vlans':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)
        vlan_sets = get_untagged_vlans(t_file)
        # ex: [('1', 'B10-B13,B15-B20,E2,E4,E6,E8,F2,F4,F6,F8'), ('50', 'A2-A24'), ('101', 'A1,B2,B9,B14,B21-B24,E5,E7,F5,F7,Trk1,Trk20-Trk24')]
        # ex2: [('1', '2/49-2/50'), ('50', '1/2-1/6,1/8,1/10-1/12,1/15,1/19,1/22-1/24,1/27-1/28,1/30-1/32,1/35-1/36,1/39-1/40,1/43-1/44,1/46-1/48,2/3,2/7,2/10,2/12,2/14-2/20,2/22,2/24-2/48')]

        # update data for single switches 
        if '0' in hostname.keys():
            hostname = hostname['0']

            for vlan_id, interfaces_range in vlan_sets:
                vlan_name = get_vlans_names(t_file)[vlan_id]
                for _, interface in convert_interfaces_range(interfaces_range):
                    data['untagged_vlans'].append({'hostname': hostname, 'interface': interface,
                        'vlan_id': vlan_id, 'vlan_name': vlan_name})
                continue
            continue
        
        # update data for stacks 
        trunk_stacks = get_trunk_stack(t_file)
        for vlan_id, interfaces_range in vlan_sets:
            vlan_name = get_vlans_names(t_file)[vlan_id]

            for stack_nr, interface in convert_interfaces_range(interfaces_range):

                # Find stack number for Trunks
                if 'T' in interface: 
                    for nr in range(1,20):
                        if (interface, str(nr)) in trunk_stacks:
                            stack_nr = str(nr)
                            break

                data['untagged_vlans'].append({'hostname': hostname[stack_nr], 'interface': str(interface),
                    'vlan_id': vlan_id, 'vlan_name': vlan_name})

    return data

def tagged_vlans_json(config_files):
    data = {'tagged_vlans':[]}

    for t_file in config_files:
        hostnames = get_hostname(t_file)

        # get list of tagged vlan tuples like:
        # [('5', 'A23-A24,B10,B20,F1,F4'), ('9', 'A23-A24,B10,B20,F1,F4'), ('50', 'A23-A24,B10,B20,F1,F4')]
        vlan_sets = get_untagged_vlans(t_file, 'tagged')

        trunk_stacks = get_trunk_stack(t_file)
        for vlan_id, interfaces_range in vlan_sets:
            vlan_name = get_vlans_names(t_file)[vlan_id]

            # iterate through all the interfaces that belong to a vlan
            for stack_nr, interface in convert_interfaces_range(interfaces_range):
                
                interface = str(interface)
                vlan_stacks = []

                if '0' in hostnames.keys():
                    vlan_stacks.append(hostnames['0'])

                # Find stack number for Trunks
                if 'T' in interface: 
                    for nr in range(0,20):
                        nr = str(nr)
                        if (interface, nr) in trunk_stacks:
                            vlan_stacks.append(hostnames[nr])
                else: 
                    vlan_stacks.append(hostnames[str(stack_nr)])

                for hostname in vlan_stacks:
                    interface_exists = False # flag to notify that the interface exist in data['tagged_vlans'][hostname]
                    for v_dict in data['tagged_vlans']:
                        if v_dict['hostname'] == hostname and v_dict['interface'] == interface:
                            # update the interface list with vlan data
                            v_dict['tagged_vlans'].append({'name': vlan_name, 'vlan_id': vlan_id})
                            interface_exists = True # update flag
                            break # exit the loop with updated flag

                    # create a new dictionary entry if the interface vlan list does not exists
                    if not interface_exists:
                        data['tagged_vlans'].append({ 'hostname': hostname, 'interface': interface, 
                            'tagged_vlans': [{'name': vlan_name, 'vlan_id': vlan_id}] })
                        interface_exists = False
    return data

def ip_addresses_json(config_files):
    data = {'ip_addresses':[]}

    for t_file in config_files:
        hostnames = get_hostname(t_file)

        hostname = hostnames['0'] if '0' in hostnames.keys() else hostnames['1']

        vlan_id, vlan_name, ip = get_ip_address(t_file)

        data['ip_addresses'].append({'hostname': hostname, 'ip': ip, 'vlan_id': vlan_id, 'vlan_name': vlan_name})
    
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
        '2/A2-2/A4'
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

def debug_get_hostname(data_folder):
    table = []
    headers = ["File name", "Hostname"]
    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_hostname(f) ])
    print("\n== Debug: get_hostname ==")
    print(tabulate(table, headers, "github"))

def debug_get_site(data_folder):
    table = []
    headers = ["File Name", "Location"]
    for f in config_files(data_folder):
        hostname = os.path.basename(f)
        table.append([ hostname, get_site(hostname) ])
    print("\n== Debug: get_site ==")
    print(tabulate(table, headers, "github"))

def debug_get_device_role(data_folder):
    table = []
    headers = ["File name", "Device role"]

    for f in config_files(data_folder):
        hostname = os.path.basename(f)
        table.append([os.path.basename(f), get_device_role(f, hostname)])
    print("\n== Debug: get_device_role ==")
    print(tabulate(table, headers, "github"))

def debug_get_trunks(data_folder):
    table = []
    headers = ["File Name", "Trunks"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_trunks(f)])
    print("\n== Debug: get_trunks ==")
    print(tabulate(table, headers))

def debug_get_trunk_stack(data_folder):
    table = []
    headers = ["File Name", "Trunks sets"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_trunk_stack(f)])
    print("\n== Debug: get_trunks ==")
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

def debug_device_type(data_folder):
    table = []
    headers = ["File Name", "Device Type"]
    for f in config_files(data_folder):
        hostname = get_hostname(f)
        table.append([hostname, device_type(hostname)])
    print("\n== Debug: device_type ==")
    print(tabulate(table, headers))

def debug_devices_json(data_folder):
    device_type_slags = {
      'J9623A': 'hpe-aruba-2620-24',
      'J9772A': 'hpe-aruba-2530-48g-poep',
      'J9853A': 'hpe-aruba-2530-48g-poep-2sfpp',
      'JL256A_stack': "hpe-aruba-2930f-48g-poep-4sfpp",
      'JL075A_stack': 'hpe-aruba-3810m-16sfpp-2-slot-switch',
      'JL693A_stack': "hpe-aruba-2930f-12g-poep-2sfpp",
      'JL322A_stack': 'hpe-aruba-2930m-48g-poep'
    }

    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(devices_json(files, device_type_slags, devices_tags))

    print("\n'device_json()' Output: for ", data_folder)
    print(output)

def debug_trunks_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(trunks_json(files))

    print("\n'trunks_json()' Output: for ", data_folder)
    print(output)

def debug_vlans_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(vlans_json(files))

    print("\n'vlans_json()' Output: for ", data_folder)
    print(output)

def debug_interface_names_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(interface_names_json(files))

    print("\n'interface_names_json()' Output: for ", data_folder)
    print(output)

def debug_untagged_vlans_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(untagged_vlans_json(files))

    print("\n'untagged_vlans_json()' Output: for ", data_folder)
    print(output)

def debug_tagged_vlans_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(tagged_vlans_json(files))

    print("\n'tagged_vlans_json()' Output: for ", data_folder)
    print(output)

def debug_ip_addresses_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(ip_addresses_json(files))

    print("\n'ip_addresses_json()' Output: for ", data_folder)
    print(output)

if __name__ == "__main__":
    print("\n=== Singles ===")
    #data_folder = main_folder + "/data/aruba-8-ports/"
    #data_folder = main_folder + "/data/aruba-12-ports/"
    #data_folder = main_folder + "/data/aruba-48-ports/"
    #data_folder = main_folder + "/data/aruba-48-ports/"
    #data_folder = main_folder + "/data/aruba-modular/"
    #data_folder = main_folder + "/data/hpe-8-ports/"
    data_folder = main_folder + "/data/hpe-48-ports/"
    #data_folder = main_folder + "/data/procurve-single/"

    #debug_config_files(data_folder)
    #debug_convert_range()
    debug_get_hostname(data_folder)
    #debug_get_device_role(data_folder)
    #debug_get_site(data_folder)
    debug_get_trunks(data_folder)
    #debug_get_interface_names(data_folder)
    #debug_get_vlans(data_folder)
    #debug_get_vlans_names(data_folder)
    #debug_get_untagged_vlans(data_folder)
    #debug_get_ip_address(data_folder)
    #debug_device_type(data_folder)

    print("\n=== Singles JSON ===")
    data_folder = main_folder + "/data/hpe-48-ports/"

    #debug_devices_json(data_folder)
    #debug_trunks_json(data_folder)
    #debug_interface_names_json(data_folder)
    #debug_vlans_json(data_folder)
    #debug_untagged_vlans_json(data_folder)
    #debug_tagged_vlans_json(data_folder)
    #debug_ip_addresses_json(data_folder)


    print("\n=== Stacking ===")
    data_folder = main_folder + "/data/aruba-stack/"
    #data_folder = main_folder + "/data/hpe-stack/"
    #data_folder = main_folder + "/data/aruba-modular-stack/"

    debug_get_hostname(data_folder)
    #debug_get_device_role(data_folder)
    #debug_get_site(data_folder)
    debug_get_trunks(data_folder)
    #debug_get_trunk_stack(data_folder)

    
    print("\n=== Stacking JSON ===")
    #data_folder = main_folder + "/data/aruba-stack/"
    data_folder = main_folder + "/data/aruba-stack-2930/"

    #debug_devices_json(data_folder)
    #debug_trunks_json(data_folder)
    #debug_interface_names_json(data_folder)
    #debug_vlans_json(data_folder)
    #debug_untagged_vlans_json(data_folder)
    #debug_tagged_vlans_json(data_folder)
    #debug_ip_addresses_json(data_folder)

    print("\n=== No files functions ===")
    #debug_convert_range()
    #debug_convert_interfaces_range()