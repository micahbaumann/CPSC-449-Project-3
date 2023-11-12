# Use this file to remove the current catalog.db file and populate it with the newest version found in catalog.sql

echo "Updating database file"
rm ./enroll/var/catalog.db
sqlite3 ./enroll/var/catalog.db < ./enroll/var/catalog.sql
echo "Database file updated :)"
