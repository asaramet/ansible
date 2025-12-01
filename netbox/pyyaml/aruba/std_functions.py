#!/usr/bin/env  python3

# Standard reusable functions

import re, sys, yaml, logging
from pathlib import Path
from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from functions import recursive_section_search, campuses

# Configure logging
logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for convert_range() - performance optimization
_RANGE_NON_DIGIT_RE = re.compile(r'[^\d]+')
_RANGE_DIGIT_RE = re.compile(r'\d+')

# Path definitions
script_path = Path(__file__).resolve()
aruba_dir = script_path.parent
pyyaml_dir = aruba_dir.parent
project_dir = pyyaml_dir.parent
data_folder = project_dir / 'data'

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
    'JL075A': 'hpe-aruba-3810m-16sfpp-2-slot-switch',

    # Aruba OS-CX devices
    'JL679A': 'hpe-aruba-6100-12g-poe4-2sfpp',
    'JL679A_stack': 'hpe-aruba-6100-12g-poe4-2sfpp',
    'JL658A': 'hpe-aruba-6300m-24sfpp-4sfp56',
    'JL658A_stack': 'hpe-aruba-6300m-24sfpp-4sfp56',
    'JL659A': 'hpe-aruba-6300m-48sr5-poe6-4sfp56',
    'JL659A_stack': 'hpe-aruba-6300m-48sr5-poe6-4sfp56',
}

# --- Base functions ---
def search_line(expression, t_file):
    """
    Search for a line matching a regex pattern in a file.

    Args:
        expression: Regex pattern string to search for
        t_file: Path to file to search (Path object or string)

    Returns:
        str: First matching line, or None if no match found
    """
    # Pre-compile regex pattern for better performance
    pattern = re.compile(expression)

    # Convert to Path object if needed
    file_path = Path(t_file) if not isinstance(t_file, Path) else t_file

    with open(file_path, "r") as f:
        for line in f:  # Iterate line-by-line instead of loading entire file
            if pattern.search(line):
                return line

    return None
    
def recursive_search(pattern, text, start=False):
    """
    Search lines in a text recursively, when line starts with or contains a pattern.

    Args:
        pattern: String pattern to search for
        text: List of text lines to search through
        start: If True, match lines that start with pattern; if False, match lines containing pattern

    Returns:
        list: List of matching lines (stripped)
    """
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

# Return a list of file paths from a folder
def config_files(data_folder):
    """
    Return a list of file paths from a folder.

    Args:
        data_folder: Path object or string representing the folder

    Returns:
        list: List of Path objects for files in the folder
    """
    folder = Path(data_folder) if not isinstance(data_folder, Path) else data_folder
    return [f for f in folder.iterdir() if f.is_file()]

def convert_range(range_str):
    """
    Convert a range string to a list of elements.

    Examples:
        'A1-A4' -> ['A1', 'A2', 'A3', 'A4']
        'B10-B13' -> ['B10', 'B11', 'B12', 'B13']
        '1/1-1/4' -> ['1/1', '1/2', '1/3', '1/4']
        '2/A2-2/A4' -> ['2/A2', '2/A3', '2/A4']
        'A21' -> ['A21'] (no range)

    Args:
        range_str: String representing a range (e.g., 'A1-A4') or single element

    Returns:
        list: List of elements in the range

    Raises:
        ValueError: If prefixes in start and end don't match
    """
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
    non_digit_match = _RANGE_NON_DIGIT_RE.match(start)
    if non_digit_match:
        prefix_start += non_digit_match.group()
        prefix_end += _RANGE_NON_DIGIT_RE.match(end).group()

        # Ensure the prefixes are the same
        if prefix_start != prefix_end:
            raise ValueError("Prefixes do not match")

        start = _RANGE_DIGIT_RE.search(start).group()
        end = _RANGE_DIGIT_RE.search(end).group()

    if prefix_start:
        # Generate the list of elements
        return [f"{prefix_start}{num}" for num in range(int(start), int(end) + 1)]

    return [num for num in range(int(start), int(end) + 1)]

