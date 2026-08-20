# Migrating Database from EC2 to the RDS server

In `ec2/variables.tf` file set real values of:
- ami_id
- subnet_id
- vpc_id

In `rds/variables.tf` file set real values of:
- rds_vpc
- subnet_ids

## Apply terraform code

```bash
terraform init
terraform validate
terraform plan
terraform apply
```

### Install mysql on EC2 instance

#### Connect to the EC2 instance
On `AWS > EC2 > Instances` -> choose: `db_serwer` -> Click `Connect` button.

#### Install mysql

```bash
# Downloading mysql on EC2 Amazon Linux
sudo wget https://dev.mysql.com/get/mysql80-community-release-el9-5.noarch.rpm
sudo rpm --import https://repo.mysql.com/RPM-GPG-KEY-mysql-2025
sudo dnf install mysql80-community-release-el9-5.noarch.rpm -y
dnf repolist enabled | grep "mysql.*-community.*"
sudo dnf install mysql-community-server -y
sudo systemctl start mysqld
# test
sudo systemctl status mysqld

# get the root inital password
cd /var/log
sudo cat mysqld.log | grep password
# *** output (example) ***
# 2025-08-01T14:21:03.386417Z 6 [Note] [MY-010454] [Server] A temporary password is generated for root@localhost: XBcmIOuln4-i

cd ~
sudo su -
mysql -u root -p
# enter password: XBcmIOuln4-i

# Change the initial password
ALTER USER root@localhost IDENTIFIED BY 'Admin@123';
SHOW DATABASES;
# *** output ***
# +--------------------+
# | Database           |
# +--------------------+
# | information_schema |
# | mysql              |
# | performance_schema |
# | sys                |
# +--------------------+

CREATE DATABASE ec2db;
USE ec2db;

CREATE TABLE Employee (
    FirstName VARCHAR(20),
    LastName VARCHAR(20),
    DoB DATE
);

INSERT INTO Employee (FirstName, LastName, DoB) 
VALUES ("John", "Smith", '2000-03-17');
INSERT INTO Employee (FirstName, LastName, DoB) 
VALUES ("Jan", "Kowalski", '2000-03-17');

SELECT * FROM Employee;
# *** output ***
# +-----------+-----------+------------+
# | FirstName | LastName  | DoB        |
# +-----------+-----------+------------+
# | John      | Smith     | 2000-03-17 |
# | Jan       | Kowalski  | 2000-03-17 |
# +-----------+-----------+------------+

exit;
```

#### Connect to RDS database

Open: `AWS > Aurora and RDS > Databases` -> click na the `DB identifier`
From `Endpoint & port` copy the Endpoint e.g.:
`terraform-20250801140705343900000001.c34keo06inrq.eu-central-1.rds.amazonaws.com`

Connect to RDS database (on EC2)

```bash
# [root@ip-172-31-20-130 ~]#
mysql -h terraform-20250801140705343900000001.c34keo06inrq.eu-central-1.rds.amazonaws.com -P 3306 -u admin -p
# enter password: password123

SHOW DATABASES;
# *** output ***
# +--------------------+
# | Database           |
# +--------------------+
# | information_schema |
# | mydatabase         |
# | mysql              |
# | performance_schema |
# | sys                |
# +--------------------+

USE mydatabase;   # define in main.tf
SHOW TABLES;
# *** output ***
# Empty set (0.00 sec)
exit;

# Dump the ec2db database from MySQL to db.sql file
mysqldump -u root -p ec2db > db.sql 
# Enter password: Admin@123
ls
# *** output ***
# db.sql

# Load (migrate) the data from db.sql to RDS (to mydatabase)
mysql -h terraform-20250801140705343900000001.c34keo06inrq.eu-central-1.rds.amazonaws.com -u admin -P 3306 -p mydatabase < db.sql
# enter password: password123

# test
mysql -h terraform-20250801140705343900000001.c34keo06inrq.eu-central-1.rds.amazonaws.com -P 3306 -u admin -p
# enter password: password123

USE mydatabase;
SHOW TABLES;
# *** output ***
# +----------------------+
# | Tables_in_mydatabase |
# +----------------------+
# | Employee             |
# +----------------------+
```

```bash
cat db.sql
# *** output ***
# -- MySQL dump 10.13  Distrib 8.0.43, for Linux (x86_64)
# --
# -- Host: localhost    Database: ec2db
# -- ------------------------------------------------------
# -- Server version       8.0.43

# /*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
# /*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
# /*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
# /*!50503 SET NAMES utf8mb4 */;
# /*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
# /*!40103 SET TIME_ZONE='+00:00' */;
# /*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
# /*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
# /*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
# /*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

# --
# -- Table structure for table `Employee`
# --

# DROP TABLE IF EXISTS `Employee`;
# /*!40101 SET @saved_cs_client     = @@character_set_client */;
# /*!50503 SET character_set_client = utf8mb4 */;
# CREATE TABLE `Employee` (
#   `FirstName` varchar(20) DEFAULT NULL,
#   `LastName` varchar(20) DEFAULT NULL,
#   `DoB` date DEFAULT NULL
# ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
# /*!40101 SET character_set_client = @saved_cs_client */;

# --
# -- Dumping data for table `Employee`
# --

# LOCK TABLES `Employee` WRITE;
# /*!40000 ALTER TABLE `Employee` DISABLE KEYS */;
# INSERT INTO `Employee` VALUES ('Gauri','Shirkande','2000-03-17'),('Jan','Kowalski','2000-03-17');
# /*!40000 ALTER TABLE `Employee` ENABLE KEYS */;
# UNLOCK TABLES;
# /*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

# /*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
# /*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
# /*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
# /*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
# /*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
# /*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
# /*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

# -- Dump completed on 2025-08-01 14:53:19
```

### Cleanup

```bash
terraform destroy
```