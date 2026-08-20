# WordPress on GKE + Cloud SQL + HTTPS

Complete Terraform-based deployment of WordPress on Google Cloud with a managed HTTPS certificate on your own domain. Everything is described in Terraform — one config file, two `terraform apply` runs, and you have a working site on `https://your-domain.com`.

## What you get

- Kubernetes cluster (GKE) with Workload Identity enabled
- Managed MySQL database (Cloud SQL) with the SQL Auth Proxy as a sidecar
- Persistent storage for `wp-content` (themes, plugins, uploads)
- Public HTTPS Load Balancer with a free Google-managed certificate
- Static IP that you point your domain to
- WordPress with `WP_HOME` properly configured and TLS termination handled at the LB

The whole thing takes **~15–20 minutes** + an additional **15–60 minutes** for certificate provisioning in Stage 2.

## Prerequisites

You need these installed locally:

- **Terraform** 1.0 or newer — check with `terraform -version`
- **gcloud CLI** — check with `gcloud version`
- **kubectl** — useful for cluster diagnostics
- **`gke-gcloud-auth-plugin`**:
```bash
  gcloud components install gke-gcloud-auth-plugin
```

You also need:

- A **GCP project** with billing enabled and the Owner role (or equivalent admin roles)
- A **registered domain** (any registrar — Namecheap, Cloudflare, GoDaddy, etc.) with access to the DNS panel

## Architecture

The deployment runs as a single-replica WordPress Pod with:
- WordPress container with a PVC mounted at `/var/www/html/wp-content`
- Cloud SQL Auth Proxy as a sidecar container, connecting to a private Cloud SQL instance
- Workload Identity binding a Kubernetes ServiceAccount to a GCP ServiceAccount with `cloudsql.client`
- A Google-managed certificate attached to a GCE Ingress with a static global IP

## Deployment procedure

