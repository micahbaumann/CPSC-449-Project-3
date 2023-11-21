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
            if table.table_status == 'ACTIVE':
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
    # {"AttributeName": "Email", "AttributeType": "S"},
    # {"AttributeName": "FirstName", "AttributeType": "S"},
    # {"AttributeName": "LastName", "AttributeType": "S"},
    # {"AttributeName": "Role", "AttributeType": "S"}
]

# Create the "Users" table
my_catalog.create_table("Users", users_key_schema, users_attribute_definitions)


# ********************************** Create "Classes table" *************************************

# Define the key schema and attribute definitions for the "Classes" table
classes_key_schema = [
    {"AttributeName": "CourseCode", "KeyType": "HASH"},
    {"AttributeName": "SectionNumber", "KeyType": "RANGE"}
]

classes_attribute_definitions = [
    # {"AttributeName": "ClassID", "AttributeType": "N"},
    {"AttributeName": "CourseCode", "AttributeType": "S"},
    {"AttributeName": "SectionNumber", "AttributeType": "N"},
    # {"AttributeName": "ClassName", "AttributeType": "S"},
    # {"AttributeName": "Department", "AttributeType": "S"},
    # {"AttributeName": "InstructorID", "AttributeType": "N"},
    # {"AttributeName": "Capacity", "AttributeType": "N"},
    # either 'active' or 'inactive'
    # {"AttributeName": "State", "AttributeType": "S"}
]

# Create the "Classes" table
my_catalog.create_table("Classes", classes_key_schema, classes_attribute_definitions)

# ********************************** Create "Enrollments table" *********************************

# Define the key schema and attribute definitions for the "Enrollments" table
enrollments_key_schema = [
    {"AttributeName": "EnrollmentID", "KeyType": "HASH"},
]

enrollments_attribute_definitions = [
    {"AttributeName": "EnrollmentID", "AttributeType": "N"},
    # {"AttributeName": "StudentID", "AttributeType": "N"},
    # {"AttributeName": "ClassID", "AttributeType": "N"},
    # {"AttributeName": "SectionNumber", "AttributeType": "N"},
    # {"AttributeName": "EnrollmentStatus", "AttributeType": "S"}
]

# Create the "Enrollments" table
my_catalog.create_table("Enrollments", enrollments_key_schema, enrollments_attribute_definitions)



# ********************************** Populate tables with data **********************************

# Populate the "Users" table
users_items = [
    # registrar has UserId 1
    {"UserId": 1, "Username": "registrar", "Email": "registrar@example.com", "FirstName": "Registrar", "LastName": "Registrar", "Role": "Registrar"},
    # 5 student with UserId 2-6
    {"UserId": 2, "Username": "edwinperaza", "Email": "edwinperaza@example.com", "FirstName": "Edwin", "LastName": "Peraza", "Role": "Student"},
    {"UserId": 2, "Username": "johndoe", "Email": "johndoe@example.com", "FirstName": "John", "LastName": "Doe", "Role": "Student"},
    {"UserId": 3, "Username": "alicesmith", "Email": "alicesmith@example.com", "FirstName": "Alice", "LastName": "Smith", "Role": "Student"},
    {"UserId": 4, "Username": "bobjohnson", "Email": "bobjohnson@example.com", "FirstName": "Bob", "LastName": "Johnson", "Role": "Student"},
    {"UserId": 5, "Username": "evawilliams", "Email": "evawilliams@example.com", "FirstName": "Eva", "LastName": "Williams", "Role": "Student"},
    {"UserId": 6, "Username": "chrisbrown", "Email": "chrisbrown@example.com", "FirstName": "Chris", "LastName": "Brown", "Role": "Student"},
    # 5 instructor with UserId 7-11
    {"UserId": 7, "Username": "professoranderson", "Email": "professoranderson@example.com", "FirstName": "Professor", "LastName": "Anderson", "Role": "Instructor"},
    {"UserId": 8, "Username": "drclark", "Email": "drclark@example.com", "FirstName": "Dr.", "LastName": "Clark", "Role": "Instructor"},
    {"UserId": 9, "Username": "msjohnson", "Email": "msjohnson@example.com", "FirstName": "Ms.", "LastName": "Johnson", "Role": "Instructor"},
    {"UserId": 10, "Username": "janesmith", "Email": "janesmith@example.com", "FirstName": "Jane", "LastName": "Smith", "Role": "Instructor"},
    {"UserId": 11, "Username": "professorbrown", "Email": "professorbrown@example.com", "FirstName": "Professor", "LastName": "Brown", "Role": "Instructor"},
]

