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
    
# search lines in a text recursively
def recursive_search(pattern, text):
    # base case
    if not text:
        return []

    found_lines = []
    for i, line in enumerate(text):
        if line.startswith(pattern):
            found_lines.append(line.strip())

            found_lines += recursive_search(pattern, text[i+1:])
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
    
    # Extract the prefix and numeric parts of the start and end
    if re.match(r'[^\d]+', start): 
        prefix_start = re.match(r'[^\d]+', start).group()
        prefix_end = re.match(r'[^\d]+', end).group()

        # Ensure the prefixes are the same
        if prefix_start != prefix_end:
            raise ValueError("Prefixes do not match")
        
        num_start = int(re.search(r'\d+', start).group())
        num_end = int(re.search(r'\d+', end).group())
        
        # Generate the list of elements
        return [f"{prefix_start}{num}" for num in range(num_start, num_end + 1)]
    
    return [num for num in range(int(start), int(end))]

# Convert and interfaces range string, such as 'B10-B13,B15-B20,E2,E4,E6,E8,F2,F4,F6,F8'
# to a valid list of interfaces
def convert_interfaces_range(interfaces_string):
    i_list = []

    for el in interfaces_string.split(","):
        if '-' in el:
            for interface in convert_range(el):
                # convert range string to list interfaces list and save them
                i_list.append(interface)
            continue
        i_list.append(el)

    return i_list

# Convert and interfaces range string, such as '1/39-1/40,1/43-1/44,1/46-1/48,2/3,2/7,2/10,2/12,2/14-2/20,2/22,2/24-2/48'
# to a valid list of interfaces
def convert_stack_interfaces_range(interfaces_string):
    i_list = []
    stack_nr = None

    for el in interfaces_string.split(","):

        #if 'Trk' in el:
            # get stack number for trunks
        #    stack_nr = 22

        if '-' in el:

            # Split stack number and range
            start, end = el.split('-')
            if '/' in start:
                s_nr, s_el = start.split('/')
                e_nr, e_el = end.split('/')
                stack_nr = s_nr if s_nr == e_nr else None
                el = s_el + '-' + e_el

            for interface in convert_range(el):
                # convert range string to list interfaces list and save them
                i_list.append((stack_nr, interface))
            continue

        if '/' in el:
            stack_nr, el = el.split('/')


        i_list.append((stack_nr,el))

    return i_list

# --- Get functions ---
def get_hostname(t_file):
    hostname_line = search_line("hostname", t_file)

    hostname = hostname_line.split()[1].replace('"','') if not hostname_line.isspace() else " "

    #if not search_line("stacking", t_file):
    if not search_line("member", t_file):
        # Not a stack
        return hostname

    with open(t_file, "r") as f:
        raw_text = f.readlines()

    text = []
    for line in raw_text:
        text.append(line.strip())

    stacks = set()
    for line in recursive_search("member", text):
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
    for line in recursive_search("trunk", text):
        line_data = line.split()
        trunks.append({"name": line_data[2], 'interfaces': line_data[1]})

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
        if isinstance(hostname, str):
            d_label = device_type_slags[device_type(hostname)]
            data['devices'].append({'name': hostname, 'device_role': get_device_role(t_file, hostname), 'device_type': d_label,
                'site': get_site(hostname), 'tags': tags, 'serial':serial_numbers()[hostname]})
            continue

        # update data for stacks 
        clean_name = hostname['1'][:-2]
        d_label = device_type_slags[device_type(clean_name)]
        data['chassis'].append({'name': clean_name})

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
        hostname = get_hostname(t_file)
        trk_lists = get_trunks(t_file)

        # update data for single switches 
        if isinstance(hostname, str):
            for trunk in trk_lists:
                if trunk == []: continue
                trk_name = trunk['name'].title()
                data['trunks'].append({'hostname': hostname, 'name': trk_name})

                #there is always max 2 interfaces in a trunk, but sometimes they are created with '-' instead of ','
                interfaces = trunk['interfaces'].replace('-', ',').split(',') 
                for interface in interfaces:
                    data['trunk_interfaces'].append({'hostname': hostname, 'interface': interface, 'trunk_name': trk_name})
            continue

        # update data for stacks 
        clean_name = hostname['1'][:-2]
        for trunk in trk_lists:
            if trunk == []: continue
            trk_name = trunk['name'].title()

            interfaces = trunk['interfaces'].replace('-', ',').split(',')
            for stack_interface in interfaces:
                stack_nr, interface = stack_interface.split('/')
                stack_hostname = hostname[stack_nr]

                if {'hostname': stack_hostname, 'name': trk_name} not in data['trunks']:
                    data['trunks'].append({'hostname': stack_hostname, 'name': trk_name})

                data['trunk_interfaces'].append({'hostname': stack_hostname, 'interface': interface, 'trunk_name': trk_name})

    return data

def interface_names_json(config_files):
    data = {'interface_names':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)

        # update data for single switches 
        if isinstance(hostname, str):
            for i_tuple in get_interface_names(t_file):
                interface, name = i_tuple
                data['interface_names'].append({'hostname': hostname, 'interface': interface, 'name': name})
            continue
    
        # update data for stacks 
        clean_name = hostname['1'][:-2]
        for i_tuple in get_interface_names(t_file):
            stack_interface, name = i_tuple
            stack_nr, interface = stack_interface.split('/')
            stack_hostname = hostname[stack_nr]

            if {'hostname': stack_hostname, 'interface': interface, 'name': name} not in data['interface_names']:
                data['interface_names'].append({'hostname': stack_hostname, 'interface': interface, 'name': name})

    return data

