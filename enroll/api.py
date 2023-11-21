import sqlite3
import contextlib
import requests
import redis
import boto3

from fastapi import FastAPI, Depends, HTTPException, status, Request
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

WAITLIST_MAXIMUM = 15
MAXIMUM_WAITLISTED_CLASSES = 3
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

def check_id_exists_in_table(id_name: str,id_val: int, table_name: str, db: sqlite3.Connection = Depends(get_db)) -> bool:
    """return true if value found, false if not found"""
    vals = db.execute(f"SELECT * FROM {table_name} WHERE {id_name} = ?",(id_val,)).fetchone()
    if vals:
        return True
    else:
        return False


def check_user(id_val: int, username: str, name: str, email: str, roles: list, db: sqlite3.Connection = Depends(get_db)):
    vals = db.execute(f"SELECT * FROM Users WHERE UserId = ?",(id_val,)).fetchone()
    if not vals:
        db.execute("INSERT INTO Users(Userid, Username, FullName, Email) VALUES(?,?,?,?)",(id_val, username, name, email))

        if "Student" in roles:
            db.execute("INSERT INTO Students (StudentId) VALUES (?)",(id_val,))

        if "Instructor" in roles:
            db.execute("INSERT INTO Instructors (InstructorId) VALUES (?)",(id_val,))
        
        db.commit()


def check_role(user_id: int):
    response = users_table.query(KeyConditionExpression=Key('UserId').eq(user_id))
    user_item = response.get('Items')[0] if 'Items' in response else None

    if not user_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with UserId {user_id} not found"
        )
    
    role = user_item.get('Role')
    if role not in ['Registrar', 'Instructor', 'Student']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid role for user with UserId {user_id}"
        )

    return role


def check_class_exists(class_id: int):
    response = classes_table.query(
        KeyConditionExpression=Key('ClassID').eq(class_id)
    )

    class_item = response.get('Items')[0] if 'Items' in response else None

    if not class_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ClassID {class_id} not found"
        )

    return class_item


def get_last_enrollment_id():
    response = enrollments_table.query(
        KeyConditionExpression='EnrollmentID > :enrollment_id',
        ExpressionAttributeValues={':enrollment_id': 0},
        ScanIndexForward=False,  # Descending order to get the last record
        Limit=1
    )

    last_enrollment_item = response.get('Items')[0] if 'Items' in response else None

    if last_enrollment_item:
        return last_enrollment_item['EnrollmentID']
    else:
        return 0


def get_enrollment_status(student_id: int, class_id: int):
    response = enrollments_table.query(
        KeyConditionExpression=Key('StudentID').eq(student_id) & Key('ClassID').eq(class_id),
        ProjectionExpression='EnrollmentStatus',
        Limit=1
    )

    enrollment_item = response.get('Items')[0] if 'Items' in response else None

    if enrollment_item:
        return enrollment_item.get('EnrollmentStatus')
    else:
        return None


def update_enrollment_status(student_id: int, class_id: int, new_status: str):
    response = enrollments_table.update_item(
        Key={'StudentID': student_id, 'ClassID': class_id},
        UpdateExpression='SET EnrollmentStatus = :status',
        ExpressionAttributeValues={':status': new_status},
        ReturnValues='UPDATED_NEW'
    )

    updated_item = response.get('Attributes')

    if updated_item:
        return updated_item.get('EnrollmentStatus')
    else:
        return None
    

def update_current_enrollment(class_id: int, increment: bool = True):
    # Determine whether to increment or decrement
    update_expression = 'ADD CurrentEnrollment :delta' if increment else 'ADD CurrentEnrollment :delta * -1'
    
    # Set the value of :delta based on whether to increment or decrement
    expression_attribute_values = {':delta': 1} if increment else {':delta': -1}

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


### Student related endpoints

