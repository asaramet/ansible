#!/usr/bin/env python3

# Collect Aruba J8697A data and create a j8697a.yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import serial_numbers, device_type

this_folder = os.path.dirname(os.path.realpath(__file__))
main_folder = os.path.dirname(this_folder)
#data_folder = main_folder + "/data/aruba-J8697A/"
data_folder = main_folder + "/data/hp-modular/"

def search_line(expression, t_file):
    with open(t_file, "r") as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if re.search(expression, line): return line

    return " " # return empty space if line not found
    
def get_hostname(t_file):
    hostname_line = search_line("hostname", t_file)
    return hostname_line.split()[1].replace('"','') if not hostname_line.isspace() else " "

def get_site(t_file):
    campuses = {
        "h": "flandernstrasse",
        "g": "gppingen",
        "s": "stadtmitte",
        "w": "weststadt"
    }
    return "campus-" + campuses[get_hostname(t_file)[1]]

def get_device_role(t_file):
    role_code = get_hostname(t_file)[2:4]
    if role_code == "cs":
        return "distribution-layer-switch"
    return "access-layer-switch"

def set_tags():
    return "switch"

# return the devices json object
def devices_json(config_files):
    d_types = { 
        'J8697A': 'hpe-procurve-5406zl',
        'J8698A': 'hpe-procurve-5412zl',
        'J8770A': 'hpe-procurve-4204vl',
        'J8773A': 'hpe-procurve-4208vl',
        'J9850A': 'hpe-5406r-zl2',
        'J9851A': 'hpe-5412r-zl2'
    }

    data = {'devices':[]}
    for t_file in config_files:
        hostname = get_hostname(t_file)
        d_type = d_types[device_type(hostname)]
        data['devices'].append({'name': hostname, 'device_role': get_device_role(t_file), 'device_type': d_type,
            'site': get_site(t_file), 'tags': set_tags(), 'serial':serial_numbers()[hostname]})
    return data

# search lines in a text recursively
def recursive_search(text, pattern):
    # base case
    if not text:
        return []

    found_lines = []
    for i, line in enumerate(text):
        if line.startswith(pattern):
            found_lines.append(line.strip())

            found_lines += recursive_search(text[i+1:], pattern)
            break 

    return found_lines

