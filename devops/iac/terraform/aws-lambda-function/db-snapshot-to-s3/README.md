# AWS: lambda function -  export DB snapshot to s3

## RUN

- In `vars.tf` set:
  - the unique `name` of the bucket,
  - your root `account ID`.

```
terraform init
terraform apply
```

### Enter sample data in the DB

```
psql -h main123.c34keo06inrq.eu-central-1.rds.amazonaws.com -U adminuser -d db1 -c "
CREATE TABLE users (
id SERIAL PRIMARY KEY,
name VARCHAR(100) NOT NULL,
email VARCHAR(100) UNIQUE NOT NULL,
created_at TIMESTAMP DEFAULT NOW()
);"
```

- password = pass123908089

```
psql -h main123.c34keo06inrq.eu-central-1.rds.amazonaws.com -U adminuser -d db1 -c "INSERT INTO users (id, name, email, created_at) VALUES (1, 'John Smith', 'john@example.com', NOW());"
```

### Create a snapshot

In the AWS console, create a snapshot of the DB instance: RDS > Snapshots: `Take snapshot`.

### Run lambda function

Lambda > Functions > export_rds_snapshot_to_s3 : `Test`

### Wait...

Wait a few minutes and check the content of the bucket.
