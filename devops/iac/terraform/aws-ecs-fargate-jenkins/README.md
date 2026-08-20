# AWS: ECS + FARGATE + Jenkins

## RUN

```bash
terraform init
terraform apply
```


## Tests

```bash
aws ecs list-tasks --cluster fargate-cluster

# *** Output example ***
# {
#     "taskArns": [
#         "arn:aws:ecs:eu-central-1:253490761607:task/fargate-cluster/89bcbff9b3ba4444b6ab73b6e4e276e6"
#     ]
# }

aws ecs describe-tasks --cluster fargate-cluster --tasks 89bcbff9b3ba4444b6ab73b6e4e276e6 --query "tasks[].lastStatus" --output text

aws ecs describe-tasks --cluster fargate-cluster --tasks 89bcbff9b3ba4444b6ab73b6e4e276e6 --query "tasks[].attachments[].details[?name=='networkInterfaceId'].value[]" --output text

# *** Output example ***
# eni-0a929833a7496ef78

aws ec2 describe-network-interfaces --network-interface-ids eni-0a929833a7496ef78 --query "NetworkInterfaces[].Association.PublicIp" --output text

# *** Output example ***
# 54.93.220.26

curl -I http://54.93.220.26:8080
```
