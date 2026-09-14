#!/usr/bin/env python3
"""
Device Specifications Database Access Class

Interact with the device_specs PostgreSQL database via the DeviceSpecifications class.

Install required packages:
    - pip install psycopg-binary pyyaml
    - sudo pacman -Sy python-psycopg

Secure password options:
    1. Environment variable: DB_PASSWORD='pass' python script.py
    2. Ansible vault: password_from='vault', vault_file='path/to/vault'
    3. Config file: password_from='config', config_file='path/to/config.yaml'

Fix the PostgreSQL Permissions. Have to grant 'netzadmin' user permission to create tables
in the 'public' schema.

On the DB Server do:
    sudo -u postgres psql -d network_inventory

    # inside the `psql` prompt:

    GRANT CREATE ON SCHEMA public TO netzadmin;
"""

import os
import subprocess
import yaml
from pathlib import Path
import psycopg
from psycopg import OperationalError
from psycopg.rows import dict_row
from typing import List, Dict, Optional, Any, Tuple

# -- Defaut Paths ---
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
_NETBOX_DIR = _PROJECT_DIR / ".." / "netbox"

# STD strings
DEFAULT_VAULT_FILE = str(_NETBOX_DIR / "sql_scripts" / "vault")
DEFAULT_VAULT_PASS_FILE = str(_NETBOX_DIR / "src" / "keys" / "vault_pass_netbox")

#HOST = "192.168.122.140"
HOST = "netbox-bb"