@app.get("/list")
def list_open_classes(db: sqlite3.Connection = Depends(get_db), r = Depends(get_redis)):
    """API to fetch list of available classes in catalog.

    Args:
        None

    Returns:
        A dictionary with a list of classes available for enrollment.
    """
    response = classes_table.scan()

    return {"Classes": response['Items']}
    # if (db.execute("SELECT IsFrozen FROM Freeze").fetchone()[0] == 1):
    #     return {"Classes": []}

    # classes = db.execute("SELECT * FROM Classes")
    # classes = db.execute(
    #     "SELECT * FROM Classes WHERE \
    #         Classes.MaximumEnrollment > (SELECT COUNT(EnrollmentID) FROM Enrollments WHERE Enrollments.ClassID = Classes.ClassID) \
    #         OR Classes.WaitlistMaximum > (SELECT COUNT(WaitlistID) FROM Waitlists WHERE Waitlists.ClassID = Classes.ClassID)"
    # )
    # TODO: add redis 
    classList = {"Classes": []}
    for aClass in classes.fetchall():
        if r.llen(f"waitClassID_{aClass['ClassID']}") < aClass["WaitlistMaximum"]:
            classList["Classes"].append(aClass)

    return classList


@app.post("/enroll/{studentid}/{classid}/{sectionid}/{name}/{username}/{email}/{roles}", status_code=status.HTTP_201_CREATED)
def enroll_student_in_class(studentid: int, classid: int, sectionid: int, name: str, username: str, email: str, roles: str, db: sqlite3.Connection = Depends(get_db), r = Depends(get_redis)):
    """API to enroll a student in a class.
    
    Args:
        studentid: The student's ID.
        classid: The class ID.

    Returns:
        A dictionary with a message indicating the student's enrollment status.
    """
    role = check_role(studentid)
    if role != 'Student':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User with UserId {studentid} is not a student"
        )
    # TODO: use class_item for waitlist 
    class_item = check_class_exists(classid)

    status = get_enrollment_status(studentid, classid)
    if status == 'ENROLLED':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with StudentID {studentid} is already enrolled in class with ClassID {classid}"
        )
    elif status == 'DROPPED':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with StudentID {studentid} was dropped from class with ClassID {classid}"
        )
    elif status == 'WAITLISTED':
        if class_item.get('CurrentEnrollment') >= class_item.get('MaximumEnrollment'):
            # TODO: add to waitlist instead of raising error
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Class with ClassID {classid} is full"
            )
        else:
            # Update the status to 'ENROLLED'
            new_status = 'ENROLLED'
            updated_status = update_enrollment_status(studentid, classid, new_status)

            # Increment the CurrentEnrollment for the class
            updated_current_enrollment = update_current_enrollment(classid, increment=True)
            
            if updated_status and updated_current_enrollment:
                return {
                    "message": "Enrollment updated successfully",
                    "updated_status": updated_status,
                    "updated_current_enrollment": updated_current_enrollment
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update enrollment status"
                )
    elif status is None:
        if class_item.get('CurrentEnrollment') < class_item.get('MaximumEnrollment'):
            new_enrollment_id = get_last_enrollment_id() + 1
            enrollment_item = {
                "EnrollmentID": new_enrollment_id,
                "StudentID": studentid,
                "ClassID": classid,
                "EnrollmentStatus": "ENROLLED"
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
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update current enrollment"
                )
        # else:
            # TODO: check if waitlist is not full and add to wailist if not full


  
    # TODO: create function to increment waitlist 


    
    # roles = [word.strip() for word in roles.split(",")]
    # check_user(studentid, db)
    
    # classes = db.execute("SELECT * FROM Classes WHERE ClassID = ?", (classid,)).fetchone()
    # if not classes:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="Class not found")
    
    # enrolled = db.execute("SELECT * FROM Enrollments WHERE ClassID = ? AND StudentID = ? AND EnrollmentStatus='ENROLLED'", (classid, studentid)).fetchone()
    # if enrolled:
    #     raise HTTPException(
    #         status_code=status.HTTP_409_CONFLICT,
    #         detail="Student already enrolled")
    
    # class_section = classes["SectionNumber"]
    # count = db.execute("SELECT COUNT() FROM Enrollments WHERE ClassID = ?", (classid,)).fetchone()[0]
    # waitlist_count = db.execute("SELECT COUNT() FROM Waitlists WHERE ClassID = ?", (classid,)).fetchone()[0]
    waitlist_count = r.llen(f"waitClassID_{classid}")
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
    r.rpush(f"waitClassID_{classid}", studentid)
        # return {"message": f"Enrolled in waitlist {class_section} of class {classid}."}
    # else:
        # return {"message": f"Unable to enroll in waitlist for the class, reached the maximum number of students"}

