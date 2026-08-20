# Deploying Spark on Kubernetes (Minikube) example

This example based on Ganesh Walavalkar’s post
(https://wganesh.medium.com/spark-on-minikube-d577e92539be)

## Start the cluster:

```bash
minikube start --memory 8192 --cpus 4
```

## Build the Docker image:

```bash
docker build -f docker/Dockerfile -t spark-hadoop:3.2.0 ./docker
```

OR copy the `image` form `DockerHub`:

```bash
docker pull mjhea0/spark-hadoop:3.2.0
# change the name to spark-hadoop:3.2.0 (as used in the example [in the *.yaml files])
docker tag mjhea0/spark-hadoop:3.2.0 spark-hadoop:3.2.0
```

## Load the image into Minikube:

```bash
minikube image load spark-hadoop:3.2.0
```

## Create the deployments and services:

```bash
kubectl apply -f ./kubernetes/spark-master-deployment.yaml
kubectl apply -f ./kubernetes/spark-master-service.yaml
sleep 10
kubectl apply -f ./kubernetes/spark-worker-deployment.yaml

kubectl get deployments
# *** Output example ***
# NAME           READY   UP-TO-DATE   AVAILABLE   AGE
# spark-master   1/1     1            1           4h44m
# spark-worker   2/2     2            2           4h43m

kubectl get pods
# *** Output example ***
# NAME                            READY   STATUS    RESTARTS   AGE
# spark-master-5b75d56678-npgrf   1/1     Running   0          4h44m
# spark-worker-899c4d88b-ghklm    1/1     Running   0          4h43m
# spark-worker-899c4d88b-krx9l    1/1     Running   0          4h43m

minikube addons enable ingress
kubectl apply -f ./kubernetes/minikube-ingress.yaml

kubectl get pods -n ingress-nginx
# *** Output example ***
# NAME                                        READY   STATUS      RESTARTS   AGE
# ingress-nginx-admission-create-xmvk7        0/1     Completed   0          2m23s
# ingress-nginx-admission-patch-nkq8c         0/1     Completed   0          2m23s
# ingress-nginx-controller-56d7c84fd4-hp6mh   1/1     Running     0          2m23s
```

## Add an entry to `/etc/hosts`:

```bash
echo "127.0.0.1 spark-kubernetes" | sudo tee -a /etc/hosts
cat /etc/hosts | grep spark-kubernetes
```

## Minikube tunnel

NOTE:
Here `Docker` is used as the driver, so Minikube ip returns the IP of the `Docker container`, which does not have direct access to host machine ports.
To access port 80 of the Minikube cluster, a `tunnel` must be used:

```bash
# run in diffrent terminal:
minikube tunnel
# *** output *** 
# Password: # put admin pass (for "sudo ...")
```

## Tests

### In the browser 

Open [http://spark-kubernetes/](http://spark-kubernetes/).

### Minikube dashboard

To open `minikube dashboard` run:

```bash
minikube dashboard
```

### PySpark shell test

To test, run the `PySpark shell` from the the `master container`:

```bash
kubectl get pods -o wide
# *** Output example ***
# NAME                            READY   STATUS    RESTARTS      AGE   IP           NODE       NOMINATED NODE   READINESS GATES
# spark-master-54c69fd6cb-rwjrc   1/1     Running   1 (28m ago)   28m   10.244.0.3   minikube   <none>           <none>
# spark-worker-7f7d764684-662lb   1/1     Running   0             28m   10.244.0.5   minikube   <none>           <none>
# spark-worker-7f7d764684-wm6bf   1/1     Running   0             28m   10.244.0.4   minikube   <none>           <none>

# NOTE: In the command below, use your own parameters:
kubectl exec spark-master-54c69fd6cb-rwjrc -it -- \
    pyspark --conf spark.driver.bindAddress=10.244.0.3 --conf spark.driver.host=10.244.0.3
```

Run the following code after the `PySpark prompt` appears, type the following commands:

```bash
>>> words = 'the quick brown fox jumps over the lazy dog the quick brown fox jumps over the lazy dog'
>>> sc = SparkContext.getOrCreate()
>>> seq = words.split()
>>> data = sc.parallelize(seq)
>>> counts = data.map(lambda word: (word, 1)).reduceByKey(lambda a, b: a + b).collect()
>>> dict(counts)                                                                
# {'quick': 2, 'the': 4, 'brown': 2, 'fox': 2, 'jumps': 2, 'over': 2, 'lazy': 2, 'dog': 2}
>>> sc.stop()
>>> quit()
```

## Cleaning

```bash
./delete.sh
```
