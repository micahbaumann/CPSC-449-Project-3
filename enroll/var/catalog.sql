PRAGMA foreign_keys=ON;
BEGIN TRANSACTION;

CREATE TABLE Users (
    UserId INTEGER NOT NULL PRIMARY KEY,
    Username VARCHAR(30) NOT NULL UNIQUE,
    FullName VARCHAR(100) NOT NULL,
    Email VARCHAR(100) NOT NULL
);

CREATE TABLE Classes (
    ClassID INT NOT NULL UNIQUE,
    CourseCode VARCHAR(15) NOT NULL DEFAULT 'XXX 001',
    SectionNumber INT NOT NULL,
    Name VARCHAR(100) DEFAULT "Class",
    MaximumEnrollment INT DEFAULT 30,
    WaitlistCount INT DEFAULT 0,
    WaitlistMaximum INT DEFAUlT 15,
    PRIMARY KEY (ClassID, SectionNumber)
);

CREATE TABLE Students (
    StudentID INTEGER PRIMARY KEY NOT NULL UNIQUE,
    FOREIGN KEY (StudentID) REFERENCES Users(UserId)
);

CREATE TABLE Enrollments (
    EnrollmentID INTEGER         NOT NULL PRIMARY KEY AUTOINCREMENT,
    StudentID INT                NOT NULL,
    ClassID INT                  NOT NULL,
    SectionNumber INT            NOT NULL,
    EnrollmentStatus VARCHAR(25) NOT NULL DEFAULT "ENROLLED",
    FOREIGN KEY (StudentID) REFERENCES Students(StudentID),
    FOREIGN KEY (ClassID, SectionNumber) REFERENCES Classes(ClassID, SectionNumber)
);

CREATE TABLE Instructors (
    InstructorID INTEGER PRIMARY KEY NOT NULL UNIQUE,
    FOREIGN KEY (InstructorID) REFERENCES Users(UserId)
);

CREATE TABLE InstructorClasses (
    InstructorClassesID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    InstructorID INT            NOT NULL,
    ClassID INT                 NOT NULL,
    SectionNumber INT           NOT NULL,
    FOREIGN KEY (InstructorID) REFERENCES Instructors(InstructorID),
    FOREIGN KEY (ClassID, SectionNumber) REFERENCES Classes(ClassID, SectionNumber)
);

CREATE TABLE Waitlists (
    WaitlistID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    StudentID INT      NOT NULL,
    ClassID INT        NOT NULL,
    SectionNumber INT  NOT NULL,
    Position INT       NOT NULL,
    FOREIGN KEY (StudentID) REFERENCES Students(StudentID),
    FOREIGN KEY (ClassID, SectionNumber) REFERENCES Classes(ClassID, SectionNumber)
);

CREATE TABLE Freeze (
    IsFrozen BOOLEAN DEFAULT 0
);

INSERT INTO Freeze VALUES (0);

COMMIT;