@app.delete("/enrollmentdrop/{studentid}/{classid}/{sectionid}/{name}/{username}/{email}/{roles}")
def drop_student_from_class(studentid: int, classid: int, sectionid: int, name: str, username: str, email: str, roles: str, db: sqlite3.Connection = Depends(get_db), r = Depends(get_redis)):
    # roles = [word.strip() for word in roles.split(",")]
    # check_user(studentid, username, name, email, roles, db)
    # Try to Remove student from the class
    status = get_enrollment_status(studentid, classid)
    if status == 'DROPPED':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with StudentID {studentid} is already dropped from class with ClassID {classid}"
        )
    if status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with StudentID {studentid} is not enrolled in class with ClassID {classid}"
        )
    elif status == 'ENROLLED':
        new_status = 'DROPPED'
        updated_status = update_enrollment_status(studentid, classid, new_status)
        # Decrement the CurrentEnrollment for the class
        updated_current_enrollment = update_current_enrollment(classid, increment=False)
        if updated_status and updated_current_enrollment:
            return {
                "message": "Class driooed updated successfully",
                "updated_status": updated_status,
                "updated_current_enrollment": updated_current_enrollment
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update enrollment status"
            )



    # dropped_student = db.execute("SELECT StudentID FROM Enrollments WHERE StudentID = ? AND ClassID = ? AND SectionNumber = ?",(studentid,classid,sectionid)).fetchone()
    # if not dropped_student:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND, 
    #         detail="Student and class combination not found")

    # query = db.execute("UPDATE Enrollments SET EnrollmentStatus = 'DROPPED' WHERE StudentID = ? AND ClassID = ?", (studentid, classid))
    # db.commit()
    # Add student to class if there are students in the waitlist for this class
    # next_on_waitlist = db.execute("SELECT * FROM Waitlists WHERE ClassID = ? ORDER BY Position ASC", (classid,)).fetchone()
    # TODO: add redis according to dynamodb 
    next_on_waitlist = r.lpop(f"waitClassID_{classid}")
    if next_on_waitlist:
        try:
            db.execute("INSERT INTO Enrollments(StudentID, ClassID, SectionNumber,EnrollmentStatus) \
                            VALUES (?, ?, ?,'ENROLLED')", (next_on_waitlist, classid, sectionid))
            # db.execute("DELETE FROM Waitlists WHERE StudentID = ? AND ClassID = ?", (next_on_waitlist['StudentID'], classid))
            # db.execute("UPDATE Classes SET WaitlistCount = WaitlistCount - 1 WHERE ClassID = ?", (classid,))
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "ErrorType": type(e).__name__, 
                    "ErrorMessage": str(e)
                },
            )
        
        return {"Result": [
            {"Student dropped from class": dropped_student}, 
            {"Student added from waitlist": next_on_waitlist},
        ]}
    return {"Result": [{"Student dropped from class": dropped_student} ]}

@app.delete("/waitlistdrop/{studentid}/{classid}/{name}/{username}/{email}/{roles}")
def remove_student_from_waitlist(studentid: int, classid: int, name: str, username: str, email: str, roles: str, db: sqlite3.Connection = Depends(get_db), r = Depends(get_redis)):
    # roles = [word.strip() for word in roles.split(",")]
    # check_user(studentid, username, name, email, roles, db)
    # exists = db.execute("SELECT * FROM Waitlists WHERE StudentID = ? AND ClassID = ?", (studentid, classid)).fetchone()
    status = get_enrollment_status(studentid, classid)
    if status == 'DROPPED':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with StudentID {studentid} is already dropped from class with ClassID {classid}"
        )
    if status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with StudentID {studentid} is not enrolled in class with ClassID {classid}"
        )
    elif status == 'ENROLLED':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with StudentID {studentid} is enrolled in class with ClassID {classid}"
        )
    if status == 'WAITLISTED':
        new_status = 'DROPPED'
        updated_status = update_enrollment_status(studentid, classid, new_status)
        if not updated_status:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Student was not on the waitlist"
            )

    exists = r.lrem(f"waitClassID_{classid}", 0, studentid)
    if exists == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"Error": "No such student found in the given class on the waitlist"}
        )
    # db.execute("DELETE FROM Waitlists WHERE StudentID = ? AND ClassID = ?", (studentid, classid))
    # db.execute("UPDATE Classes SET WaitlistCount = WaitlistCount - 1 WHERE ClassID = ?", (classid,))
    # db.commit()
    return {"Element removed": studentid}
    
