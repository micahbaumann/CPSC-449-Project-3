import sqlite3
import contextlib
import requests
import redis
import boto3

from fastapi import FastAPI, Depends, HTTPException, status, Request
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

KRAKEND_PORT = "5400"

# start dynamo db
dynamo_db = boto3.resource('dynamodb', endpoint_url="http://localhost:5500")
# retrieve tables
users_table = dynamo_db.Table('Users')
classes_table = dynamo_db.Table('Classes')
enrollments_table = dynamo_db.Table('Enrollments')

class Settings(BaseSettings, env_file="enroll/.env", extra="ignore"):
    database: str
    logging_config: str

def get_db():
    with contextlib.closing(sqlite3.connect(settings.database)) as db:
        db.row_factory = sqlite3.Row
        yield db

def get_redis():
    yield redis.Redis()

settings = Settings()
app = FastAPI()


def check_user(id_val: int, username: str, email: str):
    """check if user exists in Users table, if not, add user"""
    response = users_table.query(KeyConditionExpression=Key('UserId').eq(id_val))
    items = response.get('Items', [])

    if items:
        user_item = items[0]
        return user_item
    else:
        user_item = {
            "UserId": id_val,
            "Username": username,
            "Email": email
        }
        users_table.put_item(Item=user_item)
        return user_item


def check_class_exists(class_id: int):
    response = classes_table.query(
        KeyConditionExpression=Key('ClassID').eq(class_id)
    )

    class_items = response.get('Items', [])

    if not class_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ClassID {class_id} not found"
        )
    return class_items[0]



def get_enrollment_status(student_id: int, class_id: int):
    response = enrollments_table.query(
        IndexName='StudentID-ClassID-index',
        KeyConditionExpression=Key('StudentID').eq(student_id) & Key('ClassID').eq(class_id),
        ProjectionExpression='EnrollmentState',
        Limit=1
    )

    items = response.get('Items', [])

    if items:
        enrollment_item = items[0]
        return enrollment_item.get('EnrollmentState')
    else:
        return None



def update_enrollment_status(enrollment_id: int, new_status: str):
    try:
        response = enrollments_table.update_item(
            Key={'EnrollmentID': enrollment_id},
            UpdateExpression='SET EnrollmentState = :status',
            ExpressionAttributeValues={':status': new_status},
            ReturnValues='UPDATED_NEW'
        )
        updated_item = response.get('Attributes')
        if updated_item:
            return updated_item.get('EnrollmentState')
        else:
            return None

    except ClientError as e:
        print(f"Error updating enrollment status for enrollmentID {enrollment_id}: {e.response['Error']['Message']}")
        return None

    

