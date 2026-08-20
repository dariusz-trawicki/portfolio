# Kubernetes: Run containerized Java Web Application with Tomcat, MySQL, Memcached, and RabbitMQ on K8s - EKS (AWS)

This example demonstrates running a Java web application on EKS. The application is built and deployed with `Maven` on a `Tomcat` server, and relies on `MySQL`, `Memcached`, and `RabbitMQ`. An `Nginx` container acts as the web frontend.

#### Goal of the Task

The goal is to deploy a complete multi-tier application on Kubernetes (`EKS`) with `persistent storage`, `networking`, and external access.

Key objectives:
- Use Kubernetes manifests for:
  - Deployments (`DB`, `Tomcat app`, `Memcache`, `RabbitMQ`),
  - Services for internal communication,
  - `Ingress` (`NGINX`) for external access.
- Configure `persistent storage` using `AWS EBS` and a proper `StorageClass` (gp3).
- Set up readiness and liveness probes and use initContainers to guarantee service dependencies (`DB`, `Memcache`) are ready before the app starts.
- Integrate with `AWS Application Load Balancer` through `Ingress`.


#### Application Architecture on Kubernetes with AWS EKS

```text
Application Load Balancer
    ↓
Ingress
    ↓
TomcatService → Tomcat Pod
    ├── RMQService → RabbitMQ Pod → Secret
    ├── MCService → Memcache Pod
    └── DBService → DB Pod
                       ├── Secret (password DB)
                       ├── PVC → StorageClass → Amazon EBS
                       └── mount: /var/lib/mysql
```

#### Step 1. Terraform - create ESK cluster

1. Create an S3 Bucket for the Backend

```bash
cd terraform/s3-backend
terraform init
terraform validate
terraform plan
terraform apply
```

2. Create the EKS cluster

```bash
cd ../eks
terraform init
terraform validate
terraform plan
terraform apply
```

3. Point `kubectl` to the `EKS cluster`

```bash
aws eks --region eu-central-1 update-kubeconfig --name vproapp-cluster
# Test:
kubectl get nodes
# *** output (exapmle) ***
# NAME                                            STATUS   ROLES    AGE     VERSION
# ip-172-20-2-240.eu-central-1.compute.internal   Ready    <none>   152m   v1.28.15-eks-3abbec1
# ip-172-20-2-6.eu-central-1.compute.internal     Ready    <none>   120m   v1.28.15-eks-3abbec1
# ip-172-20-3-11.eu-central-1.compute.internal    Ready    <none>   152m   v1.28.15-eks-3abbec1
```

#### Step 2. Deploy App on K8s Cluster

1. Deploy the NGINX Ingress Controller

```bash
kubectl apply -n ingress-nginx -f \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.1/deploy/static/provider/cloud/deploy.yaml
```


2. Deploy the manifests

Deploy the Kubernetes manifests for:
  - Deployments (`DB`, `Tomcat app`, `Memcache`, `RabbitMQ`),
  - `Services` for internal communication,
  - Configure `persistent storage` using `AWS EBS` and a proper `StorageClass` (`gp3`).
  - Set up readiness and liveness probes and use initContainers to guarantee service dependencies (`DB`, `Memcache`) are ready before the app starts.

```bash
cd ../../kubedefs
kubectl apply -f .

# Tests:
kubectl get pods
# *** output (exapmle) ***
# NAME                        READY   STATUS    RESTARTS      AGE
# vproapp-6dbbc968c9-zhh4k    1/1     Running   0             77s
# vprodb-7cb6cfdc6c-bl8f5     1/1     Running   1 (50s ago)   77s
# vpromc-66c7f7d974-k5zmb     1/1     Running   0             77s
# vpromq01-5f78db7574-kfpdp   1/1     Running   0             76s

kubectl get deploy
# *** output ***
# NAME       READY   UP-TO-DATE   AVAILABLE   AGE
# vproapp    1/1     1            1           2m28s
# vprodb     1/1     1            1           2m28s
# vpromc     1/1     1            1           2m28s
# vpromq01   1/1     1            1           2m27s

kubectl get svc
# *** output ***
# NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)     AGE
# kubernetes        ClusterIP   10.100.0.1       <none>        443/TCP     166m
# vproapp-service   ClusterIP   10.100.162.218   <none>        8080/TCP    3m8s
# vprocache01       ClusterIP   10.100.13.10     <none>        11211/TCP   3m8s
# vprodb            ClusterIP   10.100.76.240    <none>        3306/TCP    3m8s
# vpromq01          ClusterIP   10.100.93.173    <none>        5672/TCP    3m7s


kubectl describe svc vproapp-service
# *** output (exapmle) ***
# Name:                     vproapp-service
# Namespace:                default
# Labels:                   <none>
# Annotations:              <none>
# Selector:                 app=vproapp
# Type:                     ClusterIP
# IP Family Policy:         SingleStack
# IP Families:              IPv4
# IP:                       10.100.162.218
# IPs:                      10.100.162.218
# Port:                     <unset>  8080/TCP
# TargetPort:               8080/TCP
# Endpoints:                172.20.3.87:8080
# Session Affinity:         None
# Internal Traffic Policy:  Cluster
# Events:                   <none>

kubectl get pvc
# *** output (exapmle) ***
# NAME          STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
# db-pv-claim   Bound    pvc-7bc0aec0-938b-4bf1-8cb5-773d17c895e2   3Gi        RWO            gp3            11m

kubectl get ingress
# *** output (exapmle) ***
# NAME           CLASS   HOSTS                ADDRESS                                                                    PORTS   AGE
# vpro-ingress   nginx   vprofile.dartit.pl   a9db2bc26a35a420aa0f11121074b562-44694593.eu-central-1.elb.amazonaws.com   80      24m

kubectl describe ingress vpro-ingress
# *** output (exapmle) ***
# Name:             vpro-ingress
# Labels:           <none>
# Namespace:        default
# Address:          a9db2bc26a35a420aa0f11121074b562-44694593.eu-central-1.elb.amazonaws.com
# Ingress Class:    nginx
# Default backend:  <default>
# Rules:
#   Host                Path  Backends
#   ----                ----  --------
#   vprofile.dartit.pl  
#                       /   vproapp-service:8080 (172.20.3.87:8080)
# Annotations:          nginx.ingress.kubernetes.io/use-regex: true
# Events:
#   Type    Reason  Age                From                      Message
#   ----    ------  ----               ----                      -------
#   Normal  Sync    24m (x2 over 25m)  nginx-ingress-controller  Scheduled for sync
```

#### Step 3. Add DNS record

Add DNS record:
- Name: vprofile.xxxxx.com
- Type: CNAME
- Value: a9db2bc26a35a420aa0f11121074b562-44694593.eu-central-1.elb.amazonaws.com

Visit: `http://vprofile.xxxxx.com`


#### Step 4. Cleanup

```bash
kubectl delete -n ingress-nginx -f \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.1/deploy/static/provider/cloud/deploy.yaml


kubectl delete -f .

# destroy EKS cluster
cd ../terraform/eks
terraform destroy

# destroy s3-backend
cd ../s3-backend
terraform destroy
```