def convert_interfaces_range(interfaces_string):
    """
    Convert an interface range string to a list of (stack, interface) tuples.

    Examples:
        'B10-B13,B15-B20,E2,E4' -> [('0','B10'), ('0','B11'), ('0','B12'), ('0','B13'),
                                     ('0','B15'), ('0','B16'), ('0','B17'), ('0','B18'),
                                     ('0','B19'), ('0','B20'), ('0','E2'), ('0','E4')]
        '1/2-1/4,1/16,2/1' -> [('1','1/2'), ('1','1/3'), ('1','1/4'), ('1','1/16'), ('2','2/1')]
        'A1,Trk1-Trk2' -> [('0','A1'), ('0','Trk1'), ('0','Trk2')]

    Args:
        interfaces_string: Comma-separated string of interface ranges and single interfaces

    Returns:
        list: List of (stack, interface) tuples where stack is '0' for non-stacked interfaces
    """
    i_list = []

    for el in interfaces_string.split(","):
        stack = '0'
        if '-' in el:
            for interface in convert_range(el):
                # convert range string to list interfaces list and save them
                if '/' in str(interface):
                    stack, _ = interface.split('/')
                i_list.append((stack, interface))
            continue

        if '/' in str(el):
            stack = el.split('/')[0]
        i_list.append((stack, el))

    return i_list

def device_type(hostname):
    """
    Return device type for a given hostname.

    Args:
        hostname: Hostname string to lookup

    Returns:
        str: Device type if found, None otherwise
    """
    for device_type, d_list in devices().items():
        if hostname in d_list:
            return device_type

    return None

# --- Get functions ---
def get_os_version(t_file):
    """
    Extract OS version from Aruba/HPE config file.

    Detects two formats:
    - AOS (Aruba OS): Files containing "; Ver"
    - Other versions: Lines starting with "!Version"

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        str: "AOS" for Aruba OS, version string for others, or None if not found
    """
    if search_line("; Ver", t_file):
        return "AOS"

    os_line = search_line("!Version", t_file)
    if os_line:
        return os_line.split(' ')[1]

    return None

def get_hostname(t_file):
    """
    Extract hostname and stack member information from config file.

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        dict: Dictionary mapping member ID to hostname
              - Single switch: {'0': 'hostname'}
              - Stack: {'1': 'hostname-1', '2': 'hostname-2', ...}
    """
    # Convert to Path object if needed
    file_path = Path(t_file) if not isinstance(t_file, Path) else t_file

    hostname_line = search_line("hostname", file_path)
    hostname = hostname_line.split()[1].replace('"', '') if not hostname_line.isspace() else " "

    # Check if this is a stack
    if not search_line("member", file_path):
        # Not a stack
        return {'0': hostname}

    # Stack configuration - read file and extract member information
    with open(file_path, "r") as f:
        text = [line.strip() for line in f]  # Read and strip in one comprehension

    stacks = set()
    for line in recursive_search("member", text):
        line_data = line.split()

        if 'vsf' in line_data:  # Aruba OS-CX switches
            stacks.add(line_data[2])
        else:
            stacks.add(line_data[1])

    hostnames = {}
    for member in stacks:
        hostnames[member] = f"{hostname}-{member}"

    return hostnames

def site_slug(t_file):
    """
    Generate a site slug based on hostname and location.

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        str: Site slug (e.g., 'hengstenbergareal', 'campus-n', 'campus-s')
    """
    hostnames = get_hostname(t_file)
    hostname = hostnames['0'] if '0' in hostnames else hostnames['1']

    location = get_location(t_file)
    if location:
        location, _, _ = location
        location, _ = location.split('.', 1)

    if location == 'W20':
        return "hengstenbergareal"

    return f"campus-{campuses[hostname[1]]}"

def get_location(file):
    """
    Extract and normalize location information from config file.

    Parses location strings in formats like:
    - "V.C01.123" (rack in building C, room 123)
    - "C01.123" (building C, room 123)

    Args:
        file: Path to config file (Path object or string)

    Returns:
        tuple: (normalized_location, room, rack_flag) or None if no location found
               - normalized_location: Format "C01.123"
               - room: Room number string
               - rack_flag: Boolean indicating if this is a rack location (starts with "V.")
    """
    location_line = search_line("location", file)

    if not location_line or location_line.isspace():
        return None

    location = location_line.split()[-1].strip('"')
    rack = False

    if location.split('.')[0] == 'V':
        location = location[2:]
        rack = True

    building, room = location.split(".", 1)

    building_nr = str(int(building[1:]))  # convert "01" to "1", for example
    if len(building_nr) == 1:
        # add "0" to single digit buildings
        building_nr = "0" + building_nr

    location = f"{building[0]}{building_nr}.{room}"

    return (location, room, rack)