def update_current_enrollment(class_id: int, increment: bool = True):
    # Determine whether to increment or decrement
    update_expression = 'ADD CurrentEnrollment :delta' if increment else 'SET CurrentEnrollment = CurrentEnrollment - :delta'

    # Set the value of :delta based on whether to increment or decrement
    expression_attribute_values = {':delta': 1} if increment else {':delta': 1}

    # Perform the update
    response = classes_table.update_item(
        Key={'ClassID': class_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues='UPDATED_NEW'
    )

    updated_item = response.get('Attributes')

    if updated_item:
        return updated_item.get('CurrentEnrollment')
    else:
        return None


def is_instructor_for_class(instructor_id: int, class_id: int):
        response = classes_table.get_item(Key={"ClassID": class_id})
        # Check if the class exists and has the specified instructor
        if "Item" in response:
            class_info = response["Item"]
            return class_info.get("InstructorID") == instructor_id
        else:
            return False    
        

def get_students_for_class(class_id: int, enrollment_status: str):
    enrolled_students = []
    response = enrollments_table.query(
        IndexName='ClassID-EnrollmentState-index',
        KeyConditionExpression=Key('ClassID').eq(class_id) & Key('EnrollmentState').eq(enrollment_status),
        ProjectionExpression='StudentID, EnrollmentState'
    )
    for item in response.get("Items", []):
        student_info = {
            "StudentID": item.get("StudentID"),
            "EnrollmentState": item.get("EnrollmentState"),
        }
        enrolled_students.append(student_info)

    return enrolled_students    

        

def drop_students_from_class(class_id: int):
    dropped_students = []
    # Query for ENROLLED students
    enrolled_response = enrollments_table.query(
        IndexName='ClassID-EnrollmentState-index',
        KeyConditionExpression=Key('ClassID').eq(class_id) & Key('EnrollmentState').eq('ENROLLED'),
        ProjectionExpression='StudentID, EnrollmentID'
    )
    # Query for WAITLISTED students
    waitlisted_response = enrollments_table.query(
        IndexName='ClassID-EnrollmentState-index',
        KeyConditionExpression=Key('ClassID').eq(class_id) & Key('EnrollmentState').eq('WAITLISTED'),
        ProjectionExpression='StudentID , EnrollmentID'
    )
    try:
        print("Fourth checkpoint")
        # Process ENROLLED students
        for item in enrolled_response.get("Items", []):
            student_id = item.get("StudentID")
            enrollment_id = item.get("EnrollmentID")
            updated_status = update_enrollment_status(enrollment_id, 'DROPPED')
            if updated_status:
                dropped_students.append(student_id)
        print("Fifth checkpoint")
        # Process WAITLISTED students
        for item in waitlisted_response.get("Items", []):
            student_id = item.get("StudentID")
            enrollment_id = item.get("EnrollmentID")
            updated_status = update_enrollment_status(enrollment_id, 'DROPPED')
            if updated_status:
                dropped_students.append(student_id)
        if dropped_students != []:
            return dropped_students
        else:
            return None
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Failed to drop students from class {class_id}: {e.response['Error']['Message']}")
    
    
def retrieve_enrollment_record_id(student_id: int, class_id: int):
    response = enrollments_table.query(
        IndexName='StudentID-ClassID-index',
        KeyConditionExpression=Key('StudentID').eq(student_id) & Key('ClassID').eq(class_id),
        ProjectionExpression='EnrollmentID',
        Limit=1
    )
    # return response.get('Items')
    enrollment_item = response.get('Items')[0] if 'Items' in response and len(response.get('Items')) != 0 else None

    if enrollment_item:
        return enrollment_item.get('EnrollmentID')
    else:
        return None


def add_to_waitlist(class_id: int, student_id: int, redis):
    response_class = classes_table.query(
        KeyConditionExpression=Key('ClassID').eq(class_id)
    )
    new_response = retrieve_enrollment_record_id(student_id, class_id)
    if not new_response:
        # create a new enrollment record
        response = enrollments_table.scan(
                ProjectionExpression='EnrollmentID',
                Select='SPECIFIC_ATTRIBUTES',
            )
        items = response.get('Items', [])

        # Find the highest enrollmentID
        highest_enrollment_id = 0
        for item in items:
            enrollment_id = item.get('EnrollmentID', 0)
            
            if enrollment_id > highest_enrollment_id:
                highest_enrollment_id = enrollment_id

        # Calculate the new ClassID
        new_enrollment_id = highest_enrollment_id + 1

        enrollment_item = {
            "EnrollmentID": new_enrollment_id,
            "StudentID": student_id,
            "ClassID": class_id,
            "EnrollmentState": "WAITLISTED"
        }
        enrollments_table.put_item(Item=enrollment_item)
        
    else:
        updated_status = update_enrollment_status(new_response, 'WAITLISTED')
        if not updated_status:
            raise HTTPException(
                status_code=500,
                detail="Failed to update enrollment status"
            )

    if redis.llen(f"waitClassID_{class_id}") < response_class["Items"][0]["WaitlistMaximum"]:
        redis.rpush(f"waitClassID_{class_id}", student_id)
        return True
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Class and Waitlist with ClassID {class_id} are full"
        )
    
    
