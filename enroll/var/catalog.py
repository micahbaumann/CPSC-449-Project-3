import boto3
from botocore.exceptions import ClientError

class Catalog:
    """Creates tables for the catalog database"""
    def __init__(self, dyn_resource):
        """
        :param dyn_resource: A Boto3 DynamoDB resource.
        """
        self.dyn_resource = dyn_resource
        # The table variable is set during the scenario in the call to
        # 'exists' if the table exists. Otherwise, it is set by 'create_table'.
        self.table = None

    def create_table(self, table_name, key_schema, attribute_definitions, global_secondary_indexes):
        """
        Creates an Amazon DynamoDB table for the catalog database.

        :param table_name: The name of the table to create.
        :return: The newly created table.
        """
        try:
            self.table = self.dyn_resource.create_table(
                TableName = table_name,
                KeySchema = key_schema,
                AttributeDefinitions= attribute_definitions,
                ProvisionedThroughput={
                    "ReadCapacityUnits": 10,
                    "WriteCapacityUnits": 10,
                },
                GlobalSecondaryIndexes=global_secondary_indexes
            )
            self.table.wait_until_exists()
            print(f"Table {table_name} created successfully.")
        except ClientError as err:
            # TODO: setup logger
            # logger.error(
            #     "Couldn't create table %s. Here's why: %s: %s",
            #     table_name,
            #     err.response["Error"]["Code"],
            #     err.response["Error"]["Message"],
            # )
            print(
                "Couldn't create table {}. Here's why: {}: {}".format(
                    table_name,
                    err.response["Error"]["Code"],
                    err.response["Error"]["Message"],
                )
            )
            raise
        else:
            return self.table
        
    def put_items(self, table_name, items):
        """
        Adds items to the specified DynamoDB table.

        :param table_name: The name of the table to add items to.
        :param items: A list of dictionaries, where each dictionary represents an item to add.
        """
        table = self.dyn_resource.Table(table_name)
        for item in items:
            try:
                table.put_item(Item=item)
            except ClientError as e:
                print(f"Error adding item to {table_name}: {e.response['Error']['Message']}")
                raise e
        
    def delete_table_if_exists(self, table_name):
        """
        Deletes the specified DynamoDB table if it exists.

        :param table_name: The name of the table to delete.
        """
        try:
            table = self.dyn_resource.Table(table_name)
            if table.table_State == 'ACTIVE':
                table.delete()
                table.wait_until_not_exists()
                print(f"Table {table_name} deleted successfully.")
            else:
                print(f"Table {table_name} does not exist.")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"Table {table_name} does not exist.")
            else:
                raise
        

# start an instance of the Catalog class
dynamo_db = boto3.resource("dynamodb", endpoint_url = "http://localhost:5500")  
my_catalog = Catalog(dynamo_db)  

# ********************************** Delete tables if they exist **********************************

my_catalog.delete_table_if_exists("Users")
my_catalog.delete_table_if_exists("Classes")
my_catalog.delete_table_if_exists("Enrollments")

# ********************************** Create "Users table" ***************************************

# Define the key schema and attribute definitions for the "Users" table
users_key_schema = [
    {"AttributeName": "UserId", "KeyType": "HASH"}

]

users_attribute_definitions = [
    {"AttributeName": "UserId", "AttributeType": "N"},
    # {"AttributeName": "Username", "AttributeType": "S"},
    {"AttributeName": "Email", "AttributeType": "S"},
    # {"AttributeName": "FirstName", "AttributeType": "S"},
    # {"AttributeName": "LastName", "AttributeType": "S"},
    # {"AttributeName": "Role", "AttributeType": "S"}
]

