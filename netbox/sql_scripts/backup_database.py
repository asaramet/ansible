#!/usr/bin/env python3
"""
Database Backup and Restore Script

Backup and restore the network_inventory PostgreSQL database.
Uses pg_dump and pg_restore for reliable database operations.

Install required packages:
    - pip install psycopg-binary
    - sudo pacman -Sy postgresql (or equivalent for your distro)

Usage:
    Backup: 
        - python backup_database.py backup 
        - python backup_database.py backup --output backup_file.sql
    Restore: 
        - python backup_database.py restore
        - python backup_database.py restore --input backup_file.sql
"""

import os, typer
import subprocess
from pathlib import Path
from typing import Optional

from std_objs import initialize_inventory, project_dir

app = typer.Typer(help="Backup and restore network_inventory database")

# Backup directory
BACKUP_DIR = project_dir / "data" / "backups"
BACKUP_FILE = BACKUP_DIR / "nw_backup.sqlc"

# Global inventory object
inventory = None

def ensure_backup_directory():
    """Create backup directory if it doesn't exist"""
    BACKUP_DIR.mkdir(exist_ok=True)

def backup_database(output_file: str, host: str, port: int, dbname: str,
                   user: str, password: Optional[str] = None):
    """
    Backup database using pg_dump
    
    Args:
        output_file: Path to output backup file
        host: Database host
        port: Database port
        dbname: Database name
        user: Database user
        password: Database password (optional)
    """
    ensure_backup_directory()
    
    # Build pg_dump command
    cmd = [
        'pg_dump',
        '-h', host,
        '-p', str(port),
        '-U', user,
        '-d', dbname,
        '-F', 'c',  # Custom format for compression
        '-f', str(output_file)
    ]
    
    # Set password environment variable if provided
    env = os.environ.copy()
    if password:
        env['PGPASSWORD'] = password
    
    try:
        typer.secho(f"Backing up database '{dbname}' to {output_file}...", fg=typer.colors.BLUE)
        result = subprocess.run(cmd, env=env, check=True, 
                              capture_output=True, text=True)
        typer.secho(f"✓ Database backup completed successfully", fg=typer.colors.GREEN)
        return True
    except subprocess.CalledProcessError as e:
        typer.secho(f"✗ Backup failed: {e.stderr}", fg=typer.colors.RED, err=True)
        return False
    except Exception as e:
        typer.secho(f"✗ Error during backup: {str(e)}", fg=typer.colors.RED, err=True)
        return False

def restore_database(input_file: str, host: str, port: int, dbname: str,
                    user: str, password: Optional[str] = None,
                    drop_existing: bool = False):
    """
    Restore database using pg_restore
    
    Args:
        input_file: Path to input backup file
        host: Database host
        port: Database port
        dbname: Database name
        user: Database user
        password: Database password (optional)
        drop_existing: Drop existing database before restore
    """
    # Check if backup file exists
    backup_path = Path(input_file)
    if not backup_path.exists():
        typer.secho(f"✗ Backup file not found: {input_file}", fg=typer.colors.RED, err=True)
        return False
    
    # Set password environment variable if provided
    env = os.environ.copy()
    if password:
        env['PGPASSWORD'] = password
    
    try:
        if drop_existing:
            typer.secho(f"Dropping existing database '{dbname}'...", fg=typer.colors.YELLOW)
            # Drop existing database
            drop_cmd = [
                'dropdb',
                '-h', host,
                '-p', str(port),
                '-U', user,
                dbname
            ]
            subprocess.run(drop_cmd, env=env, check=True, 
                          capture_output=True, text=True)
            
            typer.secho(f"Creating new database '{dbname}'...", fg=typer.colors.YELLOW)
            # Create new database
            create_cmd = [
                'createdb',
                '-h', host,
                '-p', str(port),
                '-U', user,
                dbname
            ]
            subprocess.run(create_cmd, env=env, check=True, 
                          capture_output=True, text=True)
        
        typer.secho(f"Restoring database '{dbname}' from {input_file}...", fg=typer.colors.BLUE)
        
        # Restore database with data-only mode
        restore_cmd = [
            'pg_restore',
            '-h', host,
            '-p', str(port),
            '-U', user,
            '-d', dbname,
            '-F', 'c',  # Custom format
            '-j', '4',  # Use 4 parallel jobs for faster restore
            '-a',       # Data only (no schema)
            '-n', 'public', # Only restore public schema
            str(input_file)
        ]
        
        result = subprocess.run(restore_cmd, env=env, check=True, 
                              capture_output=True, text=True)

        # If there were errors about ownership, try to fix them
        if "must be owner" in result.stderr:
            typer.secho("Fixing ownership issues...", fg=typer.colors.YELLOW)
            
            # Grant necessary permissions to the user
            grant_cmd = [
                'psql',
                '-h', host,
                '-p', str(port),
                '-U', user,
                '-d', dbname,
                '-c', f"ALTER TABLE public.devices OWNER TO {user};",
                '-c', f"ALTER INDEX public.idx_hostname OWNER TO {user};",
                '-c', f"ALTER INDEX public.idx_serial_number OWNER TO {user};",
                '-c', f"ALTER INDEX public.idx_hostname_serial OWNER TO {user};",
                '-c', f"ALTER INDEX public.idx_active OWNER TO {user};",
            ]
            
            subprocess.run(' '.join(grant_cmd), env=env, shell=True, 
                          capture_output=True, text=True)                
        
        typer.secho(f"✓ Database restore completed successfully", fg=typer.colors.GREEN)
        return True
        
    except subprocess.CalledProcessError as e:
        typer.secho(f"✗ Restore failed: {e.stderr}", fg=typer.colors.RED, err=True)
        # Try to continue even if there are some errors
        if 'must be owner' in e.stderr:
            typer.echo("Restore completed with some ownership warnings (data should be intact)", fg=typer.color.YELLOW)
            return True
        return False
    except Exception as e:
        typer.secho(f"✗ Error during restore: {str(e)}", fg=typer.colors.RED, err=True)
        return False

