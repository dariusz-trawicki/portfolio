terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-central-1"
}

#############################
# 1. Domain in Amazon SES
#############################

resource "aws_ses_domain_identity" "dartit" {
  domain = "dartit.pl"
}

#############################
# 2. DKIM for the domain
#############################

resource "aws_ses_domain_dkim" "dartit" {
  domain = aws_ses_domain_identity.dartit.domain
}

################################################
# 3. Outputs to configure in your DNS provider
################################################

# TXT record for domain verification
output "ses_verification_txt_name" {
  value = "_amazonses.${aws_ses_domain_identity.dartit.domain}"
}

output "ses_verification_txt_value" {
  value = aws_ses_domain_identity.dartit.verification_token
}

# 3 DKIM CNAME records
output "ses_dkim_records" {
  value = [
    for token in aws_ses_domain_dkim.dartit.dkim_tokens :
    {
      name  = "${token}._domainkey.${aws_ses_domain_identity.dartit.domain}"
      type  = "CNAME"
      value = "${token}.dkim.amazonses.com"
    }
  ]
}
