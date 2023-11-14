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

    def create_table(self, table_name, key_schema, attribute_definitions):
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
            )
            self.table.wait_until_exists()
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
        

# start an instance of the Catalog class
dynamo_db = boto3.resource("dynamodb", endpoint_url = "http://localhost:8000")  
my_catalog = Catalog(dynamo_db)  

# ********************************** Create "Users table" ***************************************

# Define the key schema and attribute definitions for the "Users" table
users_key_schema = [
    {"AttributeName": "UserId", "KeyType": "HASH"}
]

users_attribute_definitions = [
    {"AttributeName": "UserId", "AttributeType": "N"},
    {"AttributeName": "Username", "AttributeType": "S"},
    {"AttributeName": "Email", "AttributeType": "S"},
    {"AttributeName": "FirstName", "AttributeType": "S"},
    {"AttributeName": "LastName", "AttributeType": "S"},
    {"AttributeName": "Role", "AttributeType": "S"}
]

# Create the "Users" table
my_catalog.create_table("Users", users_key_schema, users_attribute_definitions)


# ********************************** Create "Classes table" *************************************

# Define the key schema and attribute definitions for the "Classes" table
classes_key_schema = [
    {"AttributeName": "ClassID", "KeyType": "HASH"},
    {"AttributeName": "SectionNumber", "KeyType": "RANGE"}
]

classes_attribute_definitions = [
    {"AttributeName": "ClassID", "AttributeType": "N"},
    {"AttributeName": "CourseCode", "AttributeType": "S"},
    {"AttributeName": "SectionNumber", "AttributeType": "N"},
    {"AttributeName": "ClassName", "AttributeType": "S"},
    {"AttributeName": "Department", "AttributeType": "S"},
    {"AttributeName": "InstructorID", "AttributeType": "N"},
    {"AttributeName": "Capacity", "AttributeType": "N"},
    # either 'active' or 'inactive'
    {"AttributeName": "State", "AttributeType": "S"}
]

# Create the "Classes" table
my_catalog.create_table("Classes", classes_key_schema, classes_attribute_definitions)

# ********************************** Create "Enrollments table" *********************************

# Define the key schema and attribute definitions for the "Enrollments" table
enrollments_key_schema = [
    {"AttributeName": "EnrollmentID", "KeyType": "HASH"}
]

enrollments_attribute_definitions = [
    {"AttributeName": "EnrollmentID", "AttributeType": "N"},
    {"AttributeName": "StudentID", "AttributeType": "N"},
    {"AttributeName": "ClassID", "AttributeType": "N"},
    {"AttributeName": "SectionNumber", "AttributeType": "N"},
    {"AttributeName": "EnrollmentStatus", "AttributeType": "S"}
]

# Create the "Enrollments" table
my_catalog.create_table("Enrollments", enrollments_key_schema, enrollments_attribute_definitions)



# ********************************** Populate tables with data **********************************

# Populate the "Users" table
users_table = dynamo_db.Table("Users")

users_items = [
    {"UserId": 1, "Username": "edwinperaza", "Email": "edwinperaza@example.com", "FirstName": "Edwin", "LastName": "Peraza", "Role": "Student"},
    {"UserId": 2, "Username": "janesmith", "Email": "janesmith@example.com", "FirstName": "Jane", "LastName": "Smith", "Role": "Instructor"},
]

for item in users_items:
    users_table.put_item(Item=item)

# Populate the "Classes" table
classes_table = dynamo_db.Table("Classes")

classes_items = [
    {"ClassID": 1, "SectionNumber": 1, "CourseCode": "CS-101", "ClassName": "Introduction to Computer Science", "Department": "Computer Science", "InstructorID": 2, "Capacity": 50, "State": "active"},
    {"ClassID": 2, "SectionNumber": 1, "CourseCode": "ENG-101", "ClassName": "English 101", "Department": "English", "InstructorID": 3, "Capacity": 30, "State": "active"},
    # Add more class items as needed
]

for item in classes_items:
    classes_table.put_item(Item=item)

# Populate the "Enrollments" table
enrollments_table = dynamo_db.Table("Enrollments")

enrollments_items = [
    {"EnrollmentID": 1, "StudentID": 1, "ClassID": 1, "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    {"EnrollmentID": 2, "StudentID": 1, "ClassID": 2, "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    # Add more enrollment items as needed
]

for item in enrollments_items:
    enrollments_table.put_item(Item=item)