def get_modules(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    names = {
        '1': 'A', '2': 'B', '3': 'C', '4': 'D', '5': 'E', '6': 'F',
        '7': 'G', '8': 'H', '9': 'I', '10': 'J', '11': 'K', '12': 'L'
    }
    modules = []
    for line in recursive_search(text, "module"):
        m_list = line.split()
        name = m_list[1]
        if name in names.keys():
            name = names[name]
        modules.append({'module': name, 'type': m_list[3]})
    return modules

# return the modules json object
def modules_json(config_files):
    data = {'modules':[]}
    types = {
        "j8702a": "ProCurve 24-port 10/100/1000Base-T PoE Switch Module",
        "j8705a": "HP J8705A ProCurve PoE 20 Port Gig-T SFP Plus 4 Port Mini GBIC ZL Module",
        "j8706a": "ProCurve Switch 5400zl 24p Mini-GBIC Module",
        "j8707a": "HP 4-Port 10GbE X2 ZL Module",
        "j8765a": "ProCurve Switch VL 24-Port 10/100-TX Module",
        "j8766a": "HP ProCurve J8766A VL 1-Port 10GbE X2 ZL Module",
        "j8768a": "ProCurve Switch 24-port Gig-T vl Module",
        "j9033a": "HP ProCurve Switch vl 20-Port Gig-T+ 4 SFP Module",
        "j9534a": "Aruba J9534A",
        "j9550a": "HP 24-Port GiG-T v2 ZL Module",
        "j9537a": "Aruba J9537A",
        "j9538a": "Aruba J9538A",
        "j9986a": "Aruba J9986A",
        "j9990a": "Aruba J9990A",
        "j9992a": "Aruba J9992A",
        "j9993a": "Aruba J9993A"
        }
    for t_file in config_files:
        modules = get_modules(t_file)
        device = get_hostname(t_file)

        for module in modules:
            data['modules'].append({'device': device, 'module_bay': module['module'], 'type': types[module['type'].lower()]})
    return data

def get_trunks(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    trunks = []
    for line in recursive_search(text, "trunk"):
        line_data = line.split()
        trunks.append({"name": line_data[2], 'interfaces': line_data[1]})

    return trunks

# return trunks and interfaces json objects
def trunks_json(config_files):
    data = {'trunks':[], 'trunk_interfaces':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)
        trk_lists = get_trunks(t_file)

        for trunk in trk_lists:
            trk_name = trunk['name'].title()
            data['trunks'].append({'hostname': hostname, 'name': trk_name})

            #there is always max 2 interfaces in a trunk, but sometimes they are created with '-' instead of ','
            interfaces = trunk['interfaces'].replace('-', ',').split(',') 
            for interface in interfaces:
                data['trunk_interfaces'].append({'hostname': hostname, 'interface': interface, 'trunk_name': trk_name})

    return data

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

def get_interface_names(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    return recursive_section_search(text, 'interface', 'name')

def interface_names_json(config_files):
    data = {'interface_names':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)
        for i_tuple in get_interface_names(t_file):
            interface, name = i_tuple
            data['interface_names'].append({'hostname': hostname, 'interface': interface, 'name': name})
    
    return data

def get_vlans(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    return recursive_section_search(text, 'vlan', 'name')

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

def get_untagged_vlans(t_file, pattern = 'untagged'):
    with open(t_file, "r") as f:
        text = f.readlines()

    return recursive_section_search(text, 'vlan', pattern)

def get_vlans_names(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    vlans = {}
    for vlan_id, vlan_name in recursive_section_search(text, 'vlan', 'name'):
        vlans[vlan_id] = vlan_name
    return vlans


def convert_range(range_str):
    # Split the input string into the start and end parts
    start, end = range_str.split('-')
    
    # Extract the prefix and numeric parts of the start and end
    prefix_start = re.match(r'[^\d]+', start).group()
    num_start = int(re.search(r'\d+', start).group())
    prefix_end = re.match(r'[^\d]+', end).group()
    num_end = int(re.search(r'\d+', end).group())
    
    # Ensure the prefixes are the same
    if prefix_start != prefix_end:
        raise ValueError("Prefixes do not match")
    
    # Generate the list of elements
    return [f"{prefix_start}{num}" for num in range(num_start, num_end + 1)]

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

def untagged_vlans_json(config_files):
    data = {'untagged_vlans':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)
        vlan_sets = get_untagged_vlans(t_file)
        # ex: [('1', 'B10-B13,B15-B20,E2,E4,E6,E8,F2,F4,F6,F8'), ('50', 'A2-A24'), ('101', 'A1,B2,B9,B14,B21-B24,E5,E7,F5,F7,Trk1,Trk20-Trk24')]
        for vlan_id, interfaces_range in vlan_sets:
            vlan_name = get_vlans_names(t_file)[vlan_id]
            for interface in convert_interfaces_range(interfaces_range):
                data['untagged_vlans'].append({'hostname': hostname, 'interface': interface,
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

def get_ip_address(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    vlan_id, ip_string = recursive_section_search(text, 'vlan', 'ip address')[0]
    vlan_name = get_vlans_names(t_file)[vlan_id]

    _, ip, netmask = ip_string.split(' ')

    # count 1-bits in the binary representation of the netmask
    ip_bits = sum(bin(int(x)).count('1') for x in netmask.split('.'))

    return vlan_id, vlan_name, ip + '/' + str(ip_bits)

def ip_addresses_json(config_files):
    data = {'ip_addresses':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)
        vlan_id, vlan_name, ip = get_ip_address(t_file)

        data['ip_addresses'].append({'hostname': hostname, 'ip': ip, 'vlan_id': vlan_id, 'vlan_name': vlan_name})
    
    print(data)
    return data


# Collect all the data and saved it to a YAML file
def main():
    # get data files
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]

    with open(main_folder + "/data/yaml/hp_modular.yaml", 'w') as f:
        yaml.dump(devices_json(files), f)
        yaml.dump(modules_json(files), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)
        yaml.dump(vlans_jason(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

#---- Debugging ----#
def text_files():
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    return files

def debug_get_hostname():
    table = []
    headers = ["File name", "Hostname"]
    for f in text_files():
        table.append([ os.path.basename(f), get_hostname(f) ])
    print(tabulate(table, headers, "github"))

def debug_get_site():
    table = []
    headers = ["File Name", "Location"]
    for f in text_files():
        table.append([ os.path.basename(f), get_site(f) ])
    print(tabulate(table, headers, "github"))

def debug_get_device_role():
    table = []
    headers = ["File name", "Device role"]
    for f in text_files():
        table.append([os.path.basename(f), get_device_role(f)])
    print(tabulate(table, headers, "github"))

def debug_get_modules():
    table = []
    types = set()
    headers = ["File Name", "Modules"]
    for f in text_files():
        modules = get_modules(f)
        table.append([os.path.basename(f), modules])
        for module in modules:
            types.add(module['type'])
    print(tabulate(table, headers, "github"))
    print(types)

def debug_get_trunks():
    table = []
    headers = ["File Name", "Trunks"]
    for f in text_files():
        table.append([os.path.basename(f), get_trunks(f)])
    print(tabulate(table, headers))

def debug_get_interface_names():
    for f in text_files():
        print(os.path.basename(f), '---> ', get_interface_names(f))

def debug_get_vlans():
    for f in text_files():
        print(os.path.basename(f), '---> ', get_vlans(f))

def debug_get_untagged_vlans():
    print("\n== Collect interfaces ranges for untagged vlans ==")
    for f in text_files():
        print(os.path.basename(f), '---> ', get_untagged_vlans(f))
    print('\n')

def debug_convert_interfaces_range():
    i_strings = [
        'B10-B13,B15-B20,E2,E4,E6,E8,F2,F4,F6,F8',
        'A2-A3,A6-A9,A12,A15-A20,A23,B13-B14',
        'A1,B17,B20-B24,E3,E5,E7,F5,F7,Trk20-Trk25,Trk27,Trk30'
    ] 

    print("\n== Converting interface ranges strings to list of interfaces ==")
    for i_str in i_strings:
        print(i_str, " ----> ", convert_interfaces_range(i_str))

def debug_get_vlans_names():
    for f in text_files():
        print(os.path.basename(f), '---> ', get_vlans_names(f))

def debug_get_ip_address():
    table = []
    headers = ["File Name", "IP"]
    for f in text_files():
        table.append([os.path.basename(f), get_ip_address(f)])
    print(tabulate(table, headers))

if __name__ == "__main__":
    main()
    #debug_get_hostname()
    #debug_get_site()
    #debug_get_device_role()
    #debug_get_modules()
    #debug_get_trunks()
    #debug_get_interface_names()
    #debug_get_vlans()
    #debug_get_vlans_names()
    #debug_get_untagged_vlans()
    #debug_convert_interfaces_range()
    debug_get_ip_address()
