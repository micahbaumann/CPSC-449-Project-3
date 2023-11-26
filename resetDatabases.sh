#!/bin/bash

# This script has to be used after run.sh
echo "Updating DynamoDB database"
# Run the Catalog.py script in the enroll/var directory
python enroll/var/catalog.py
echo "DynamoDB database updated :)"

echo "Updating Sqlite3 database"
sqlite3 ./users/var/primary/fuse/users.db < ./users/var/users.sql
echo "Sqlite3 database updated :)"