### Student related endpoints
# TODO: endpoint working, returns all information for a class
@app.get("/list")
def list_open_classes(r = Depends(get_redis)):
    """API to fetch list of available classes in catalog.

    Args:
        None

    Returns:
        A dictionary with a list of classes available for enrollment.
    """
    response = classes_table.query(
        IndexName='State-index',
        KeyConditionExpression=Key('State').eq('active'),
        ProjectionExpression='ClassID, CourseCode, SectionNumber, ClassName, Department, MaxCapacity, CurrentEnrollment, CurrentWaitlist, InstructorID, WaitlistMaximum'
    )
    items = response.get('Items', [])
    classList = {"Classes": []}
    for aClass in items:
        if r.llen(f"waitClassID_{aClass['ClassID']}") < aClass["WaitlistMaximum"]:
            classList["Classes"].append(aClass)

    return classList


# TODO: endpoint fully working with krakend
# TODO: test redis 
@app.post("/enroll/{studentid}/{classid}/{username}/{email}")
def enroll_student_in_class(studentid: int, classid: int, username: str, email: str, r = Depends(get_redis)):
    """API to enroll a student in a class.
    
    Args:
        studentid: The student's ID.
        classid: The class ID.

    Returns:
        A dictionary with a message indicating the student's enrollment status.
    """
    check_user(studentid, username, email)
    # TODO: use class_item for waitlist 
    class_item = check_class_exists(classid)
    if class_item.get('State') != 'active':
        raise HTTPException(
            status_code=409,
            detail=f"Class with ClassID {classid} is not active"
        )
    status = get_enrollment_status(studentid, classid)
    if status == 'ENROLLED':
        raise HTTPException(
            status_code=409,
            detail=f"Student with StudentID {studentid} is already enrolled in class with ClassID {classid}"
        )

    elif status == 'WAITLISTED':
        raise HTTPException(
            status_code=409,
            detail=f"Student with StudentID {studentid} is already on the waitlist for class with ClassID {classid}"
        )
    # TODO: either allow or not allow to enroll if dropped 
    elif status == 'DROPPED':
        raise HTTPException(
            status_code=409,
            detail=f"Student with StudentID {studentid} was dropped from class with ClassID {classid}"
        )
    elif status is None:
        if class_item.get('CurrentEnrollment') < class_item.get('MaxCapacity'):
            response = enrollments_table.scan(
                ProjectionExpression='EnrollmentID',
                Select='SPECIFIC_ATTRIBUTES',
            )
            items = response.get('Items', [])

            # Find the highest ClassID
            highest_enrollment_id = 0
            for item in items:
                enrollment_id = item.get('EnrollmentID', 0)
            
                if enrollment_id > highest_enrollment_id:
                    highest_enrollment_id = enrollment_id

            # Calculate the new ClassID
            new_enrollment_id = highest_enrollment_id + 1

            enrollment_item = {
                "EnrollmentID": new_enrollment_id,
                "StudentID": studentid,
                "ClassID": classid,
                "EnrollmentState": "ENROLLED"
            }
            enrollments_table.put_item(Item=enrollment_item)

            # Increment the CurrentEnrollment for the class
            updated_current_enrollment = update_current_enrollment(classid, increment=True)

            if updated_current_enrollment is not None:
                return {
                    "message": "Enrollment added successfully",
                    "enrollment_item": enrollment_item,
                    "updated_current_enrollment": updated_current_enrollment
                }
            else:
                # Handle error if the update fails
                raise HTTPException(
                    status_code=500,
                    detail="Failed to update current enrollment"
                )
        else:
            if add_to_waitlist(classid, studentid, r):
                return {
                    "message": "Student added to waitlist",
                }
            
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to update current enrollment"
        )

    # TODO: create function to increment waitlist 

    
    # class_section = classes["SectionNumber"]
    # count = db.execute("SELECT COUNT() FROM Enrollments WHERE ClassID = ?", (classid,)).fetchone()[0]
    # waitlist_count = db.execute("SELECT COUNT() FROM Waitlists WHERE ClassID = ?", (classid,)).fetchone()[0]
    # waitlist_count = r.llen(f"waitClassID_{classid}")
    # print(count)
    # if count < classes["MaximumEnrollment"]:
    #     db.execute("INSERT INTO Enrollments(StudentID, ClassID, SectionNumber) VALUES(?,?,?)",(studentid, classid, class_section))
    #     db.commit()
    #     return {"message": f"Enrolled student {studentid} in section {class_section} of class {classid}."}
    # elif waitlist_count < classes["WaitlistMaximum"]:
    #     waitlisted = r.lpos(f"waitClassID_{classid}", studentid)
    #     # waitlisted = db.execute("SELECT * FROM Waitlists WHERE StudentID = ? AND ClassID = ?", (studentid, classid)).fetchone()
    #     if waitlisted:
    #         raise HTTPException(
    #             status_code=status.HTTP_409_CONFLICT,
    #             detail="Student already waitlisted")

        # max_waitlist_position = db.execute("SELECT MAX(Position) FROM Waitlists WHERE ClassID = ? AND  SectionNumber = ?",(classid,sectionid)).fetchone()[0]
        # print("Position: " + str(max_waitlist_position))
        # if not max_waitlist_position: max_waitlist_position = 0
        # db.execute("INSERT INTO Waitlists(StudentID, ClassID, SectionNumber, Position) VALUES(?,?,?,?)",(studentid, classid, class_section, max_waitlist_position + 1))
        # db.commit()
    # r.rpush(f"waitClassID_{classid}", studentid)
        # return {"message": f"Enrolled in waitlist {class_section} of class {classid}."}
    # else:
        # return {"message": f"Unable to enroll in waitlist for the class, reached the maximum number of students"}
    

