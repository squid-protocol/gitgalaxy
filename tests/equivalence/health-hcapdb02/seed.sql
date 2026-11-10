INSERT INTO HCZMSA1.patient (patientId, userName, firstName, lastName, dateOfBirth) VALUES (5, 'SEEDUSER5', 'Seed', 'Five', '1980-01-01');
INSERT INTO HCZMSA1.patient (patientId, userName, firstName, lastName, dateOfBirth) VALUES (6, 'SEEDUSER6', 'Seed', 'Six', '1981-02-02');
INSERT INTO HCZMSA1.user (patientId, userName, userPassword) VALUES (6, 'DUPUSER', 'DUPUSER');
