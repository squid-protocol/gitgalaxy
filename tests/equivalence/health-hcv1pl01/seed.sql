INSERT INTO HCZMSA1.patient (patientId, userName, firstName, lastName, dateOfBirth, insCardNumber, address, city, postcode, phoneMobile, emailAddress) VALUES (1, 'SEEDUSER1', 'Seed', 'One', '1980-01-01', '1111111111', '1 Seed Road', 'Seedtown', 'SE1 1AA', '07000000001', 'one@example.com');
INSERT INTO HCZMSA1.patient (patientId, userName, firstName, lastName, dateOfBirth, insCardNumber, address, city, postcode, phoneMobile, emailAddress) VALUES (2, 'SEEDUSER2', 'Seed', 'Two', '1981-02-02', '2222222222', '2 Seed Road', 'Seedtown', 'SE2 2AA', '07000000002', 'two@example.com');
INSERT INTO HCZMSA1.threshold (patientId, heartRate, bloodPressure) VALUES (2, 100, '130/85');
INSERT INTO HCZMSA1.bloodpressure (patientId, bpDateTime, bloodPressure) VALUES (2, '2026-11-09-10.30.15.000000', '110/70');
INSERT INTO HCZMSA1.heartrate (patientId, hrDateTime, heartRate) VALUES (2, '2026-11-09-10.30.15.000000', 80);