my_catalog.put_items("Users", users_items)


# Populate the "Classes" table
classes_items = [
    {"ClassID": 1, "SectionNumber": 1, "CourseCode": "CS-101", "ClassName": "Introduction to Computer Science", "Department": "Computer Science", "InstructorID": 2, "Capacity": 50, "State": "inactive"},
    {"ClassID": 1, "SectionNumber": 2, "CourseCode": "CS-101", "ClassName": "Introduction to Computer Science", "Department": "Computer Science", "InstructorID": 2, "Capacity": 50, "State": "active"},
    
    {"ClassID": 2, "SectionNumber": 1, "CourseCode": "ENG-101", "ClassName": "English 101", "Department": "English", "InstructorID": 3, "Capacity": 30, "State": "inactive"},
    {"ClassID": 2, "SectionNumber": 2, "CourseCode": "ENG-101", "ClassName": "English 101", "Department": "English", "InstructorID": 3, "Capacity": 30, "State": "active"},
    
    {"ClassID": 3, "SectionNumber": 1, "CourseCode": "MATH-101", "ClassName": "Mathematics 101", "Department": "Mathematics", "InstructorID": 4, "Capacity": 40, "State": "inactive"},
    {"ClassID": 3, "SectionNumber": 2, "CourseCode": "MATH-101", "ClassName": "Mathematics 101", "Department": "Mathematics", "InstructorID": 4, "Capacity": 40, "State": "active"},
    
    {"ClassID": 4, "SectionNumber": 1, "CourseCode": "PHYS-101", "ClassName": "Physics 101", "Department": "Physics", "InstructorID": 5, "Capacity": 35, "State": "inactive"},
    {"ClassID": 4, "SectionNumber": 2, "CourseCode": "PHYS-101", "ClassName": "Physics 101", "Department": "Physics", "InstructorID": 5, "Capacity": 35, "State": "active"},
    
    {"ClassID": 5, "SectionNumber": 1, "CourseCode": "CHEM-101", "ClassName": "Chemistry 101", "Department": "Chemistry", "InstructorID": 6, "Capacity": 45, "State": "inactive"},
    {"ClassID": 5, "SectionNumber": 2, "CourseCode": "CHEM-101", "ClassName": "Chemistry 101", "Department": "Chemistry", "InstructorID": 6, "Capacity": 45, "State": "active"},
]

my_catalog.put_items("Classes", classes_items)


# Populate the "Enrollments" table
enrollments_items = [
    {"EnrollmentID": 1, "StudentID": 2, "CourseCode": "CPSC-101", "SectionNumber": 1, "EnrollmentStatus": "DROPPED"},
    {"EnrollmentID": 2, "StudentID": 2, "CourseCode": "CHEM-101", "SectionNumber": 1, "EnrollmentStatus": "WAITLISTED"},
    {"EnrollmentID": 3, "StudentID": 2, "CourseCode": "PHYS-101", "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    {"EnrollmentID": 4, "StudentID": 2, "CourseCode": "MATH-101", "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    {"EnrollmentID": 5, "StudentID": 2, "CourseCode": "ENG-101", "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    {"EnrollmentID": 6, "StudentID": 3, "CourseCode": "CPSC-101", "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    {"EnrollmentID": 7, "StudentID": 3, "CourseCode": "CHEM-101", "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    {"EnrollmentID": 8, "StudentID": 3, "CourseCode": "PHYS-101", "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    {"EnrollmentID": 9, "StudentID": 3, "CourseCode": "MATH-101", "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    {"EnrollmentID": 10, "StudentID": 3, "CourseCode": "ENG-101", "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    {"EnrollmentID": 11, "StudentID": 4, "CourseCode": "CPSC-101", "SectionNumber": 1, "EnrollmentStatus": "ENROLLED"},
    # Add more enrollment items as needed
]

my_catalog.put_items("Enrollments", enrollments_items)

