# AWS: ECS + FARGATE + Nginx

## RUN

```bash
terraform init
terraform apply
```


## Tests

```bash
aws ecs list-tasks --cluster fargate-cluster

# *** Output (example) ***
# {
#     "taskArns": [
#         "arn:aws:ecs:eu-central-1:253490761607:task/fargate-cluster/ffe3ac24c223446fb1c8ddecae49733b"
#     ]
# }

aws ecs describe-tasks --cluster fargate-cluster --tasks ffe3ac24c223446fb1c8ddecae49733b --query "tasks[].attachments[].details[?name=='networkInterfaceId'].value[]" --output text

# *** Output (example) ***
# eni-016b02fbb4c54a244

aws ec2 describe-network-interfaces --network-interface-ids eni-016b02fbb4c54a244 --query "NetworkInterfaces[].Association.PublicIp" --output text

# *** Output (example) ***
# 35.159.30.215

curl -I http://35.159.30.215
```