# TODO: ENDPOINT WORKING INCLUDING KRAKEND, NEED TO TEST REDIS
# TODO: ADD REDIS 
@app.delete("/enrollmentdrop/{studentid}/{classid}/{username}/{email}")
def drop_student_from_class(studentid: int, classid: int, username: str, email: str, r = Depends(get_redis)):
    """API to drop a class.
    
    Args:
        studentid: The student's ID.
        classid: The class ID.

    Returns:
        A dictionary with a message indicating the student's enrollment status.
    """
    check_user(studentid, username, email)
    new_updated_status = None
    updated_status = None
    updated_current_enrollment = None
    # Try to Remove student from the class
    status = get_enrollment_status(studentid, classid)
    if status == 'DROPPED':
        raise HTTPException(
            status_code=409,
            detail=f"Student with StudentID {studentid} is already dropped from class with ClassID {classid}"
        )
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Student with StudentID {studentid} is not enrolled in class with ClassID {classid}"
        )
    elif status == 'WAITLISTED':
        raise HTTPException(
            status_code=404,
            detail=f"Student with StudentID {studentid} is on the waitlist for class {classid}. Drop from the waitlist instead."
        )
    elif status == 'ENROLLED':
        new_status = 'DROPPED'
        response = retrieve_enrollment_record_id(studentid, classid)
        updated_status = update_enrollment_status(response, new_status)
        # Decrement the CurrentEnrollment for the class
        updated_current_enrollment = update_current_enrollment(classid, increment=False)
        if updated_current_enrollment:
            # TODO: work on the logic for redis 
            next_on_waitlist = r.lpop(f"waitClassID_{classid}")
            if next_on_waitlist:
                new_status = 'ENROLLED'
                new_response = retrieve_enrollment_record_id(next_on_waitlist, classid)
                new_updated_status = update_enrollment_status(new_response, new_status)
                updated_current_enrollment = update_current_enrollment(classid, increment=True)
            
            return {
                "message": "Class dropped updated successfully",
                "updated_status": updated_status,
                "new_student": new_updated_status,
                "updated_current_enrollment": updated_current_enrollment
            }
        else:
            return {"message": "Class dropped updated successfully",
                "updated_status": updated_status,
                "updated_current_enrollment": updated_current_enrollment}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to update enrollment status"
        )
    


    # Add student to class if there are students in the waitlist for this class
    # next_on_waitlist = db.execute("SELECT * FROM Waitlists WHERE ClassID = ? ORDER BY Position ASC", (classid,)).fetchone()
    # TODO: add redis according to dynamodb 
    # next_on_waitlist = r.lpop(f"waitClassID_{classid}")
    # if next_on_waitlist:
    #     try:
    #         db.execute("INSERT INTO Enrollments(StudentID, ClassID, SectionNumber,EnrollmentStatus) \
    #                         VALUES (?, ?, ?,'ENROLLED')", (next_on_waitlist, classid, sectionid))
    #         # db.execute("DELETE FROM Waitlists WHERE StudentID = ? AND ClassID = ?", (next_on_waitlist['StudentID'], classid))
    #         # db.execute("UPDATE Classes SET WaitlistCount = WaitlistCount - 1 WHERE ClassID = ?", (classid,))
    #         db.commit()
    #     except sqlite3.IntegrityError as e:
    #         raise HTTPException(
    #             status_code=status.HTTP_400_BAD_REQUEST,
    #             detail={
    #                 "ErrorType": type(e).__name__, 
    #                 "ErrorMessage": str(e)
    #             },
    #         )
        
    #     return {"Result": [
    #         {"Student dropped from class": dropped_student}, 
    #         {"Student added from waitlist": next_on_waitlist},
    #     ]}
    # return {"Result": [{"Student dropped from class": dropped_student} ]}

