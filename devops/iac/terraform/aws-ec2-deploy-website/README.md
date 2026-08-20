# Terraform: Automated Website Deployment on AWS EC2 (Apache + Tooplate)

**Variant 01** — `SSH provisioners` (`file` + `remote-exec`): `Terraform` uploads a script and executes it over `SSH` after the instance is up.

**Variant 02** — `Cloud-Init` (`user_data`): All `bootstrap` steps run on first boot via `EC2` user data.

