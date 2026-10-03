CREATE DATABASE IF NOT EXISTS blood_management;
USE blood_management;

CREATE TABLE admin (
    admin_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE,
    password VARCHAR(255)
);

CREATE TABLE donor (
    donor_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    age INT,
    gender VARCHAR(20),
    blood_group VARCHAR(5) NOT NULL,
    phone VARCHAR(15) NOT NULL,
    last_donation_date DATE
);

CREATE TABLE donor_health (
    health_id INT PRIMARY KEY AUTO_INCREMENT,
    donor_id INT NOT NULL,
    medical_history TEXT,
    weight DECIMAL(5,2),
    blood_pressure VARCHAR(20),
    hemoglobin DECIMAL(5,2),
    health_status VARCHAR(30),
    checked_date DATE,
    FOREIGN KEY (donor_id) REFERENCES donor(donor_id) ON DELETE CASCADE
);

CREATE TABLE donor_eligibility (
    eligibility_id INT PRIMARY KEY AUTO_INCREMENT,
    donor_id INT NOT NULL,
    last_donation_date DATE,
    eligible_date DATE,
    status VARCHAR(30),
    FOREIGN KEY (donor_id) REFERENCES donor(donor_id) ON DELETE CASCADE
);

CREATE TABLE donation (
    donation_id INT PRIMARY KEY AUTO_INCREMENT,
    donor_id INT NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    donation_date DATE NOT NULL,
    quantity DECIMAL(5,2) NOT NULL,
    expiry_date DATE NOT NULL,
    FOREIGN KEY (donor_id) REFERENCES donor(donor_id) ON DELETE CASCADE
);

CREATE TABLE blood_stock (
    stock_id INT PRIMARY KEY AUTO_INCREMENT,
    donation_id INT UNIQUE NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    quantity DECIMAL(5,2) NOT NULL,
    collection_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    status VARCHAR(30) DEFAULT 'Available',
    FOREIGN KEY (donation_id) REFERENCES donation(donation_id) ON DELETE CASCADE
);

CREATE TABLE hospital (
    hospital_id INT PRIMARY KEY AUTO_INCREMENT,
    hospital_name VARCHAR(150) NOT NULL,
    address TEXT,
    phone VARCHAR(15)
);

CREATE TABLE blood_request (
    request_id INT PRIMARY KEY AUTO_INCREMENT,
    hospital_id INT NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    quantity DECIMAL(5,2) NOT NULL,
    request_date DATE NOT NULL,
    priority VARCHAR(20),
    status VARCHAR(30) DEFAULT 'Pending',
    FOREIGN KEY (hospital_id) REFERENCES hospital(hospital_id) ON DELETE CASCADE
);

-- TRIGGERS
DELIMITER //
CREATE TRIGGER prevent_unapproved_donation
BEFORE INSERT ON donation
FOR EACH ROW
BEGIN
    DECLARE is_approved INT DEFAULT 0;
    SELECT COUNT(*) INTO is_approved FROM donor_eligibility WHERE donor_id = NEW.donor_id AND status = 'Approved';
    IF is_approved = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Donor is not medically approved for donation.';
    END IF;
END //
DELIMITER ;

-- VIEWS
CREATE VIEW blood_expiry_view AS
SELECT stock_id, blood_group, quantity, collection_date, expiry_date,
CASE WHEN expiry_date < CURDATE() THEN 'Expired' WHEN DATEDIFF(expiry_date, CURDATE()) <= 7 THEN 'Near Expiry' ELSE 'Available' END AS calculated_status
FROM blood_stock WHERE status = 'Available' AND DATEDIFF(expiry_date, CURDATE()) <= 7;

CREATE VIEW available_blood_view AS
SELECT blood_group, SUM(quantity) AS total_quantity FROM blood_stock WHERE status = 'Available' AND expiry_date >= CURDATE() GROUP BY blood_group;

-- PROCEDURES
DELIMITER //
CREATE PROCEDURE get_available_blood(IN bg VARCHAR(5))
BEGIN
    SELECT blood_group, SUM(quantity) as available_qty FROM blood_stock WHERE blood_group = bg AND status = 'Available' AND expiry_date >= CURDATE() GROUP BY blood_group;
END //
DELIMITER ;

-- SAMPLE DATA
INSERT INTO admin (username, password) VALUES ('admin', 'admin123');
INSERT INTO donor (name, age, gender, blood_group, phone) VALUES ('John Doe', 30, 'Male', 'O+', '1234567890'), ('Jane Smith', 25, 'Female', 'A-', '0987654321');
INSERT INTO hospital (hospital_name, address, phone) VALUES ('City Care Hospital', '123 Main St', '1112223333');