The demo requires **two `terraform apply` runs**:
1. First creates the cluster and base infrastructure (HTTP only)
2. Second adds HTTPS resources (run *after* you've configured DNS records)

### Step 0 — authenticate with GCP

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR-PROJECT-ID
```

`application-default login` saves credentials to `~/.config/gcloud/application_default_credentials.json`. Terraform picks them up automatically.

### Step 1 — prepare the config file

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Open `terraform.tfvars` in your editor and set:

```hcl
project_id    = "your-gcp-project"
sql_user_name = "wordpress"

region        = "<your-gcp-region>"
zone          = "<your-gcp-zone>"

# IMPORTANT: keep this `false` for the first apply
enable_https      = false
wordpress_domains = ["your-domain.com", "www.your-domain.com"]
```

> **Why `enable_https = false` initially?** The HTTPS resources include a `kubernetes_manifest` (the managed certificate) which needs the cluster to exist at plan time. Enabling HTTPS on the first apply causes a "no client config" error.

### Step 2 — first `terraform apply` (base infrastructure)

```bash
terraform init
terraform apply
```

Wait ~10–15 minutes. The sequence you'll observe:

1. Enabling GCP APIs — seconds
2. Creating service accounts — seconds
3. **Cloud SQL instance** — ~5–10 minutes (slowest)
4. **GKE cluster and node pool** — ~3–5 minutes (in parallel)
5. Kubernetes resources (KSA, secret, PVC, deployment, service) — ~1 minute
6. **L4 LoadBalancer** — final ~2 minutes

Example output:
```
generated_sql_password = <sensitive>
loadbalancer_ip = "34.116.144.248"
next_steps = <<EOT
Stage 1 deployed. Next:
  1. Configure DNS A records pointing to 8.233.224.240:
     your-domain.com, www.your-domain.com
  2. Verify with: dig your-domain.com
  3. Set enable_https=true in terraform.tfvars and run: terraform apply
EOT
static_ip = "8.233.224.240"
```

**Save the `static_ip` value** — you need it for the next step.

Get kubectl credentials for the cluster:

```bash
gcloud container clusters get-credentials wordpress-cluster \
    --zone europe-central2-a \
    --project YOUR-PROJECT-ID
```

Optional HTTP sanity check (no cert yet):

```bash
curl -I http://<loadbalancer_ip>
# HTTP/1.1 302 Found
# Location: http://<loadbalancer_ip>/wp-admin/install.php
```

### Step 3 — configure DNS at your registrar

This is done in your registrar's panel, not in Terraform.

1. Log in to your registrar's DNS panel
2. Disable any "domain forwarding" if it was set
3. Remove old A and CNAME records that point elsewhere
4. Add two **A** records pointing to the static IP from Step 2:

   | Host              | Type | Value             | TTL  |
   |-------------------|------|-------------------|------|
   | your-domain.com   | A    | `<STATIC_IP>`     | 3600 |
   | www.your-domain.com | A  | `<STATIC_IP>`     | 3600 |

5. **CAA record (important if your registrar injects its own CAA records).**
   Some registrars (e.g. `nazwa.pl`) inject CAA records permitting only their partner CAs (Let's Encrypt, Certum). Google's managed certs use `pki.goog`, which won't be allowed unless you add it explicitly:

   | Host              | Type | Value                  | TTL  |
   |-------------------|------|------------------------|------|
   | your-domain.com   | CAA  | `0 issue "pki.goog"`   | 3600 |

6. **Best practice**: remove the wildcard record (`*.your-domain.com`) and use an explicit `www` A record instead.

Save the changes and wait for DNS propagation. **Usually 10–30 minutes**, in rare cases up to 24 hours.

Verify with `dig`:

```bash
dig your-domain.com
# Output example:
# ...
# ;; ANSWER SECTION:
# your-domain.com.        3599    IN      A       8.233.224.240
#...

dig www.your-domain.com

# Check from public resolvers — this is what Google will see during cert validation
dig @8.8.8.8 your-domain.com +short
dig @1.1.1.1 your-domain.com +short
dig @8.8.8.8 www.your-domain.com +short
# 8.233.224.240
# 8.233.224.240
# 8.233.224.240
```

If you don't see your static IP in the `ANSWER SECTION` — DNS hasn't propagated yet, wait longer.

Verify the CAA record (if your registrar adds its own):

```bash
dig @8.8.8.8 your-domain.com CAA +short
# Look for: 0 issue "pki.goog"
```

### Step 4 — second `terraform apply` (enable HTTPS)

Once DNS points to your static IP, change `terraform.tfvars`:

```hcl
enable_https = true
```

Then:

```bash
terraform apply
```

The apply log will show:
- 2 new resources added: `kubernetes_manifest.wordpress_cert` (certificate) and `kubernetes_ingress_v1.wordpress` (Ingress = HTTPS Load Balancer)
- 2 existing resources changed: the Service (from `LoadBalancer` to `NodePort`) and the Deployment (adding `WORDPRESS_CONFIG_EXTRA` env)

Takes ~2–3 minutes.

> **Note:** after this step, the old site on `loadbalancer_ip` stops working — that's expected. The L4 LB is being removed, the HTTPS LB is being created.

Expected output:
```
next_steps = <<EOT
HTTPS enabled. Wait 15-60 min for cert provisioning.
Monitor: kubectl describe managedcertificate wordpress-cert
Then open: https://your-domain.com
EOT
static_ip = "8.233.224.240"
```

### Step 5 — wait for the certificate

Google has to:

1. Create the HTTPS Load Balancer (~2–5 min)
2. Verify you actually own the domain (HTTP-01 challenge, ~5–15 min)
3. Issue and install the certificate (~5–30 min)

Total typically **15–60 minutes**.

Wait a few minutes, then check that the backend is HEALTHY:

```bash
kubectl get ingress wordpress-ingress \
  -o jsonpath='{.metadata.annotations.ingress\.kubernetes\.io/backends}'; echo

# {"k8s-be-30633--62aba77615906961":"HEALTHY"}
```

If empty — wait and retry.

Verify the health check is configured correctly (insert the backend name from above):

```bash
HC=$(gcloud compute backend-services describe k8s-be-30633--62aba77615906961 \
  --global --format='value(healthChecks)' | sed 's|.*/||')

gcloud compute health-checks describe $HC \
  --format='value(httpHealthCheck.requestPath,httpHealthCheck.port)'

# /readme.html    31456
```

Monitor cert provisioning in a second terminal:

```bash
watch -n 30 '
  kubectl get managedcertificate wordpress-cert
  echo
  kubectl get managedcertificate wordpress-cert -o jsonpath="{range .status.domainStatus[*]}{.domain}{\"\\t\"}{.status}{\"\\n\"}{end}"
'
```

Status transitions:
```
Provisioning → Active             ✅  ready, working
Provisioning → FailedNotVisible   ❌  DNS not pointing to the IP, fix records
```

When done you'll see:
```
NAME             AGE   STATUS
wordpress-cert   30m   Active

your-domain.com       Active
www.your-domain.com   Active
```

Or with the alternative command:
```bash
watch -n 30 'kubectl describe managedcertificate wordpress-cert | tail -15'
# Status:
#   Certificate Name:    mcrt-c7188ca1-5e94-48c5-93bc-2a3832bc780f
#   Certificate Status:  Active
#   Domain Status:
#     Domain:     your-domain.com
#     Status:     Active
#     Domain:     www.your-domain.com
#     Status:     Active
```

### Step 6 — verify

```bash
open https://your-domain.com   # WordPress should open

curl -vI https://your-domain.com 2>&1 | grep -E "subject|issuer|HTTP"
# *  subject: CN=your-domain.com
# *  subjectAltName: host "your-domain.com" matched cert's "your-domain.com"
# *  issuer: C=US; O=Google Trust Services; CN=WR3
# * using HTTP/2
# > HEAD / HTTP/2
# < HTTP/2 302
```

Done — HTTPS works.

## Troubleshooting

### Cert stuck in `FailedNotVisible`

DNS is not visible to Google's resolver yet, or CAA records block `pki.goog`. Verify:

```bash
dig @8.8.8.8 your-domain.com +short
dig @8.8.8.8 your-domain.com CAA +short
```

If CAA records exist and don't include `pki.goog`, add one (see Step 3).

If DNS looks fine but the cert is still failing, force a recreate:

```bash
kubectl delete managedcertificate wordpress-cert
terraform apply
```

### Cert stuck in `Provisioning` for > 60 minutes

Check that the backend is `HEALTHY`:

```bash
kubectl get ingress wordpress-ingress \
  -o jsonpath='{.metadata.annotations.ingress\.kubernetes\.io/backends}'; echo
```

If `UNHEALTHY`, check the health check path. The Terraform code uses a `BackendConfig` pointing the health check at `/readme.html` (which WordPress serves with `200 OK`, unlike `/` which returns `302`).


## Cleanup

When you're done:

```bash
terraform destroy
```

Wait ~10–15 minutes. This removes everything: cluster, database, IP, certificate, LB, service accounts. GCP APIs stay enabled (they're free, no point disabling them).

At your registrar:
- Remove the A records and the CAA record you added
- Restore your original DNS records

If `destroy` doesn't finish cleanly, check manually that nothing expensive is left:

```bash
gcloud container clusters list --project YOUR-PROJECT-ID
gcloud sql instances list --project YOUR-PROJECT-ID
gcloud compute disks list --project YOUR-PROJECT-ID
gcloud compute forwarding-rules list --project YOUR-PROJECT-ID
gcloud compute addresses list --project YOUR-PROJECT-ID
```

Each should return `Listed 0 items.`. If something remains, delete it with `gcloud ... delete`.

## Cost estimate

Rough monthly cost with default settings:

| Resource                                  | Cost (USD/mo) |
|-------------------------------------------|---------------|
| GKE node (`n1-standard-1`)                | ~25           |
| Cloud SQL (`db-f1-micro`)                 | ~8            |
| HTTPS Load Balancer + static IP           | ~18           |
| Disks (boot + PVC)                        | ~2            |
| Google-managed certificate                | **0** ✅      |
| Domain (registrar, separate)              | ~10–25/year   |
| **Total**                                 | **~50–55**    |

For lab/test use, `terraform destroy` after each session brings the cost to zero.