@app.get("/waitlist/{studentid}/{classid}/{name}/{username}/{email}/{roles}")
def view_waitlist_position(studentid: int, classid: int, name: str, username: str, email: str, roles: str, db: sqlite3.Connection = Depends(get_db), r = Depends(get_redis)):
    roles = [word.strip() for word in roles.split(",")]
    check_user(studentid, username, name, email, roles, db)
    position = r.lpos(f"waitClassID_{classid}", studentid)
    
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

@app.get("/enrolled/{instructorid}/{classid}/{sectionid}/{name}/{username}/{email}/{roles}")
def view_enrolled(instructorid: int, classid: int, sectionid: int, name: str, username: str, email: str, roles: str, db: sqlite3.Connection = Depends(get_db)):
    roles = [word.strip() for word in roles.split(",")]
    check_user(instructorid, username, name, email, roles, db)
    instructor_class = db.execute("SELECT * FROM InstructorClasses WHERE classID=? AND SectionNumber=?",(classid,sectionid)).fetchone()
    if not instructor_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instructor does not have this class"
        )

    enrolled_students = db.execute("SELECT StudentID FROM Enrollments WHERE classID=? AND SectionNumber=? AND EnrollmentStatus='ENROLLED'",(classid,sectionid))
    enrolled = enrolled_students.fetchall()
    if enrolled:
        return {"All students enrolled in this instructor's classes" : enrolled}
    else:
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT
        )

@app.get("/dropped/{instructorid}/{classid}/{sectionid}/{name}/{username}/{email}/{roles}")
def view_dropped_students(instructorid: int, classid: int, sectionid: int, name: str, username: str, email: str, roles: str, db: sqlite3.Connection = Depends(get_db)):
    roles = [word.strip() for word in roles.split(",")]
    check_user(instructorid, username, name, email, roles, db)
    instructor_class = db.execute("SELECT * FROM InstructorClasses WHERE classID=? AND SectionNumber=?",(classid,sectionid)).fetchone()
    if not instructor_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instructor does not have this class"
        )
    
    query = "SELECT StudentID FROM Enrollments WHERE ClassID = ? AND SectionNumber = ? AND EnrollmentStatus = 'DROPPED'"
    dropped_students = db.execute(query, (classid, sectionid)).fetchall()
    if not dropped_students:
        raise HTTPException(status_code=404, detail="No dropped students found for this class.")
    return {"Dropped Students ID": [student["StudentID"] for student in dropped_students]}

@app.delete("/drop/{instructorid}/{classid}/{studentid}/{name}/{username}/{email}/{roles}")
def drop_student_administratively(instructorid: int, classid: int, studentid: int, name: str, username: str, email: str, roles: str, db: sqlite3.Connection = Depends(get_db)):
    roles = [word.strip() for word in roles.split(",")]
    check_user(instructorid, username, name, email, roles, db)
    instructor_class = db.execute("SELECT * FROM InstructorClasses WHERE classID=?",(classid,)).fetchone()
    if not instructor_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instructor does not have this class"
        )
    
    in_class = db.execute("SELECT * FROM Enrollments WHERE classID=? AND EnrollmentStatus='ENROLLED' AND StudentID=?",(classid, studentid)).fetchone()
    if not in_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student is not enrolled"
        )

    query = "UPDATE Enrollments SET EnrollmentStatus = 'DROPPED' WHERE StudentID = ? AND ClassID = ?"
    result = db.execute(query, (studentid, classid))
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Student, class, or section not found.")
    
    # Add student to class if there are students in the waitlist for this class
    next_on_waitlist = lpop(f"waitClassID_{classid}")
    if next_on_waitlist:
        try:
            db.execute("INSERT INTO Enrollments(StudentID, ClassID, SectionNumber,EnrollmentStatus) \
                            VALUES (?, ?, (SELECT SectionNumber FROM Classes WHERE ClassID=?), 'ENROLLED')", (next_on_waitlist, classid, classid))
            db.execute("UPDATE Classes SET WaitlistCount = WaitlistCount - 1 WHERE ClassID = ?", (classid,))
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "ErrorType": type(e).__name__, 
                    "ErrorMessage": str(e)
                },
            )
    return {"message": f"Student {studentid} has been administratively dropped from class {classid}"}

