# AWS Lambda Function example: get list of the s3 buckets

## RUN

- CLI: list the s3 buckets (assumption: we have at least one bucket):

```bash
aws s3 ls
```

- terraform

```bash
terraform init
terraform apply
```

## Results

- Run the function in CLI:

```bash
aws lambda invoke --function-name get_s3_buckets_function response.json`
```

- The above command returns:

```json
{
    "StatusCode": 200,
    "ExecutedVersion": "$LATEST"
}
```

- In `reponse.json` file we get (for example):

```json
{"statusCode": 200, "body": "[\"aws-cloudtrail-logs-xxxxx-9afd90ca\", \"my-s3-bucket-name-xxx\"]"}
```