# MLFLOW on EC2 AWS Demo (with terraform)

Demo project: 
Train and Log an ElasticNet Wine Quality Model to a Remote MLflow Server.

#### Terraform: create S3 and EC2

```bash
# create key-pair
cd terraform
terraform init
terraform apply
# Output example:
# ec2_public_dns = "ec2-3-76-126-107.eu-central-1.compute.amazonaws.com"
# ec2_public_dns = "3.76.126.107"

# Test:
ssh -i ./mlflow-key.pem ubuntu@3.76.126.107
```

#### Set Up a Python 3.12 Virtual Environment with Conda and Install Dependencies

```bash
cd ..
conda create -p venv python=3.12 -y
conda activate ./venv
pip install -r requirements.txt
```

#### Edit the Code (`app.py` and `app.ipynb`) to Set the MLflow Server URI

```python
MLFLOW_SERVER_URI = "http://ec2-3-76-126-107.eu-central-1.compute.amazonaws.com:5000/"
```

#### Run demo project

```bash
python app.py

# optional with Jupyter
python -m ipykernel install --user --name app-312 --display-name "Python 3.12 (app)"
jupyter notebook app.ipynb
```