def get_flor_nr(room_nr):
    """
    Extract floor number from room number string.

    Examples:
        '123' -> '1' (first character)
        'u05' -> '-0' (underground, 'u' prefix becomes negative)
        '205' -> '2'

    Args:
        room_nr: Room number string (e.g., '123', 'u05', '205')

    Returns:
        str: Floor number as string, or None if room_nr is None
    """
    if not room_nr:
        return None

    if room_nr[0] == 'u':
        room_nr = '-' + room_nr[1:]

    flor = room_nr[0]
    flor = int(room_nr[:2]) if flor == '-' else int(flor)

    return str(flor)

def get_flor_name(room_nr):
    """
    Get floor number and German floor name from room number.

    Args:
        room_nr: Room number string (e.g., '123', 'u05')

    Returns:
        tuple: (floor_number, floor_name_german)
               - Negative/0 floors use predefined names (Untergeschoss, Erdgeschoss)
               - Positive floors use format "Etage N"

    Examples:
        'u05' -> ('-0', 'Untergeschoss')
        '005' -> ('0', 'Erdgeschoss')
        '123' -> ('1', 'Etage 1')
        '205' -> ('2', 'Etage 2')
    """
    flor_name = {
        "-3": "Untergeschoss 3",
        "-2": "Untergeschoss 2",
        "-1": "Untergeschoss",
        "0": "Erdgeschoss"
    }

    flor = get_flor_nr(room_nr)
    if int(flor) < 1:
        return (flor, flor_name[flor])

    return (flor, f"Etage {flor}")

def get_parent_location(location):
    """
    Get parent location slug for a building.

    Args:
        location: Location string (e.g., 'C01.123', 'S08.205')

    Returns:
        str: Parent location slug (e.g., 'fl-gebude-01', 'sm-gebude-08')

    Examples:
        'F01.123' -> 'fl-gebude-01'
        'G05.456' -> 'gp-gebude-05'
        'S08.205' -> 'sm-gebude-08'
        'W20.100' -> 'ws-gebude-20'
    """
    prefixes = {
        "F": "fl",
        "G": "gp",
        "S": "sm",
        "W": "ws"
    }

    building = location.split(".")[0]
    return f"{prefixes[building[0]]}-gebude-{building[1:]}"

def floor_slug(location):
    """
    Generate floor location slug from location string.

    Args:
        location: Location string or tuple (location_string, room, rack)

    Returns:
        str: Floor slug in format "building-floor_number-floor_name" or None if no location

    Examples:
        'S01.205' -> 's01-2-etage-2'
        'C08.005' -> 'c08-0-erdgeschoss'
        'F02.u05' -> 'f02-0-untergeschoss'
        ('S01.205', '205', False) -> 's01-2-etage-2'
    """
    if not location:
        return None

    if isinstance(location, tuple):
        location = location[0]

    flor_tags = {
        "-3": "untergeschoss-3",
        "-2": "untergeschoss-2",
        "-1": "untergeschoss",
        "0": "erdgeschoss"
    }
    building, room_nr = location.split(".", 1)
    flor = get_flor_nr(room_nr)
    flor_fx = str(abs(int(flor)))  # string to use in the label
    flor_tag = flor_tags[flor] if int(flor) < 1 else f"etage-{flor}"

    return f"{building.lower()}-{flor_fx}-{flor_tag}"

def room_slug(location):
    """
    Generate room location slug from location string.

    Args:
        location: Location string or tuple (location_string, room, rack)

    Returns:
        str or tuple: Room slug in format "building-room_number", or
                      tuple (room_slug, rack_number) if rack is specified,
                      or None if no location

    Examples:
        'S08.205' -> 's08-205'
        'C01.u05' -> 'c01-u05'
        'F02.123.C2' -> ('f02-123', 'c2')  # with rack
        ('S08.205', '205', False) -> 's08-205'
    """
    if not location:
        return None

    if isinstance(location, tuple):
        location = location[0]

    building, room_nr = location.split(".", 1)

    # convert '-' to 'u' for underground rooms
    if room_nr[0] == '-':
        room_nr = f"u{room_nr[1:]}"

    # return tuple if rack number is mentioned
    if len(room_nr.split(".")) > 1:
        room_nr, rack = room_nr.split(".", 1)
        return (f"{building.lower()}-{room_nr.lower()}", rack.lower())

    return f"{building.lower()}-{room_nr.lower()}"
    

