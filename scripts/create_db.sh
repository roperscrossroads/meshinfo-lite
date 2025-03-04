#!/bin/bash

# Configuration file
CONFIG_FILE="config.ini"

# Check if the config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Configuration file '$CONFIG_FILE' not found!"
    exit 1
fi

# Function to extract values from the INI file
extract_value() {
    local section=$1
    local key=$2
    awk -F= -v section="$section" -v key="$key" '
        /^\[/{ in_section = ($0 == "[" section "]") } 
        in_section && $1 ~ "^[ \t]*" key "[ \t]*$" { gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit }
    ' "$CONFIG_FILE"
}

# Extract database credentials
DB_USER=$(extract_value "database" "username")
DB_PASS=$(extract_value "database" "password")
DB_NAME=$(extract_value "database" "database")

# Check if credentials were retrieved
if [[ -z "$DB_USER" || -z "$DB_PASS" ]]; then
    echo "Error: Could not extract database username or password."
    exit 1
fi

SQL=$(cat <<-END
CREATE DATABASE IF NOT EXISTS $DB_NAME;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';
GRANT ALL ON $DB_NAME.* TO '$DB_USER'@'localhost';
ALTER DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
COMMIT;
END
)

echo $SQL | mysql -u root