@app.get("/waitlist/{instructorid}/{classid}/{sectionid}/{name}/{username}/{email}/{roles}")
def view_waitlist(instructorid: int, classid: int, sectionid: int, name: str, username: str, email: str, roles: str, db: sqlite3.Connection = Depends(get_db), redis = Depends(get_redis)):
    roles = [word.strip() for word in roles.split(",")]
    check_user(instructorid, username, name, email, roles, db)
    instructor_class = db.execute("SELECT * FROM InstructorClasses WHERE classID=? AND SectionNumber=?",(classid,sectionid)).fetchone()
    if not instructor_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instructor does not have this class"
        )

    student_ids = redis.lrange(f"waitClassID_{classid}", 0, -1)
    if not len(student_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No students found in the waitlist for this class")
    return {"Waitlist": [{"student_id": int(student)} for student in student_ids]}

### Registrar related endpoints

@app.post("/add/{classid}/{sectionid}/{professorid}/{enrollmax}/{waitmax}", status_code=status.HTTP_201_CREATED)
def add_class(request: Request, classid: str, sectionid: str, professorid: int, enrollmax: int, waitmax: int, db: sqlite3.Connection = Depends(get_db)):
    instructor_req = requests.get(f"http://localhost:5200/user/get/{professorid}", headers={"Authorization": request.headers.get("Authorization")})
    instructor_info = instructor_req.json()

    if instructor_req.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instructor does not exist",
        )
    check_user(instructor_info["userid"], instructor_info["username"], instructor_info["name"], instructor_info["email"], instructor_info["roles"], db)

    try:
        db.execute("INSERT INTO Classes (ClassID, SectionNumber, MaximumEnrollment, WaitlistMaximum) VALUES(?, ?, ?, ?)", (classid, sectionid, enrollmax, waitmax))
        db.execute("INSERT INTO InstructorClasses (InstructorID, ClassID, SectionNumber) VALUES(?, ?, ?)", (professorid, classid, sectionid))
        db.commit()
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "ErrorType": type(e).__name__, 
                "ErrorMessage": str(e)
            },
        )
    return {"New Class Added":f"Course {classid} Section {sectionid}"}

@app.delete("/remove/{classid}/{sectionid}")
def remove_class(classid: str, sectionid: str, db: sqlite3.Connection = Depends(get_db)):

    class_found = db.execute("SELECT * FROM Classes WHERE ClassID = ? AND SectionNumber = ?",(classid,sectionid)).fetchone()
    if not class_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Class {classid} Section {sectionid} does not exist in database.")
    db.execute("DELETE FROM Classes WHERE ClassID =? AND SectionNumber =?", (classid, sectionid))
    db.execute("DELETE FROM InstructorClasses WHERE ClassID =? AND SectionNumber =?", (classid, sectionid))
    db.execute("DELETE FROM Enrollments WHERE ClassID =? AND SectionNumber =?", (classid, sectionid))
    db.commit()
    return {"Removed" : f"Course {classid} Section {sectionid}"}

@app.put("/freeze/{isfrozen}", status_code=status.HTTP_204_NO_CONTENT)
def freeze_enrollment(isfrozen: str, db: sqlite3.Connection = Depends(get_db)):
    if (isfrozen.lower() == "true"):
        db.execute("UPDATE Freeze SET IsFrozen = true")
        db.commit()
    elif (isfrozen.lower() == "false"):
        db.execute("UPDATE Freeze SET IsFrozen = false")
        db.commit()
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Freeze must be true or false.")

@app.put("/change/{classid}/{newprofessorid}", status_code=status.HTTP_204_NO_CONTENT)
def change_prof(request: Request, classid: int, newprofessorid: int, db: sqlite3.Connection = Depends(get_db)):
    instructor_req = requests.get(f"http://localhost:{KRAKEND_PORT}/user/get/{newprofessorid}", headers={"Authorization": request.headers.get("Authorization")})
    instructor_info = instructor_req.json()

    if instructor_req.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instructor does not exist",
        )

    check_user(instructor_info["userid"], instructor_info["username"], instructor_info["name"], instructor_info["email"], instructor_info["roles"], db)
    valid_class_id = check_id_exists_in_table("ClassID",classid,"Classes",db)
    if not valid_class_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class does not exist",
        )
    
    try:
        db.execute("UPDATE InstructorClasses SET InstructorID=? WHERE ClassID=?", (instructor_info["userid"], classid))
        db.commit()
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )

# Redis examples

@app.put("/add/{classid}/{studentid}", status_code=status.HTTP_204_NO_CONTENT)
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
