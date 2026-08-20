output "web_instance_id" { value = module.compute.instance_id }
output "vpc_id" { value = module.network.vpc_id }
output "subnet_id" { value = module.network.public_subnet_id }