def generate_backup_filename() -> str:
    """Generate a timestamped backup filename"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return BACKUP_DIR / f"network_inventory_backup_{timestamp}.sqlc"

@app.callback()
def initialize():
    """Initialize database connection before running any command"""
    global inventory
    inventory = initialize_inventory()

@app.command()
#def backup(output: Optional[str] = typer.Option(None, "--output", "-o", 
def backup(output: Optional[str] = typer.Option(BACKUP_FILE, "--output", "-o", 
                   help="Output backup file path. If not specified, uses timestamped filename in backups/ directory")):
    """Backup the database"""
    
    # Generate output filename if not provided
    if not output:
        output = str(generate_backup_filename())
    
    try:
        # Extract connection parameters from the inventory object
        conn_params = inventory.conn_params
        
        # Perform backup
        success = backup_database(
            output, 
            conn_params['host'], 
            conn_params['port'], 
            conn_params['dbname'], 
            conn_params['user'], 
            conn_params['password']
        )
        
        if success:
            typer.secho(f"Backup saved to: {output}", fg=typer.colors.GREEN)
        else:
            raise typer.Exit(code=1)
            
    except Exception as e:
        typer.secho(f"✗ Error: {str(e)}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command()
#def restore(input_file: str = typer.Argument(..., help="Input backup file path"),
def restore(input_file: str = BACKUP_FILE,
           drop_existing: bool = typer.Option(False, "--drop", help="Drop existing database before restore")):
    """Restore the database from a backup file"""
    
    try:
        # Extract connection parameters from the inventory object
        conn_params = inventory.conn_params
        dbname = conn_params['dbname']
        
        # Confirm restore operation
        if not typer.confirm(f"Are you sure you want to restore database '{dbname}' from {input_file}? This will overwrite existing data!"):
            typer.secho("Restore cancelled", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)
        
        # Perform restore
        success = restore_database(
            input_file, 
            conn_params['host'], 
            conn_params['port'], 
            dbname, 
            conn_params['user'], 
            conn_params['password'],
            drop_existing
        )
        
        if not success:
            raise typer.Exit(code=1)
            
    except Exception as e:
        typer.secho(f"✗ Error: {str(e)}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command()
def purge():
    """Purge all data from the database (delete all entries)"""
    
    try:
        # Extract connection parameters from the inventory object
        conn_params = inventory.conn_params
        dbname = conn_params['dbname']
        
        # Confirm purge operation
        if not typer.confirm(f"Are you sure you want to PURGE all data from database '{dbname}'? This will DELETE ALL entries and cannot be undone!"):
            typer.secho("Purge cancelled", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)
        
        typer.secho(f"Purging all data from database '{dbname}'...", fg=typer.colors.YELLOW)
        
        # Build psql command to delete all data
        cmd = [
            'psql',
            '-h', conn_params['host'],
            '-p', str(conn_params['port']),
            '-U', conn_params['user'],
            '-d', dbname,
            '-c', 'DELETE FROM devices;'
        ]
        
        # Set password environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = conn_params['password']
        
        # Execute the purge command
        result = subprocess.run(cmd, env=env, check=True, 
                              capture_output=True, text=True)
        
        typer.secho(f"✓ Database purged successfully - all entries deleted", fg=typer.colors.GREEN)
        typer.secho(f"Database is now empty and ready for restore", fg=typer.colors.BLUE)
        
    except subprocess.CalledProcessError as e:
        typer.secho(f"✗ Purge failed: {e.stderr}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"✗ Error during purge: {str(e)}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()