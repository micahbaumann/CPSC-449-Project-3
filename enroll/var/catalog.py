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

# Define the key schema and attribute definitions for the "Users" table
users_key_schema = [
    {"AttributeName": "UserId", "KeyType": "HASH"}
]

users_attribute_definitions = [
    {"AttributeName": "UserId", "AttributeType": "N"},
    {"AttributeName": "Username", "AttributeType": "S"},
    {"AttributeName": "Email", "AttributeType": "S"}
]

# Create the "Users" table
my_catalog.create_table("Users", users_key_schema, users_attribute_definitions)

# TODO: Create real tables 
# Define the key schema and attribute definitions for the "Enrollments" table
enrollments_key_schema = [
    {"AttributeName": "StudentID", "KeyType": "HASH"},
    {"AttributeName": "ClassID", "KeyType": "RANGE"}
]

enrollments_attribute_definitions = [
    {"AttributeName": "StudentID", "AttributeType": "N"},
    {"AttributeName": "ClassID", "AttributeType": "N"},
    {"AttributeName": "SectionNumber", "AttributeType": "N"}
]

# Create the "Enrollments" table
my_catalog.create_table("Enrollments", enrollments_key_schema, enrollments_attribute_definitions)