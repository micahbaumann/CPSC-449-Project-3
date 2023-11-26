# CPSC 449 Project 3

* [Project Document](https://docs.google.com/document/d/1rGKdbNxOj6FtUM_BQyWFM-yvaj4NXe5Kh3e6nWIH060/edit?usp=sharing)

## Project Members

- Edwin Peraza
- Micah Baumann
- Vivian Cao
- Liam Hernandez
- Gaurav Warad


## GitHub Repository

You can find the project's source code and documentation on our GitHub repository:

[CPSC-449 Project 3 Repository](https://github.com/micahbaumann/CPSC-449-Project-3)

## Getting started

### Prerequisites

- Tuffix (Ubuntu Linux)
- Python (version 3.10.12)
- Foreman
- KrakenD

### Setup

Initialize virtual environment and install requirements. Run command:

```
make
```

### Running API

Use the following scripts to start the project, create and populate the databases:

'''
sh run.sh
sh resetDatabases.sh
'''

### URLs and Ports

Foreman will host the processes  in the following URLs and ports:

- `users-primary`: [http://localhost:5000](http://localhost:5000)
- `enroll.1`: [http://localhost:5300](http://localhost:5000)
- `enroll.2`: [http://localhost:5301](http://localhost:5001)
- `enroll.3`: [http://localhost:5302](http://localhost:5002)
- `krakend`: [http://localhost:5400](http://localhost:5400)
- `dynamodb_local`: [http://localhost:5500](http://localhost:5500)

### Testing endpoints

Example credentials:

'''
{
    "username": "micah",
    "password": "12345"
}
'''

This credentials include the roles instructor, registrar, and student making it
simple to test all endpoints with just one bearer.

Use login endpoint to retrieve bearer and pass this bearer in body for all endpoints.