# TODO: test this endpoint 
@app.delete("/waitlistdrop/{studentid}/{classid}/{username}/{email}")
def remove_student_from_waitlist(studentid: int, classid: int, username: str, email: str, r = Depends(get_redis)):
    """API to drop a class from waitlist.
    
    Args:
        studentid: The student's ID.
        classid: The class ID.

    Returns:
        A dictionary with a message indicating the student's enrollment status.
    """
    check_user(studentid, username, email)
    # exists = db.execute("SELECT * FROM Waitlists WHERE StudentID = ? AND ClassID = ?", (studentid, classid)).fetchone()
    status = get_enrollment_status(studentid, classid)
    if status == 'DROPPED':
        raise HTTPException(
            status_code=409,
            detail=f"Student with StudentID {studentid} is already dropped from class with ClassID {classid}"
        )
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Student with StudentID {studentid} is not enrolled in class with ClassID {classid}"
        )
    elif status == 'ENROLLED':
        raise HTTPException(
            status_code=409,
            detail=f"Student with StudentID {studentid} is enrolled in class with ClassID {classid}"
        )
    if status == 'WAITLISTED':
        new_status = 'DROPPED'
        updated_status = update_enrollment_status(retrieve_enrollment_record_id(studentid, classid), new_status)
        if not updated_status:
            raise HTTPException(
                status_code=500,
                detail="Student was not on the waitlist"
            )
        
        exists = r.lrem(f"waitClassID_{classid}", 0, studentid)
        if exists == 0:
            raise HTTPException(
                status_code=400,
                detail={"Error": "No such student found in the given class on the waitlist"}
            )
        
    return {"Element removed": studentid}
    
# TODO: test this endpoint and update dynamo
@app.get("/waitlist/{studentid}/{classid}/{username}/{email}")
def view_waitlist_position(studentid: int, classid: int, username: str, email: str, r = Depends(get_redis)):
    """API to view a student's position on the waitlist.

    Args:
        studentid: The student's ID.
        classid: The class ID.

    Returns:
        A dictionary with a message indicating the student's position on the waitlist.
    """
    check_user(studentid, username, email)
    position = redis.lpos(f"waitClassID_{classid}", studentid)
    
    if position:
        message = f"Student {studentid} is on the waitlist for class {classid} in position"
    else:
        message = f"Student {studentid} is not on the waitlist for class {classid}"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=message,
        )
    return {message: position}
    