def get_lags(t_file):
    """
    Extract LAG (Link Aggregation Group) configurations from Aruba config file.

    Supports two formats:
    - ArubaOS-CX: 'interface lag <number>' with interface assignments
    - Aruba ProCurve/iOS: 'trunk <interfaces> <name> lacp'

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        list: List of dictionaries with keys:
              - 'name': LAG name (e.g., 'lag 1', 'trk1')
              - 'interfaces': Comma-separated interface list (e.g., '9-10', '1/1/26,1/1/27')

    Examples:
        ArubaOS-CX format -> [{'name': 'lag 1', 'interfaces': '1/1/26,1/1/27'}]
        ProCurve format -> [{'name': 'trk1', 'interfaces': '9-10'}]
    """
    # Convert to Path object if needed
    file_path = Path(t_file) if not isinstance(t_file, Path) else t_file

    with open(file_path, "r") as f:
        text = [line for line in f]  # Read lines into list

    lags = []
    os_version = get_os_version(file_path)

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

            # Keep the full interface name (e.g., '1/1/26') for OS-CX configs
            interface_name = interface

            if lag_number not in lag_dict:
                lag_dict[lag_number] = []
            lag_dict[lag_number].append(interface_name)

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
    """
    Extract LAG to stack member mappings from config file.

    Processes LAG configurations to create tuples mapping LAG names to stack members.
    For stacked switches, extracts the stack number from interface names (e.g., '1/1/26' -> '1').
    For non-stacked switches, defaults to stack '0'.

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        list: List of tuples (lag_name, stack_number)
              - lag_name: LAG name in title case (e.g., 'Lag 1', 'Trk1')
              - stack_number: Stack member number as string (e.g., '1', '2', or '0')

    Examples:
        Stacked switch: [('Lag 1', '1'), ('Lag 1', '1'), ('Trk2', '2')]
        Single switch: [('Trk1', '9'), ('Trk1', '10')]
    """
    lags = []

    for lag_dict in get_lags(t_file):
        for interface in lag_dict['interfaces'].split(','):
            interface = interface.split('/')[0]
            lags.append((lag_dict['name'].title(), interface))

    return lags

def get_interface_names(t_file):
    """
    Extract interface names and descriptions from config file.

    Searches for both 'name' and 'description' attributes within interface blocks.

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        list: List of tuples (interface, name_or_description)
              Examples: [('1/1/1', 'Uplink to Core'), ('1/1/2', 'Server Port')]
    """
    # Convert to Path object if needed
    file_path = Path(t_file) if not isinstance(t_file, Path) else t_file

    with open(file_path, "r") as f:
        text = [line for line in f]

    names = recursive_section_search(text, 'interface', 'name')
    names += recursive_section_search(text, 'interface', 'description')

    return names

def get_vlans(t_file):
    """
    Extract VLAN definitions with names from config file.

    Searches for VLAN blocks with 'name' attributes and automatically adds default VLAN 1.

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        set: Set of tuples (vlan_id, vlan_name)
             Always includes ('1', 'DEFAULT_VLAN')

    Examples:
        {('1', 'DEFAULT_VLAN'), ('10', 'ADMIN'), ('20', 'USERS'), ('100', 'SERVERS')}
    """
    # Convert to Path object if needed
    file_path = Path(t_file) if not isinstance(t_file, Path) else t_file

    with open(file_path, "r") as f:
        text = [line for line in f]

    vlans = set(recursive_section_search(text, 'vlan', 'name '))
    vlans.add(('1', 'DEFAULT_VLAN'))
    return vlans

