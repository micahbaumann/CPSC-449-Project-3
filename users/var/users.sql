PRAGMA foreign_keys=ON;
BEGIN TRANSACTION;

DROP TABLE IF EXISTS UserRoles;
DROP TABLE IF EXISTS Roles;
DROP TABLE IF EXISTS Registrations;

CREATE TABLE Registrations (
    UserId INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    Username VARCHAR(30) NOT NULL UNIQUE,
    FullName VARCHAR(100) NOT NULL,
    Email VARCHAR(100) NOT NULL,
    UserPassword VARCHAR(255) NOT NULL,
    BearerToken VARCHAR(255)
);

INSERT INTO Registrations(UserId, Username, FullName, Email, UserPassword) VALUES 
(1, "fara",  "Fara Smith", "fsmith@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(2, "steve",  "Steve Jobs", "sjobs@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(3, "andy",  "Andy Jones", "ajones@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(4, "tim",  "Tim Raft",   "traft@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(5, "elizabeth",  "Elizabeth Barnes", "ebarnes@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(6, "george",  "George Derns", "gderns@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(7, "pheobe",  "Pheobe Essek", "pessek@fsmithcsu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(8, "earl",  "Earl Poppins", "epoppins@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(9, "sarah",  "Sarah Colyt", "fsmith@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(10, "anna", "Anna Kant", "akant@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(11, "micah", "Micah Baumann", "mbaumann@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ="),
(12, "edwin", "Edwin Peraza", "edwinperaza@csu.fullerton.edu", "pbkdf2_sha256$600000$c9fc625a0e406cec90594958016ac631$5iDVmwSTF6K9K110LWBxH/xi0ZvwpgKt3y8gAMz0GzQ=");

CREATE TABLE Roles (
    RoleId INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    RoleName VARCHAR(30) NOT NULL
);

INSERT INTO Roles VALUES 
(1, 'Student'),
(2, 'Instructor'),
(3, 'Registrar');

CREATE TABLE UserRoles (
    Id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    RoleId INT NOT NULL REFERENCES Roles(RoleId),
    UserId INT NOT NULL REFERENCES Registrations(UserId)
);

INSERT INTO UserRoles(RoleId, UserId) VALUES 
(1, 1),
(1, 2),
(1, 3),
(1, 4),
(2, 5),
(2, 6),
(2, 7),
(3, 8),
(3, 9),
(3, 10),
(1, 11),
(2, 11),
(3, 11),
(1, 12),
(2, 12),
(3, 12);

COMMIT;
