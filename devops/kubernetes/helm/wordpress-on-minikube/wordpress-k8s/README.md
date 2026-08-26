# Deploy WordPress on Minikube with Helm

### RUN

```bash
cd wordpress-k8s

# (optional, if you want a clean start)
minikube delete

# start with reasonable resources
minikube start --cpus=4 --memory=8192

# enable addons: storage + ingress
minikube addons enable storage-provisioner
minikube addons enable default-storageclass
minikube addons enable ingress

# verify the default StorageClass is 'standard'
kubectl get sc
# Output:
# NAME                 PROVISIONER                RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
# standard (default)   k8s.io/minikube-hostpath   Delete          Immediate           false                  59s

# from folder wordpress-k8s run test/check:
helm lint wordpress-chart
# Output:
# ==> Linting wordpress-chart
# [INFO] Chart.yaml: icon is recommended
# 1 chart(s) linted, 0 chart(s) failed

# check/test templates:
helm template wordpress-chart/

# RUN: Deploy code
# wp - name of the release
# wp-ns - name of the namespace 
helm install wp wordpress-chart -n wp-ns --create-namespace
# Output example:
# NAME: wp
# LAST DEPLOYED: Wed Sep 17 10:25:53 2025
# NAMESPACE: wp-ns
# STATUS: deployed
# REVISION: 1
# TEST SUITE: None
# NOTES:
# 1. Get the application URL by running these commands:
#   http://wordpress.example.com/

# List Helm releases in the wp-ns namespace
helm list -n wp-ns
# Output example:
# NAME    NAMESPACE       REVISION        UPDATED                                 STATUS          CHART           APP VERSION
# wp      wp-ns           1               2025-09-17 09:44:31.169021 +0200 CEST   deployed        wordpress-0.1.1 1.0.0    

# Quick health snapshot of the namespace: Pods, Services, Deployments, ReplicaSets, etc.
kubectl get all -n wp-ns
# Output example:
# NAME                                      READY   STATUS    RESTARTS   AGE
# pod/wp-wordpress-76745fddfd-2vnwq         1/1     Running   0          3m7s
# pod/wp-wordpress-mysql-5d59cc4bb4-xzrln   1/1     Running   0          3m7s

# NAME                         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
# service/wp-wordpress         ClusterIP   10.111.99.160   <none>        80/TCP     3m9s
# service/wp-wordpress-mysql   ClusterIP   None            <none>        3306/TCP   3m9s

# NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/wp-wordpress         1/1     1            1           3m9s
# deployment.apps/wp-wordpress-mysql   1/1     1            1           3m9s

# NAME                                            DESIRED   CURRENT   READY   AGE
# replicaset.apps/wp-wordpress-76745fddfd         1         1         1       3m7s
# replicaset.apps/wp-wordpress-mysql-5d59cc4bb4   1         1         1       3m7s


# List Ingress objects
kubectl get ingress -n wp-ns
# Output example:
# NAME                   CLASS   HOSTS                 ADDRESS        PORTS   AGE
# wp-wordpress-ingress   nginx   wordpress.example.com   192.168.49.2   80      15m

# NOTE:
minikube ip
# Output example:
# 192.168.49.2

# Enable the NGINX Ingress Controller addon in Minikube
minikube addons enable ingress

# Set the Service type to LoadBalancer
kubectl -n ingress-nginx patch svc ingress-nginx-controller \
  -p '{"spec":{"type":"LoadBalancer"}}'

# Start the tunnel (in a separate window; keep it running)
minikube tunnel

# Check the Ingress controller Service status
kubectl -n ingress-nginx get svc ingress-nginx-controller
# Output example:
# NAME                       TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)                      AGE
# ingress-nginx-controller   LoadBalancer   10.106.179.35   127.0.0.1     80:32164/TCP,443:31736/TCP   7m56s

# add an entry to /etc/hosts
sudo sh -c 'echo "127.0.0.1  wordpress.example.com" >> /etc/hosts'

# Test without a browser:
curl -i -H "Host: wordpress.example.com" http://127.0.0.1/
# Content-Type: text/html; charset=UTF-8
# Content-Length: 0
# Connection: keep-alive
# X-Powered-By: PHP/8.2.29
# Expires: Wed, 11 Jan 1984 05:00:00 GMT
# Cache-Control: no-cache, must-revalidate, max-age=0, no-store, private
# X-Redirect-By: WordPress
# Location: http://wordpress.example.com/wp-admin/install.php
```

#### Test in a browser

Open: http://wordpress.example.com/


### Clean up

```bash
# remove hosts entry (macOS syntax; adjust for Linux if needed)
sudo sed -i '' '/wordpress\.example\.com/d' /etc/hosts

# delete the cluster
minikube delete
```