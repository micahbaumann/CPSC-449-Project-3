# CPSC 449 Project 3
* [Project Document](https://docs.google.com/document/d/1rGKdbNxOj6FtUM_BQyWFM-yvaj4NXe5Kh3e6nWIH060/edit?usp=sharing)

## Updating the Databases
1. Write the SQL. For the enroll service, write it in `enroll/var/catalog.sql`. For the enroll service, write it in `users/var/users.sql`.
2. Run `updateDB.sh` for that service:
   ```bash
   ./(SERVICE DIRECTORY)/var/updateDB.sh
   ```
3. When the SQLite CLI opens, enter `.quit`.
