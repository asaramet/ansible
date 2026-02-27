#!/usr/bin/env python3
"""
Automatically manage 'devices' table in the postgres database
"""

import yaml, typer
from pathlib import Path
from typing import Optional, List, Dict, Union

from std_app import initialize_inventory

app = typer.Typer(help = "Automatically manage 'devices' table in 'network_inventory' database")
inventory = initialize_inventory()

@app.command()
def test1(active_only: bool = False):
    """List all devices"""
    typer.secho(f"\u2713 Test 1")

@app.command()
def test2():
    """Test 2"""
    typer.secho(f"\u2713 Test 2")

if __name__ == "__main__":
    app()