class DeviceSpecifications:
    """Helper class for device_specs database operations with secure password handling."""

    def __init__(self, host: str = HOST, port: int = 5432,
                 dbname: str = 'network_inventory',
                 user: str = 'netzadmin',
                 password: Optional[str] = None,
                 password_from: str = 'vault',
                 vault_file: Optional[str] = DEFAULT_VAULT_FILE,
                 vault_password_file: str = DEFAULT_VAULT_PASS_FILE,
                 config_file: Optional[str] = None):
        
        retrieved_password = self._get_password(
            password, password_from, vault_file, vault_password_file, config_file
        )

        self.conn_params = {
            'host': host,
            'port': port,
            'dbname': dbname,
            'user': user,
            'password': retrieved_password
        }
        self.conn = None

    # ---------------------------------------------------------
    # Context Manager Methods (Optimization)
    # ---------------------------------------------------------
    def __enter__(self):
        """Allows using the class in a 'with' statement for persistent connections."""
        try:
            self.conn = psycopg.connect(**self.conn_params, row_factory=dict_row)
            return self
        except OperationalError as e:
            if "failed to resolve host" in str(e):
                raise ConnectionError(f"Cannot reach host '{self.conn_params['host']}' - hostname not found") from e
            elif "Connection refused" in str(e):
                raise ConnectionError(f"Connection refused by host '{self.conn_params['host']}' - is PostgreSQL running?") from e
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensures the connection is closed when exiting the 'with' block."""
        if self.conn:
            self.conn.close()

    # ---------------------------------------------------------
    # Security & Config Methods
    # ---------------------------------------------------------
    def _get_password(self, password: Optional[str], password_from: str,
                     vault_file: Optional[str], vault_password_file: str,
                     config_file: Optional[str]) -> str:
        """Routes password retrieval based on the chosen method."""
        match password_from:
            case 'env':
                return self._get_password_from_env()
            case 'vault':
                return self._get_password_from_vault(vault_file, vault_password_file)
            case 'config':
                return self._get_password_from_config(config_file)
            case 'direct':
                if not password:
                    raise ValueError("Password parameter required when password_from='direct'")
                print("WARNING: Using direct password is insecure. Consider using 'env', 'vault', or 'config'.")
                return password
            case _:
                raise ValueError(f"Invalid password_from value: '{password_from}'. "
                                 "Use 'env', 'vault', 'config', or 'direct'")

    def _get_password_from_env(self) -> str:
        if password := os.environ.get('DB_PASSWORD'):
            return password
        raise ValueError(
            "DB_PASSWORD environment variable not set.\n"
            "Usage: DB_PASSWORD='your_password' python script.py"
        )

    def _get_password_from_vault(self, vault_file: Optional[str], vault_password_file: str) -> str:
        if not vault_file:
            raise ValueError("vault_file parameter required when password_from='vault'")

        vault_path = Path(vault_file).expanduser().resolve()
        pass_path = Path(vault_password_file).expanduser().resolve()

        if not vault_path.exists():
            raise FileNotFoundError(f"Vault file not found: {vault_path}")
        if not pass_path.exists():
            raise FileNotFoundError(f"Vault password file not found: {pass_path}")

        try:
            result = subprocess.run(
                ['ansible-vault', 'view', str(vault_path), '--vault-password-file', str(pass_path)],
                capture_output=True, text=True, check=True
            )
            vault_data = yaml.safe_load(result.stdout)
            
            if password := vault_data.get('vault_sql_inventory_pass'):
                return password
            raise ValueError(f"vault_sql_inventory_pass not found. Available keys: {', '.join(vault_data.keys())}")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to read vault file: {e.stderr}")
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse vault YAML: {e}")

    def _get_password_from_config(self, config_file: Optional[str]) -> str:
        if not config_file:
            raise ValueError("config_file parameter required when password_from='config'")

        config_path = Path(config_file).expanduser().resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            if password := config_data.get('database', {}).get('password'):
                return password
            raise ValueError("database.password not found in config file")

        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse config YAML: {e}")

    # ---------------------------------------------------------
    # Database Operations
    # ---------------------------------------------------------
    def _execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Helper method to execute read queries and return dict rows."""
        if not self.conn or self.conn.closed:
            raise ConnectionError("Database connection is closed. Use the class within a 'with' block.")
        
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def initialize_schema(self) -> None:
        """
        Creates the 'device_specs' table schema if it does not already exist,
        along with a trigger to automatically manage the 'updated_at' timestamp.
        """
        if not self.conn or self.conn.closed:
            raise ConnectionError("Database connection is closed. Use the class within a 'with' block.")

        # SQL to create the table and an auto-update trigger for updated_at
        schema_query = """
        -- 1. Create the table
        CREATE TABLE IF NOT EXISTS device_specs (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            hostname VARCHAR(255) NOT NULL UNIQUE,
            type VARCHAR(100),
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        -- 2. Create a function to update the 'updated_at' column
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';

        -- 3. Bind the trigger to the table (fails safely if it already exists)
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_updated_at') THEN
                CREATE TRIGGER set_updated_at
                BEFORE UPDATE ON device_specs
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
            END IF;
        END $$;
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(schema_query)
            # DDL/Write operations require a commit to save to the database
            self.conn.commit()
            print("Database schema successfully initialized.")
        except Exception as e:
            # Rollback the transaction if something fails
            self.conn.rollback()
            raise RuntimeError(f"Failed to initialize schema: {e}")

    def get_all_devices(self, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Get devices from inventory.

        Args:
            is_active: If True/False, filter by status. If None, return all.

        Returns:
            List of device records as dictionaries.
        """
        query = "SELECT * FROM device_specs"
        params = ()

        if is_active is not None:
            query += " WHERE active = %s"
            params = (is_active,)

        query += " ORDER BY hostname;"
        
        return self._execute_query(query, params)

    def add_device(self, hostname: str, device_type: Optional[str] = None, is_active: bool = True) -> Tuple[Dict[str, Any], str]:
        """
        Add a new device, or update an existing one if the specifications differ.

        Args:
            hostname: The unique hostname of the device.
            device_type: Optional string for the model or type.
            is_active: State of the device (defaults to True).

        Returns:
            A tuple containing:
            - The device record as a dictionary.
            - A status string: 'inserted', 'updated', or 'ignored'.
        """
        if not self.conn or self.conn.closed:
            raise ConnectionError("Database connection is closed. Use the class within a 'with' block.")
        
        try:
            with self.conn.cursor() as cur:
                # 1. Check if the device already exists
                cur.execute("SELECT * FROM device_specs WHERE hostname = %s;", (hostname,))
                existing_device = cur.fetchone()
                
                if existing_device:
                    # 2. Compare current values with the new input
                    if existing_device['type'] == device_type and existing_device['active'] == is_active:
                        # Nothing changed, return the existing device
                        return existing_device, "ignored"
                    
                    # 3. Values differ, update the record
                    update_query = """
                        UPDATE device_specs 
                        SET type = %s, active = %s 
                        WHERE hostname = %s 
                        RETURNING *;
                    """
                    cur.execute(update_query, (device_type, is_active, hostname))
                    updated_device = cur.fetchone()
                    self.conn.commit()
                    return updated_device, "updated"
                
                else:
                    # 4. Device does not exist, insert it
                    insert_query = """
                        INSERT INTO device_specs (hostname, type, active)
                        VALUES (%s, %s, %s)
                        RETURNING *;
                    """
                    cur.execute(insert_query, (hostname, device_type, is_active))
                    new_device = cur.fetchone()
                    self.conn.commit()
                    return new_device, "inserted"

        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to process device '{hostname}': {e}")

    def delete_device(self, hostname: Optional[str] = None, device_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Delete a device from the database by either its hostname or ID.

        Args:
            hostname: The hostname of the device to delete.
            device_id: The ID of the device to delete.

        Returns:
            The deleted device record as a dictionary, or None if no record was found.
            
        Raises:
            ValueError: If neither or both arguments are provided.
        """
        if not (hostname or device_id) or (hostname and device_id):
            raise ValueError("You must provide exactly one of 'hostname' or 'device_id'.")

        if not self.conn or self.conn.closed:
            raise ConnectionError("Database connection is closed. Use the class within a 'with' block.")
        
        try:
            with self.conn.cursor() as cur:
                if hostname:
                    query = "DELETE FROM device_specs WHERE hostname = %s RETURNING *;"
                    cur.execute(query, (hostname,))
                else:
                    query = "DELETE FROM device_specs WHERE id = %s RETURNING *;"
                    cur.execute(query, (device_id,))
                
                deleted_device = cur.fetchone()
                
            # Write operations require a commit!
            self.conn.commit()
            return deleted_device
            
        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to delete device: {e}")

    def get_device_type(self, hostname: str) -> Optional[str]:
        """
        Retrieve the type of a specific device by its hostname.

        Args:
            hostname: The exact hostname of the device.

        Returns:
            The device type as a string, or None if the device does not exist 
            or has no type defined.
        """
        if not self.conn or self.conn.closed:
            raise ConnectionError("Database connection is closed. Use the class within a 'with' block.")
        
        query = "SELECT type FROM device_specs WHERE hostname = %s LIMIT 1;"
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (hostname,))
                result = cur.fetchone()
                
            if result:
                return result['type']
            return None
            
        except Exception as e:
            raise RuntimeError(f"Failed to fetch type for device '{hostname}': {e}")