## Mobile Price Classification Project using Amazon SageMaker (AWS)

Mobile price classification model: given a phone’s specs (battery capacity, RAM, screen size, pixel dimensions, cameras, connectivity flags, etc.), the model predicts which price range bucket


### Terraform

#### Create infra in AWS: S3 and iam role

In `terraform/variables.tf`, set a unique name for the S3 bucket.

```bash
cd terraform
terraform init
terraform apply
# Example output:
# s3_bucket_name = "dartit-sagemaker-123"
# sagemaker_iam_role_arn = "arn:aws:iam::123456789:role/sagemakeraccess"
```

### Python

In `research.ipynb`, set the `bucket name` (`BUCKET` variable) and the `iam role arn` (`IAM_ROLE_ARN` variable).

```bash
# Create env
cd ..
conda create -p ./venv python=3.10 -y
conda activate ./venv
pip install -r requirements.txt

# Run research.ipynb
jupyter notebook
```


#### CLEAN UP ####
```bash
conda deactivate
conda remove -p ./venv --all

cd terraform
terraform destroy
```