def vlans_jason(config_files):
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

def get_trunk_stack(t_file):
    trunks = []

    for trunk_dict in get_trunks(t_file):
        for interface in trunk_dict['interfaces'].split(','):
            interface = interface.split('/')[0]
            trunks.append((trunk_dict['name'].title(), interface))

    return trunks

def untagged_vlans_json(config_files):
    data = {'untagged_vlans':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)
        vlan_sets = get_untagged_vlans(t_file)
        # ex: [('1', 'B10-B13,B15-B20,E2,E4,E6,E8,F2,F4,F6,F8'), ('50', 'A2-A24'), ('101', 'A1,B2,B9,B14,B21-B24,E5,E7,F5,F7,Trk1,Trk20-Trk24')]
        # ex2: [('1', '2/49-2/50'), ('50', '1/2-1/6,1/8,1/10-1/12,1/15,1/19,1/22-1/24,1/27-1/28,1/30-1/32,1/35-1/36,1/39-1/40,1/43-1/44,1/46-1/48,2/3,2/7,2/10,2/12,2/14-2/20,2/22,2/24-2/48')]

        # update data for single switches 
        if isinstance(hostname, str):
            for vlan_id, interfaces_range in vlan_sets:
                vlan_name = get_vlans_names(t_file)[vlan_id]
                for interface in convert_interfaces_range(interfaces_range):
                    data['untagged_vlans'].append({'hostname': hostname, 'interface': interface,
                        'vlan_id': vlan_id, 'vlan_name': vlan_name})
                continue
            continue
        
        # update data for stacks 
        #clean_name = hostname['1'][:-2]
        trunk_stacks = get_trunk_stack(t_file)
        for vlan_id, interfaces_range in vlan_sets:
            vlan_name = get_vlans_names(t_file)[vlan_id]

            for stack_nr, interface in convert_stack_interfaces_range(interfaces_range):

                # Find stack number for Trunks
                if not stack_nr: 
                    for nr in range(1,20):
                        if (interface, str(nr) ) in trunk_stacks:
                            stack_nr = nr
                            continue

                data['untagged_vlans'].append({'hostname': hostname[str(stack_nr)], 'interface': interface,
                    'vlan_id': vlan_id, 'vlan_name': vlan_name})
            continue

    return data

def tagged_vlans_json(config_files):
    data = {'tagged_vlans':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)

        # get list of tagged vlan tuples like:
        # [('5', 'A23-A24,B10,B20,F1,F4'), ('9', 'A23-A24,B10,B20,F1,F4'), ('50', 'A23-A24,B10,B20,F1,F4')]
        vlan_sets = get_untagged_vlans(t_file, 'tagged')

        for vlan_id, interfaces_range in vlan_sets:
            vlan_name = get_vlans_names(t_file)[vlan_id]

            # iterate through all the interfaces that belong to a vlan
            for interface in convert_interfaces_range(interfaces_range):
                
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
        hostname = get_hostname(t_file)
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
    print("\n== Converting ranges to list of elements ==")

    ranges = ['B10-B13', 'B15-B20', 'E2,E4,E6-E8,F2,F4,F6,F8']

    table = []
    headers = ["String", "Converted"]
    for value in ranges:
        table.append([value, convert_range(value)])
    print(tabulate(table, headers, "github"))

def debug_convert_interfaces_range():
    print("\n== Converting interface ranges strings to list of interfaces ==")

    i_strings = [
        'B10-B13,B15-B20,E2,E4,E6,E8,F2,F4,F6,F8',
        'A2-A3,A6-A9,A12,A15-A20,A23,B13-B14',
        'A1,B17,B20-B24,E3,E5,E7,F5,F7,Trk20-Trk25,Trk27,Trk30',
        '6-26,28', '50,52,55', '50'
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

if __name__ == "__main__":
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
    #debug_convert_interfaces_range()
    #debug_get_hostname(data_folder)
    #debug_get_device_role(data_folder)
    #debug_get_site(data_folder)
    #debug_get_trunks(data_folder)
    #debug_get_interface_names(data_folder)
    #debug_get_vlans(data_folder)
    #debug_get_vlans_names(data_folder)
    #debug_get_untagged_vlans(data_folder)
    #debug_get_ip_address(data_folder)
    #debug_device_type(data_folder)

    print("\n=== Stacking ===")
    data_folder = main_folder + "/data/aruba-stack/"
    #data_folder = main_folder + "/data/hpe-stack/"
    #data_folder = main_folder + "/data/aruba-modular-stack/"

    debug_get_hostname(data_folder)
    #debug_get_device_role(data_folder)
    #debug_get_site(data_folder)
    debug_get_trunks(data_folder)

    #files = config_files(data_folder)
    #device_type_slags = { 'J9729A': 'hpe-aruba-2920-48g-poep' }
    #devices_tags = ["switch", "stack"]
    #print(devices_json(files, device_type_slags, devices_tags))