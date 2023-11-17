#!/bin/bash

echo "Populating the database..."
echo " "
# Run the Python script to populate the database
python ./enroll/var/catalog.py
echo " "
echo "Starting the services..."
echo " "
# the formation flag is used to specify the number of instances of each service
# three instances of enrollment service
# one instance of the users service plus two replicas
# one instance of the krakend service
# one instance of the dynamodb service
foreman start --formation "enroll_1=3, users_primary=1, users_secondary_1=1, users_secondary_2=1, krakend=1, dynamodb_local=1"