### Instructor related endpoints
# TODO: ENDPOINT WORKING, ONLY RETURNS STUDENT ID AND ENROLLMENT STATUS, works in krakend
@app.get("/enrolled/{instructorid}/{classid}/{username}/{email}")
def view_enrolled(instructorid: int, classid: int, username: str, email: str):
    """API to view all students enrolled in a class.
    
    Args:
        instructorid: The instructor's ID.
        classid: The class ID.

    Returns:
        A dictionary with a list of students enrolled in the instructor's classes.
    """
    check_user(instructorid, username, email)
    if not is_instructor_for_class(instructorid, classid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Instructor with InstructorID {instructorid} is not an instructor for class with ClassID {classid}"
        )
    enrolled_students = get_students_for_class(classid, 'ENROLLED')
    if not enrolled_students:
        raise HTTPException(status_code=404, detail="No enrolled students found for this class.")
    return {"Enrolled Students": enrolled_students}


# TODO: ENDPOINT WORKING, ONLY RETURNS STUDENT ID AND ENROLLMENT STATUS, errors working as well, works in krakend
@app.get("/dropped/{instructorid}/{classid}/{username}/{email}")
def view_dropped_students(instructorid: int, classid: int, username: str, email: str):
    """API to view all students dropped from a class.
    
    Args:
        instructorid: The instructor's ID.

    Returns:
        A dictionary with a list of students dropped from the instructor's classes.
    """
    check_user(instructorid, username, email)
    if not is_instructor_for_class(instructorid, classid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Instructor with InstructorID {instructorid} is not an instructor for class with ClassID {classid}"
        )
    
    dropped_students = get_students_for_class(classid, 'DROPPED')
    if not dropped_students:
        raise HTTPException(status_code=404, detail="No dropped students found for this class.")
    return {"Dropped Students": dropped_students}

# TODO: endpoint fully working, works in krakend
# TODO: add redis to add next on waitlist to class
@app.delete("/drop/{instructorid}/{classid}/{studentid}/{username}/{email}")
def drop_student_administratively(instructorid: int, classid: int, studentid: int, username: str, email: str, redis = Depends(get_redis)):
    """API to drop a student from a class.
    
    Args:
        instructorid: The instructor's ID.
        classid: The class ID.
        studentid: The student's ID.

    Returns:
        A dictionary with a message indicating the student's enrollment status.
    """
    check_user(instructorid, username, email)
    if not is_instructor_for_class(instructorid, classid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Instructor with InstructorID {instructorid} is not an instructor for class with ClassID {classid}"
        )
    status = get_enrollment_status(studentid, classid)
    if status == 'DROPPED':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with StudentID {studentid} is already dropped from class with ClassID {classid}"
        )
    # retrieve record id from dynamo
    response = retrieve_enrollment_record_id(studentid, classid)
    updated_status = update_enrollment_status(response, 'DROPPED')
    if not updated_status:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update enrollment status"
        )
    # Decrement the CurrentEnrollment for the class
    updated_current_enrollment = update_current_enrollment(classid, increment=False)
    if updated_current_enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update current enrollment"
        )
    # Add student to class if there are students in the waitlist for this class
    # TODO: add redis here
    return {"message": f"Student {studentid} has been administratively dropped from class {classid} by instructor {instructorid}"}


