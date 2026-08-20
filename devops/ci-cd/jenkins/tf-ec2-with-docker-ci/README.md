## EC2: Jenkins CI for React App Docker Image

Project use the `Terraform` to launch the `EC2 instance`. It use a script as `userdata` for the installation of `Jenkins`, `Trivy` and `Docker`. Triggered Jenkins `pipeline` builds a `Docker image` of the `React app` example and pushes it to `Docker Hub`.

### Step 1. Create EC2 instance

Update the parameters in `terraform.tfvars` with your own AWS details:
- `server_name` – a custom name for your server (e.g., `jenkins-server`)
- `vpc_id` – the ID of your existing VPC in AWS (e.g., `vpc-0123456789abcdef0`)
- `ami` – the ID of the `Amazon Machine Image` you want to use (e.g., `ami-0a72753edf3e631b7`)
- `key_pair` – the name of your existing EC2 key pair for `SSH access`
- `subnet_id` – the ID of the subnet in which the server will be launched (e.g., `subnet-0123456789abcdef0`)

On the `localhost` run:

```bash
terraform init
terraform plan
terraform apply
# *** output (example) ***
# ec2_public_ip = "52.59.138.177"
```

## Step 2: Build the Docker image with a React app example (application code from GitHub)

Open: `AWS >  EC2 > Instances` - check the server and click `Connect` and run:

```bash
git clone https://github.com/dariusz-trawicki/react-app-example
cd react-app-example
ls
docker build -t react-app-example .
docker images
# *** output ***
# REPOSITORY   TAG             IMAGE ID        CREATED        SIZE
# react-app-example       latest          af9d40175e3d   3 minutes ago   461MB

docker run -d -p 3000:3000 --name react-app-example react-app-example
```

Open: `http://52.59.138.177:3000`


## Step 3: Access Jenkins at port 8080 and install required plugins

Open: `http://52.59.138.177:8080`

### Jenkins- initial password

In `EC2 CLI`, run:

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
# f42154e4c3db4ea9a067511129850397
# OR:
sudo systemctl status jenkins
# *** output ***
# f42154e4c3db4ea9a067511129850397
```

Open: `http://52.59.138.177:8080/manage/pluginManager/available`

Install the following `plugins`:

1. NodeJS 
2. Eclipse Temurin Installer
3. OWASP Dependency Check
4. Docker
5. Docker Commons
6. Docker Pipeline
7. Docker API
8. docker-build-step

## Step 4: Set up OWASP Dependency Check 

1. Go to `Manage Jenkins > Tools` -> `Dependency-Check Installations`
-> Click `Add` and set:
- Name: `OWASP DP-Check`
- check: `Install automatically`
    - from the `Add instalator` list choose: `Install from github.com`
...and do the Step 5 (on the same page):

## Step 5: Set up Docker for Jenkins

1. Go to `Manage Jenkins > Tools` -> `Docker Installations` 
-> Click `Add` and set:
- Name: `docker`
- check: `Install automatically`
    - from the `Add instalator` list choose: `Install from docker.com`

Click `SAVE`.

2. For the docker registry (must have: an account on `Dockerhub`) -  go to `Manage Jenkins > Credentials > System > Global Credentials -> Add redentials`: Set:
- kind: `Add username and password`
- username: `DOCKERHUB_ACCOUNT_NAME` # replace with real
- password: `PASSWORD`  # replace with real
- ID: `docker-cred`

## Step 6: Create a pipeline in order to build and push the dockerized image securely using multiple security tools

Go to `Dashboard > New Item` -> set Name: e.g. `ReactProject` and choose `Pipeline` and presas `OK`. 
Choose: `Discard old builds` and set:
- Keep # of builds to keep: 2

Use the code below for the `Jenkins pipeline` (`Script` field).

**NOTE**: Replace `DOCKERHUB_ACCOUNT_NAME` with the real account name.

```bash
pipeline {
    agent any
    stages {
        stage('clean workspace') {
            steps {
                cleanWs()
            }
        }
        stage('Checkout from Git') {
            steps {
                git branch: 'main', url: 'https://github.com/dariusz-trawicki/react-app-example'
            }
        }
        stage('OWASP FS SCAN') {
            steps {
                dependencyCheck additionalArguments: '--scan ./ --disableYarnAudit --disableNodeAudit', odcInstallation: 'OWASP DP-Check'
                dependencyCheckPublisher pattern: '**/dependency-check-report.xml'
            }
        }
        stage('TRIVY FS SCAN') {
            steps {
                script {
                    try {
                        sh "trivy fs . > trivyfs.txt" 
                    }catch(Exception e){
                        input(message: "Are you sure to proceed?", ok: "Proceed")
                    }
                }
            }
        }
        stage("Docker Build Image"){
            steps{
                   
                sh "docker build -t react-app-example ."
            }
        }
        stage("TRIVY"){
            steps{
                sh "trivy image react-app-example > trivyimage.txt"
                script{
                    input(message: "Are you sure to proceed?", ok: "Proceed")
                }
            }
        }
        stage("Docker Push"){
            steps{
                script {
                    withDockerRegistry(credentialsId: 'docker-cred', toolName: 'docker'){   
                    sh "docker tag react-app-example DOCKERHUB_ACCOUNT_NAME/react-app-example:latest"
                    sh "docker push DOCKERHUB_ACCOUNT_NAME/react-app-example:latest"
                    }
                }
            }
        }
    }
}
```

Press `SAVE` button.

### Run the pipeline

From the left menu choose `Build Now` link. The pipeline build and push the image to `Docker Hub`.