def get_untagged_vlans(t_file):
    """
    Extract untagged VLAN assignments from config file.

    Handles three different configuration formats:
    1. Aruba OS ProCurve: VLAN blocks with 'untagged <interfaces>' statements
    2. ArubaOS-CX Access VLANs: Interface blocks with 'vlan access <id>' statements
    3. ArubaOS-CX Native VLANs: Interface blocks with 'vlan trunk native <id>' statements

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        list: List of tuples (vlan_id, interface_list, is_trunk_native)
              - vlan_id: VLAN ID as string
              - interface_list: Comma-separated interface names or range string
              - is_trunk_native: None for ProCurve, False for access, True for trunk native

    Examples:
        ProCurve: [('10', 'A1-A8,B2', None), ('20', 'C1-C4', None)]
        OS-CX Access: [('10', '1/1/1,1/1/2', False), ('20', '1/1/5', False)]
        OS-CX Native: [('100', 'lag 1', True)]
    """
    # Convert to Path object if needed
    file_path = Path(t_file) if not isinstance(t_file, Path) else t_file

    with open(file_path, "r") as f:
        text = [line for line in f]

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

    # --- LAG Native VLANs ---
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
    """
    Extract tagged VLAN assignments from config file.

    Handles two different configuration formats:
    1. ArubaOS-CX: Interface blocks with 'vlan trunk allowed' and 'vlan trunk native' statements
       - Parses trunk interfaces and their allowed VLANs
       - Excludes native VLANs (they are untagged)
       - Supports 'all' keyword for all VLANs
       - Formats LAG names properly (e.g., 'lag 1' -> 'Lag 1')
    2. Aruba OS ProCurve: VLAN blocks with 'tagged <interfaces>' statements

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        list: List of tuples (vlan_id, interface_list)
              - vlan_id: VLAN ID as string
              - interface_list: Comma-separated interface names

    Examples:
        ArubaOS-CX: [('10', '1/1/1,1/1/2,Lag 1'), ('20', '1/1/5,Lag 2')]
        ProCurve: [('10', 'A1-A8,B2'), ('20', 'C1-C4,Trk1')]
    """
    # Convert to Path object if needed
    file_path = Path(t_file) if not isinstance(t_file, Path) else t_file

    with open(file_path, "r") as f:
        text = [line for line in f]

    os_version = get_os_version(file_path)

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

def get_modules(t_file):
    """
    Extract module/slot information from modular Aruba/HPE switches.

    Handles multiple switch types with different module configurations:
    - Aruba 2920 stacks (hardcoded module mappings for specific hostnames)
    - Aruba modular chassis (e.g., 5406R with line cards)
    - ProCurve 2910al with expansion modules
    - HPE OS flexible-module configurations
    - Aruba OS module configurations

    Args:
        t_file: Path to config file (Path object or string)

    Returns:
        list: List of dictionaries with keys:
              - hostname: Device hostname (with stack number for stacks)
              - module: Module slot identifier (e.g., 'A', 'B', '1', '2')
              - type: Module type/model (e.g., 'j9729a', 'j9993a')
              - name: Module name (optional, e.g., 'Module A', 'Uplink')
              - stack: Stack member number (optional)

    Examples:
        [{'hostname': 'switch-1', 'module': 'A', 'type': 'j9729a',
          'name': 'Module A', 'stack': '1'}]
    """
    # Convert to Path object if needed
    file_path = Path(t_file) if not isinstance(t_file, Path) else t_file

    modules = []

    stacks_dict = {
        '1': 'A', '2': 'B', '3': 'C', '4': 'D', '5': 'E', '6': 'F',
        '7': 'G', '8': 'H', '9': 'I', '10': 'J', '11': 'K', '12': 'L'
    }

    hostnames = get_hostname(file_path)
    stack = '0'

    with open(file_path, "r") as f:
        text = [line for line in f]

    if '0' in hostnames:
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

    if clean_hostname in module_2920:
        for stack, module, m_type in module_2920[clean_hostname]:
            if '0' in hostnames:
                stack = '0'
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

    if clean_hostname in module_chassis:
        for stack, module, m_type in module_chassis[clean_hostname]:
            modules.append({'hostname': hostnames[stack], 'module': module, 'type': m_type, 'name': module, 'stack': stack})
        return modules

    # ProCurve 2910al
    module_2910al = {
        'rsgw2u127ap': [('A', 'j9008a')],
        'rsgw2u127bp': [('A', 'j9008a')]
    }

    if clean_hostname in module_2910al:
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

            if m_list[1] in stacks_dict:
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

        if module in stacks_dict:
            module = stacks_dict[module]

        modules.append({'hostname': hostnames[stack], 'module': module, 'type': m_list[3], 'name': 'Uplink', 'stack': stack})

    return modules

def devices():
    """
    Load devices dictionary from YAML configuration file.

    Returns:
        dict: Device type to hostname list mapping, e.g.,
              {'aruba-2930m-48g': ['rggw1004sp', 'rsgw7009p'], ...}
              Returns None if file cannot be loaded.

    Example:
        devices = devices()
        # {'aruba-2930m-48g': ['switch1', 'switch2'], ...}
    """
    yaml_file = project_dir.joinpath("src", "devices.yaml")

    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)

    return None