# TODO: Need to test with redis
@app.get("/waitlist/{instructorid}/{classid}/{username}/{email}")
def view_waitlist(instructorid: int, classid: int, username: str, email: str, redis = Depends(get_redis)):
    """API to view the waitlist for a class.
    
    Args:
        instructorid: The instructor's ID.

    Returns:
        A dictionary with a list of students on the waitlist for the instructor's classes.
    """
    check_user(instructorid, username, email)
    if not is_instructor_for_class(instructorid, classid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Instructor with InstructorID {instructorid} is not an instructor for class with ClassID {classid}"
        )    
    # TODO: might need to delete this if redundant
    waitlisted_students = get_students_for_class(classid, 'WAITLISTED')
    if not waitlisted_students:
        raise HTTPException(status_code=404, detail="No waitlisted students found for this class.")    

    student_ids = redis.lrange(f"waitClassID_{classid}", 0, -1)
    if not len(student_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No students found in the waitlist for this class")
    return {"Waitlist": [{"student_id": int(student)} for student in student_ids]}

### Registrar related endpoints
# TODO: ENDPOINT WORKING, WORKS WITH KRAKEND AS WELL
# TODO: probably need to create a redis waitlist 
@app.post("/add/{sectionid}/{coursecode}/{classname}/{department}/{professorid}/{enrollmax}/{status}/{waitmax}")
def add_class(request: Request, sectionid: int, coursecode: str, classname: str, department:str, professorid: int, enrollmax: int, status: str, waitmax: int):
    """API to add a class to the catalog.
    
    Args:
        sectionid: The section ID.
        coursecode: The course code.
        classname: The class name.
        department: The department.
        professorid: The professor's ID.
        enrollmax: The maximum enrollment.
        status: The status of the class.
        waitmax: The maximum waitlist.

    Returns:
        A dictionary with a message indicating the class was added successfully.
    """
    instructor_req = requests.get(f"http://localhost:{KRAKEND_PORT}/user/get/{professorid}", headers={"Authorization": request.headers.get("Authorization")})
    instructor_info = instructor_req.json()

    if instructor_req.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instructor does not exist",
        )
    check_user(instructor_info["userid"], instructor_info["username"], instructor_info["email"])
    # check if combination of coursecode and sectionid already exists
    existing_class = classes_table.query(
        IndexName='SectionNumber-CourseCode-index',
        KeyConditionExpression=Key('SectionNumber').eq(sectionid) & Key('CourseCode').eq(coursecode),
        ProjectionExpression='ClassID',
    )
    # If there's an existing class, return an error
    if existing_class.get('Items'):
        raise HTTPException(
            status_code=400,
            detail="Class with the given SectionNumber and CourseCode already exists",
        )

    # Query to find the highest existing ClassID
    response = classes_table.scan(
        ProjectionExpression='ClassID',
        Select='SPECIFIC_ATTRIBUTES',
    )
    items = response.get('Items', [])

    # Find the highest ClassID
    highest_class_id = 0
    for item in items:
        class_id = item.get('ClassID', 0)
        if class_id > highest_class_id:
            highest_class_id = class_id

    # Calculate the new ClassID
    new_class_id = highest_class_id + 1

    # Create the new class item
    new_class_item = {
        "ClassID": new_class_id,
        "SectionNumber": sectionid,
        "CourseCode": coursecode,
        "ClassName": classname,
        "Department": department,
        "InstructorID": professorid,
        "MaxCapacity": enrollmax,
        "CurrentEnrollment": 0,
        "CurrentWaitlist": 0,
        "State": status,
        "WaitlistMaximum": waitmax,
    }
    # Insert the new class item into the classes table
    try:

        classes_table.put_item(Item=new_class_item)
        return {"message": f"Class with ClassID {new_class_id} added successfully", "class_details": new_class_item}
    except ClientError as e:
        print(f"Error adding class with ClassID {new_class_id}: {e.response['Error']['Message']}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add class"
        )



