#!/usr/bin/env python3

# Generate the latest Bareos variables to automate ansible get_url module

import yaml, requests, re
from sys import stdout

def get_url():
    """Return the latest EL number and a valid URL to download Bareos RPMs."""

    base_url = "https://download.bareos.org/current"

    try:
        response = requests.get(base_url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {base_url}: {e}")
        return None, None

    # Regex to match folder names like EL_7/, EL_8/, EL_10/ ...
    matches = re.findall(r'href="(EL_\d+)/"', response.text)
    if not matches: return None, None
    
    # Deduplicate and sort numerically 
    folders = sorted(set(matches), key=lambda x: int(x.split('_')[1]))

    # latest EL
    el = folders[-1]
    url = f"{base_url}/{el}/x86_64/"

    return el, url

def bareos_common(url):
    """
    Check if a downloadable bareos-common RPM exists in the given URL.
    Returns the first matching RPM filename or None if not found.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

    # Regex to match downloadable .rpm files
    matches = re.findall(r'href="(bareos-common[^"]+\.rpm)"', response.text)

    return matches[0] if matches else None

def parse_bareos_common_rpm(filename):
    """
    Parse a bareos-common RPM filename and extract version and rpm_nr.
    Example:
        "bareos-common-24.0.5~pre32.7c5f79a1e-91.el10.x86_64.rpm"
    Returns:
        ("24.0.5", "pre32.7c5f79a1e-91.el10.x86_64")
    """
    pattern = r"bareos-common-(\d+\.\d+\.\d+)~([^.]+.*)\.rpm"
    match = re.match(pattern, filename)
    if not match:
        return None, None

    return match.groups()

def bareos_vars():
    '''Collect bareos vars as a dict.'''

    el, url = get_url()

    if not url:
        return {'el': None, 'version': None, 'rpm_nr': None}

    rpm_filename = bareos_common(url)

    if not rpm_filename:
        return {'el': None, 'version': None, 'rpm_nr': None}

    version, rpm_nr = parse_bareos_common_rpm(rpm_filename)

    return {
        'el': el,
        'version': version,
        'rpm_nr': rpm_nr
    }

def main():
    # Output Bareos variables to stdout
    yaml.dump(bareos_vars(), stdout)

main()