def device_type(hostname):
    """
    Look up device type for a given hostname from devices.yaml.

    Args:
        hostname: Device hostname to look up

    Returns:
        str: Device type slug (e.g., 'aruba-2930m-48g') or None if not found

    Example:
        device_type('rggw1004sp')  # Returns 'aruba-2930m-48g'
    """
    for dev_type, d_list in devices().items():
        if hostname in d_list:
            return dev_type

    return None

def interfaces_dict():
    """
    Load interfaces dictionary from YAML configuration file.

    Returns:
        dict: Interface type mappings for device models
              Returns None if file cannot be loaded.

    Example:
        interfaces = interfaces_dict()
        # {'aruba-2930m-48g': {'1-48': '1000base-t', ...}, ...}
    """
    yaml_file = project_dir.joinpath("src", "interfaces.yaml")

    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)

    return None

def module_types_dict():
    """
    Load module types dictionary from YAML configuration file.

    Returns:
        dict: Module type to NetBox slug mappings
              Returns None if file cannot be loaded.

    Example:
        module_types = module_types_dict()
        # {'j9729a': 'aruba-2920-2sfp-module', ...}
    """
    yaml_file = project_dir.joinpath("src", "module_types.yaml")

    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)

    return None

def convert_prefix(range_str, new_prefix):
    """
    Convert interface range prefix from 'A' to a different prefix.

    Useful for stack members where interfaces are prefixed with stack letters
    (A, B, C, etc.) and need to be converted to a different prefix.

    Args:
        range_str: Interface range string (e.g., 'A1-A24', 'A1')
        new_prefix: New prefix to replace 'A' with (e.g., 'B', 'C')

    Returns:
        str: Range string with new prefix or original if prefix is not 'A'

    Examples:
        convert_prefix('A1-A24', 'B')  # Returns 'B1-B24'
        convert_prefix('A5', 'C')      # Returns 'C5'
        convert_prefix('B1-B10', 'C')  # Returns 'B1-B10' (no change)
    """
    if range_str[0] == "A":
        if '-' in range_str:
            start, end = range_str.split('-')
            return f"{new_prefix}{start[1:]}-{new_prefix}{end[1:]}"
        return f"{new_prefix}{range_str[1:]}"

    return range_str

def modules_interfaces(model, stack_prefix="A"):
    """
    Load module interface configurations with stack prefix conversion.

    Reads interface types, PoE modes, and PoE types for a given module model
    and converts interface ranges from 'A' prefix to the specified stack prefix.

    Args:
        model: Module model code (e.g., 'j9729a')
        stack_prefix: Stack member prefix (default: 'A')

    Returns:
        dict: Dictionary with keys 'types', 'poe_mode', 'poe_types', each containing
              interface ranges mapped to their respective values

    Example:
        modules_interfaces('j9729a', 'B')
        # Returns: {'types': {'B1-B2': '1000base-x-sfp'},
        #           'poe_mode': {'B1-B2': None},
        #           'poe_types': {'B1-B2': None}}
    """
    model = model.lower()
    yaml_file = project_dir.joinpath("src", "modules_interfaces.yaml")

    with open(yaml_file, 'r') as f:
        modules = yaml.safe_load(f)

    data = {'types': {}, 'poe_mode': {}, 'poe_types': {}}

    for key in modules['types'][model]:
        converted_key = convert_prefix(key, stack_prefix)
        data['types'][converted_key] = modules['types'][model][key]

        # Handle optional poe_mode and poe_types entries
        data['poe_mode'][converted_key] = (
            modules['poe_mode'][model].get(key) if 'poe_mode' in modules and model in modules['poe_mode'] else None
        )
        data['poe_types'][converted_key] = (
            modules['poe_types'][model].get(key) if 'poe_types' in modules and model in modules['poe_types'] else None
        )

    return data

#----- Debugging -------
def debug_config_files(data_folder):
    table = []
    headers = ["File name", "Path"]
    for f in config_files(data_folder):
        table.append([f.name, str(f)])
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
        table.append([f.name, get_os_version(f)])
    print("\n== Debug: get_os_version ==")
    print(tabulate(table, headers, "github"))