# TODO: endpoint fully working, works in krakend add redis please
# TODO: probably need to drop wailist for this class in redis
@app.delete("/remove/{classid}")
def remove_class(classid: int):
    """API to remove a class from the catalog.
    
    Args:
        classid: The class ID.

    Returns:
        

    """
    class_item = check_class_exists(classid)
    dropped_students = []

    if class_item.get('CurrentEnrollment') > 0:
        # drop all the students in the class before deleting class
        dropped_students = drop_students_from_class(classid)
        if not dropped_students:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to drop students from class {classid}"
            )
    response = classes_table.delete_item(Key={'ClassID': classid})
    if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
        return {"message": f"Class with ClassID {classid} deleted successfully", "dropped_students": dropped_students}
    else:
        return {"message": f"Failed to delete class with ClassID {classid}"}



# TODO: endpoint tested and fully working, works in krakend
@app.put("/state/{classid}/{state}")
def state_enrollment(classid: int, state: str):
    """API to change class between active and inactive.
    
    Args:
        classid: The class ID.
        state: The desired state for the class.

    Returns:
        A dictionary with a message indicating the class was successfully updated.
    """
    record = check_class_exists(classid)
    
    if state not in ['active', 'inactive']:
        return {"message": "Invalid state provided"}
    if record.get('State') == state:
        return {"message": f"Class is already in the {state} state"}
    response = classes_table.update_item(
        Key={'ClassID': classid},
        UpdateExpression='SET #state_attribute = :state',
        ExpressionAttributeValues={':state': state},
        ExpressionAttributeNames={'#state_attribute': 'State'},
        ReturnValues='UPDATED_NEW'
    )
    updated_item = response.get('Attributes')
    if updated_item:
        return {"message": f"Class updated to {state} successfully"}
    else:
        return {"message": f"Failed to update class to {state}"}


# TODO: ENDPOINT WORKING, WORKS WITH KRAKEND
@app.put("/change/{classid}/{newprofessorid}")
def change_prof(request: Request, classid: int, newprofessorid: int):
    """API to change the professor for a class.
    
    Args:
        classid: The class ID.
        newprofessorid: The new professor's ID.

    Returns:
        A dictionary with a message indicating the professor was successfully updated.
    """
    instructor_req = requests.get(f"http://localhost:{KRAKEND_PORT}/user/get/{newprofessorid}", headers={"Authorization": request.headers.get("Authorization")})
    instructor_info = instructor_req.json()

    if instructor_req.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instructor does not exist",
        )
    check_user(instructor_info["userid"], instructor_info["username"], instructor_info["email"])
    class_item = check_class_exists(classid)
    if class_item.get('InstructorID') == newprofessorid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Instructor already teaches this class",
        )
    response = classes_table.update_item(
        Key={'ClassID': classid},
        UpdateExpression='SET InstructorID = :instructor_id',
        ExpressionAttributeValues={':instructor_id': newprofessorid},
        ReturnValues='UPDATED_NEW'
    )
    updated_item = response.get('Attributes')
    if updated_item:
        return {"message": f"Instructor updated to user with UserID '{newprofessorid}' successfully"}
    else:
        return {"message": f"Failed to update instructor to {newprofessorid}"}
 

# Redis examples
@app.put("/add/{classid}/{studentid}")
def freeze_enrollment(classid: str, studentid: str, db = Depends(get_redis)):
    db.rpush(f"waitClassID_{classid}", studentid)

@app.delete("/remove/{classid}")
def freeze_enrollment(classid: str, db = Depends(get_redis)):
    studentid = db.lpop(f"waitClassID_{classid}")
    return studentid

@app.get("/lpos/{classid}/{studentid}")
def freeze_enrollment(classid: str, studentid:str, db = Depends(get_redis)):
    studentidd = db.lpos(f"waitClassID_{classid}", studentid)
    return studentidd

@app.get("/waitt/{classid}/{studentid}")
def freeze_enrollment(classid: int, studentid: int, db = Depends(get_redis)):
    id = retrieve_enrollment_record_id(studentid, classid)
    return id#update_enrollment_status(id, "WAITLIST")