classes_global_secondary_indexes = [
        {
            "IndexName": "Email-index",
            "KeySchema": [
                {"AttributeName": "Email", "KeyType": "HASH"},
                {"AttributeName": "UserId", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
            "ProvisionedThroughput": {
                "ReadCapacityUnits": 10,
                "WriteCapacityUnits": 10,
            },
        },
    ]

# Create the "Users" table
my_catalog.create_table("Users", users_key_schema, users_attribute_definitions, classes_global_secondary_indexes)


# ********************************** Create "Classes table" *************************************

# Define the key schema and attribute definitions for the "Classes" table
classes_key_schema = [
    {"AttributeName": "ClassID", "KeyType": "HASH"},
    # {"AttributeName": "SectionNumber", "KeyType": "RANGE"}
]

classes_attribute_definitions = [
    {"AttributeName": "ClassID", "AttributeType": "N"},
    # {"AttributeName": "CourseCode", "AttributeType": "S"},
    # {"AttributeName": "SectionNumber", "AttributeType": "N"},
    # {"AttributeName": "ClassName", "AttributeType": "S"},
    # {"AttributeName": "Department", "AttributeType": "S"},
    # {"AttributeName": "InstructorID", "AttributeType": "N"},
    # {"AttributeName": "MaxCapacity", "AttributeType": "N"},
    # either 'active' or 'inactive'
    {"AttributeName": "State", "AttributeType": "S"}
]

classes_global_secondary_indexes = [
        {
            "IndexName": "State-index",
            "KeySchema": [
                {"AttributeName": "State", "KeyType": "HASH"},
                {"AttributeName": "ClassID", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
            "ProvisionedThroughput": {
                "ReadCapacityUnits": 10,
                "WriteCapacityUnits": 10,
            },
        },
    ]

# Create the "Classes" table
my_catalog.create_table("Classes", classes_key_schema, classes_attribute_definitions, classes_global_secondary_indexes)

# ********************************** Create "Enrollments table" *********************************

# Define the key schema and attribute definitions for the "Enrollments" table
enrollments_key_schema = [
    {"AttributeName": "EnrollmentID", "KeyType": "HASH"},
    {"AttributeName": "ClassID", "KeyType": "RANGE"}
]

enrollments_attribute_definitions = [
    {"AttributeName": "EnrollmentID", "AttributeType": "N"},
    # {"AttributeName": "StudentID", "AttributeType": "N"},
    {"AttributeName": "ClassID", "AttributeType": "N"},
    # {"AttributeName": "SectionNumber", "AttributeType": "N"},
    {"AttributeName": "EnrollmentState", "AttributeType": "S"}
]

enrollments_global_secondary_indexes = [ 
    {
        "IndexName": "ClassID-EnrollmentState-index",
        "KeySchema": [
                {"AttributeName": "ClassID", "KeyType": "HASH"},
                {"AttributeName": "EnrollmentState", "KeyType": "RANGE"},
        ],
        "Projection": {"ProjectionType": "ALL"},
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 10,
            "WriteCapacityUnits": 10,
        },
    },
    
]


# Create the "Enrollments" table
my_catalog.create_table("Enrollments", enrollments_key_schema, enrollments_attribute_definitions, enrollments_global_secondary_indexes)



# ********************************** Populate tables with data **********************************

# Populate the "Users" table
users_items = [
    # User ID 1-4 are students
    {"UserId": 1, "Username": "fara", "Email": "fsmith@csu.fullerton.edu"},
    {"UserId": 2, "Username": "steve", "Email": "sjobs@csu.fullerton.edu"},
    {"UserId": 3, "Username": "andy", "Email": "ajones@csu.fullerton.edu"},
    {"UserId": 4, "Username": "tim", "Email": "traft@csu.fullerton.edu"},
    # User ID 5-7 are instructors
    {"UserId": 5, "Username": "elizabeth", "Email": "ebarnes@csu.fullerton.edu"},
    {"UserId": 6, "Username": "george", "Email": "gderns@csu.fullerton.edu"},
    {"UserId": 7, "Username": "pheobe", "Email": "pessek@fsmithcsu.fullerton.edu"},
    # User ID 8-10 are registrars
    {"UserId": 8, "Username": "earl", "Email": "epoppins@csu.fullerton.edu"},
    {"UserId": 9, "Username": "sarah", "Email": "fsmith@csu.fullerton.edu"},
    {"UserId": 10, "Username": "anna", "Email": "akant@csu.fullerton.edu"},
    # All roles
    {"UserId": 11, "Username": "micah", "Email": "mbaumann@csu.fullerton.edu"},
    {"UserId": 12, "Username": "edwin", "Email": "edwinperaza@csu.fullerton.edu"},
]

my_catalog.put_items("Users", users_items)


# Populate the "Classes" table
classes_items = [
    {"ClassID": 1, "SectionNumber": 1, "CourseCode": "CS-101", "ClassName": "Introduction to Computer Science", "Department": "Computer Science", "InstructorID": 11, "MaxCapacity": 50, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "inactive", "WaitlistMaximum": 30},
    {"ClassID": 2, "SectionNumber": 2, "CourseCode": "CS-101", "ClassName": "Introduction to Computer Science", "Department": "Computer Science", "InstructorID": 11, "MaxCapacity": 50, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "active", "WaitlistMaximum": 30},
    
    {"ClassID": 3, "SectionNumber": 1, "CourseCode": "ENG-101", "ClassName": "English 101", "Department": "English", "InstructorID": 11, "MaxCapacity": 30, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "inactive", "WaitlistMaximum": 30},
    {"ClassID": 4, "SectionNumber": 2, "CourseCode": "ENG-101", "ClassName": "English 101", "Department": "English", "InstructorID": 11, "MaxCapacity": 30, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "active", "WaitlistMaximum": 30},
    
    {"ClassID": 5, "SectionNumber": 1, "CourseCode": "MATH-101", "ClassName": "Mathematics 101", "Department": "Mathematics", "InstructorID": 11, "MaxCapacity": 40, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "inactive", "WaitlistMaximum": 30},
    {"ClassID": 6, "SectionNumber": 2, "CourseCode": "MATH-101", "ClassName": "Mathematics 101", "Department": "Mathematics", "InstructorID": 11, "MaxCapacity": 40, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "active", "WaitlistMaximum": 30},
    
    {"ClassID": 7, "SectionNumber": 1, "CourseCode": "PHYS-101", "ClassName": "Physics 101", "Department": "Physics", "InstructorID": 5, "MaxCapacity": 35, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "inactive", "WaitlistMaximum": 30},
    {"ClassID": 8, "SectionNumber": 2, "CourseCode": "PHYS-101", "ClassName": "Physics 101", "Department": "Physics", "InstructorID": 5, "MaxCapacity": 35, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "active", "WaitlistMaximum": 30},
    
    {"ClassID": 9, "SectionNumber": 1, "CourseCode": "CHEM-101", "ClassName": "Chemistry 101", "Department": "Chemistry", "InstructorID": 6, "MaxCapacity": 45, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "inactive", "WaitlistMaximum": 30},
    {"ClassID": 10, "SectionNumber": 2, "CourseCode": "CHEM-101", "ClassName": "Chemistry 101", "Department": "Chemistry", "InstructorID": 6, "MaxCapacity": 45, "CurrentEnrollment": 0, "CurrentWaitlist": 0, "State": "active", "WaitlistMaximum": 30},
]

my_catalog.put_items("Classes", classes_items)


# Populate the "Enrollments" table
enrollments_items = [
    {"EnrollmentID": 1, "StudentID": 2, "ClassID": 1, "EnrollmentState": "DROPPED"},
    {"EnrollmentID": 2, "StudentID": 2, "ClassID": 2, "EnrollmentState": "WAITLISTED"},
    {"EnrollmentID": 3, "StudentID": 2, "ClassID": 3, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 4, "StudentID": 2, "ClassID": 4, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 5, "StudentID": 2, "ClassID": 5, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 6, "StudentID": 3, "ClassID": 6, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 7, "StudentID": 3, "ClassID": 1, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 8, "StudentID": 3, "ClassID": 2, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 9, "StudentID": 3, "ClassID": 3, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 10, "StudentID": 3, "ClassID": 4, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 11, "StudentID": 4, "ClassID": 5, "EnrollmentState": "ENROLLED"},
    # ENROLLMENTS FOR TESTING CLASS ID 1 FOR INSTRUCTOR ID 11
    {"EnrollmentID": 12, "StudentID": 1, "ClassID": 1, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 13, "StudentID": 3, "ClassID": 1, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 14, "StudentID": 4, "ClassID": 1, "EnrollmentState": "ENROLLED"},
    # FOR TESTING CLADD ID 2 FOR INSTRUCTOR ID 
    {"EnrollmentID": 15, "StudentID": 1, "ClassID": 2, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 16, "StudentID": 4, "ClassID": 2, "EnrollmentState": "ENROLLED"},
    {"EnrollmentID": 17, "StudentID": 12, "ClassID": 2, "EnrollmentState": "ENROLLED"}


]

my_catalog.put_items("Enrollments", enrollments_items)