def debug_get_hostname(data_folder):
    table = []
    headers = ["File name", "Hostname"]
    for f in config_files(data_folder):
        table.append([f.name, get_hostname(f)])
    print("\n== Debug: get_hostname ==")
    print(tabulate(table, headers, "github"))

def debug_site_slug(data_folder):
    table = []
    headers = ["File Name", "Location", "Site"]
    for f in config_files(data_folder):
        hostname = f.name
        table.append([hostname, get_location(f), site_slug(f)])
    print("\n== Debug: site_slug ==")
    print(tabulate(table, headers, "github"))

def debug_get_location(data_folder):
    table = []
    headers = ["File Name", "Location"]
    for f in config_files(data_folder):
        table.append([f.name, get_location(f)])
    print("\n== Debug: get_location() ==")
    print(tabulate(table, headers))

def debug_get_room_location(data_folder):
    table = []
    headers = ["File Name", "Room Location"]

    for f in config_files(data_folder):
        location = get_location(f)

        if location:
            location, _ = location

        table.append([f.name, get_room_location(location)])
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

        table.append([f.name, location, get_flor_nr(room)])
    print("\n== Debug: get_flor_nr() ==")
    print(tabulate(table, headers))

def debug_get_lags(data_folder):
    table = []
    headers = ["File Name", "lags"]
    for f in config_files(data_folder):
        table.append([f.name, get_lags(f)])
    print("\n== Debug: get_lags ==")
    print(tabulate(table, headers))

def debug_get_lag_stack(data_folder):
    table = []
    headers = ["File Name", "lags sets"]
    for f in config_files(data_folder):
        table.append([f.name, get_lag_stack(f)])
    print("\n== Debug: get_lags ==")
    print(tabulate(table, headers))

def debug_get_interface_names(data_folder):
    print("\n== Debug: get_interface_names ==")
    for f in config_files(data_folder):
        print(f.name, '---> ', get_interface_names(f))

def debug_get_vlans(data_folder):
    print("\n== Debug: get_vlans ==")
    for f in config_files(data_folder):
        print(f.name, '---> ', get_vlans(f))

def debug_get_untagged_vlans(data_folder):
    print("\n== Collect interfaces ranges for untagged vlans ==")
    for f in config_files(data_folder):
        print(f.name, '---> ', get_untagged_vlans(f))
    print('\n')

def debug_get_modules(data_folder):
    table = []
    headers = ["File Name", "Modules"]
    for f in config_files(data_folder):
        table.append([f.name, get_modules(f)])
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
        hostname = f.name
        location = get_location(f)
        slug = floor_slug(location)
        table.append([hostname, location, slug])
    print("\n== Debug: floor_slug ==")
    print(tabulate(table, headers, "github"))

def debug_room_slug(data_folder):
    table = []
    headers = ["File name", "Location", "Slug"]

    for f in config_files(data_folder):
        hostname = f.name
        location = get_location(f)
        slug = room_slug(location)
        table.append([hostname, location, slug])
    print("\n== Debug: room_slug ==")
    print(tabulate(table, headers, "github"))

if __name__ == "__main__":
    print("\n=== Debuging ===")

    data_folders = [
        #"aruba-8-ports",
        #"aruba-12-ports",
         "aruba-stack-2920",
        #"aruba-48-ports",
        #"hpe-8-ports",
        #"hpe-24-ports",
        #"aruba-stack",
        #"aruba-stack-2930",
        #"aruba-modular",
        #"aruba-modular-stack",
        #"procurve-single",
        #"procurve-modular",
        #"aruba_6100",
        #"aruba_6300"
    ]

    data_folder = project_dir.joinpath('data')
    for folder in data_folders:
        print(data_folder)
        configs_folder = data_folder.joinpath(folder)
        print(configs_folder)

        print("\n Folder: ", configs_folder)
        debug_get_hostname(configs_folder)
        debug_site_slug(configs_folder)
        debug_config_files(configs_folder)
        debug_get_os_version(configs_folder)
        debug_site_slug(configs_folder)
        debug_get_lags(configs_folder)
        debug_get_interface_names(configs_folder)
        debug_get_vlans(configs_folder)
        debug_get_untagged_vlans(configs_folder)
        debug_device_type(configs_folder)
        debug_get_modules(configs_folder)
        debug_get_location(configs_folder)
        debug_floor_slug(configs_folder)
        debug_room_slug(configs_folder)

    print("\n=== No files functions ===")
    debug_convert_range()
    debug_convert_interfaces_range()