#!/bin/bash
# Network Inventory Database - Command Line Interface
# Quick access to network_inventory database via psql

# Configuration
DB_NAME="network_inventory"
DB_USER="network_inventory"
#DB_HOST="localhost"
DB_HOST="192.168.122.140"
DB_PORT="5432"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to connect to database
db_connect() {
    PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" "$@"
}

# Function to display help
show_help() {
    echo "Network Inventory Database CLI"
    echo ""
    echo "Usage: $0 [command] [arguments]"
    echo ""
    echo "Commands:"
    echo "  connect              Connect to database interactively"
    echo "  add [hostname] [serial] [inventory] [active]"
    echo "                       Add new device"
    echo "  list                 List all devices"
    echo "  list-active          List only active devices"
    echo "  get [hostname]       Get device by hostname"
    echo "  update [hostname] [field] [value]"
    echo "                       Update device field"
    echo "  deactivate [hostname] Mark device as inactive"
    echo "  delete [hostname]    Delete device"
    echo "  search [term]        Search devices"
    echo "  count                Count total devices"
    echo ""
    echo "Environment Variables:"
    echo "  DB_PASSWORD          Database password (required)"
    echo ""
    echo "Examples:"
    echo "  DB_PASSWORD='pass' $0 list"
    echo "  DB_PASSWORD='pass' $0 add switch01.local SN12345 INV-001 true"
    echo "  DB_PASSWORD='pass' $0 get switch01.local"
}

# Check if password is set
if [ -z "$DB_PASSWORD" ]; then
    echo "Error: DB_PASSWORD environment variable not set"
    echo "Usage: DB_PASSWORD='your_password' $0 [command]"
    exit 1
fi

# Parse command
COMMAND="${1:-help}"

case "$COMMAND" in
    connect)
        echo -e "${BLUE}Connecting to ${DB_NAME} database...${NC}"
        db_connect
        ;;

    add)
        HOSTNAME="$2"
        SERIAL="$3"
        INVENTORY="$4"
        ACTIVE="${5:-true}"

        if [ -z "$HOSTNAME" ]; then
            echo "Error: hostname required"
            echo "Usage: $0 add [hostname] [serial] [inventory] [active]"
            exit 1
        fi

        echo -e "${BLUE}Adding device: ${HOSTNAME}${NC}"
        db_connect -c "INSERT INTO devices (hostname, serial_number, inventory_number, active) VALUES ('${HOSTNAME}', '${SERIAL}', '${INVENTORY}', ${ACTIVE}) RETURNING id, hostname;"
        ;;

    list)
        echo -e "${BLUE}All devices:${NC}"
        db_connect -c "SELECT id, hostname, serial_number, inventory_number, active, created_at FROM devices ORDER BY hostname;" -x
        ;;

    list-active)
        echo -e "${BLUE}Active devices:${NC}"
        db_connect -c "SELECT id, hostname, serial_number, inventory_number, created_at FROM devices WHERE active = TRUE ORDER BY hostname;" -x
        ;;

    get)
        HOSTNAME="$2"
        if [ -z "$HOSTNAME" ]; then
            echo "Error: hostname required"
            exit 1
        fi

        echo -e "${BLUE}Device details: ${HOSTNAME}${NC}"
        db_connect -c "SELECT * FROM devices WHERE hostname = '${HOSTNAME}';" -x
        ;;

    update)
        HOSTNAME="$2"
        FIELD="$3"
        VALUE="$4"

        if [ -z "$HOSTNAME" ] || [ -z "$FIELD" ] || [ -z "$VALUE" ]; then
            echo "Error: hostname, field, and value required"
            echo "Usage: $0 update [hostname] [field] [value]"
            echo "Fields: serial_number, inventory_number, active"
            exit 1
        fi

        echo -e "${BLUE}Updating ${HOSTNAME}: ${FIELD} = ${VALUE}${NC}"
        db_connect -c "UPDATE devices SET ${FIELD} = '${VALUE}', updated_at = CURRENT_TIMESTAMP WHERE hostname = '${HOSTNAME}' RETURNING hostname, ${FIELD};"
        ;;

    deactivate)
        HOSTNAME="$2"
        if [ -z "$HOSTNAME" ]; then
            echo "Error: hostname required"
            exit 1
        fi

        echo -e "${BLUE}Marking inactive: ${HOSTNAME}${NC}"
        db_connect -c "UPDATE devices SET active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE hostname = '${HOSTNAME}' RETURNING hostname, active;"
        ;;

    delete)
        HOSTNAME="$2"
        if [ -z "$HOSTNAME" ]; then
            echo "Error: hostname required"
            exit 1
        fi

        echo -e "${BLUE}Deleting device: ${HOSTNAME}${NC}"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            db_connect -c "DELETE FROM devices WHERE hostname = '${HOSTNAME}' RETURNING hostname;"
            echo -e "${GREEN}Deleted${NC}"
        else
            echo "Cancelled"
        fi
        ;;

    search)
        TERM="$2"
        if [ -z "$TERM" ]; then
            echo "Error: search term required"
            exit 1
        fi

        echo -e "${BLUE}Searching for: ${TERM}${NC}"
        db_connect -c "SELECT * FROM devices WHERE hostname ILIKE '%${TERM}%' OR serial_number ILIKE '%${TERM}%' OR inventory_number ILIKE '%${TERM}%' ORDER BY hostname;" -x
        ;;

    count)
        echo -e "${BLUE}Device statistics:${NC}"
        db_connect -c "SELECT COUNT(*) as total_devices, COUNT(*) FILTER (WHERE active = TRUE) as active_devices, COUNT(*) FILTER (WHERE active = FALSE) as inactive_devices FROM devices;"
        ;;

    help|--help|-h)
        show_help
        ;;

    *)
        echo "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
