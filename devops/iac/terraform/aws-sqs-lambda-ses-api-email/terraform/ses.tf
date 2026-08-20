#############################
# Domain in Amazon SES
#############################

resource "aws_ses_domain_identity" "domain" {
  domain = var.domain #"dartit.pl"
}

#############################
# DKIM for the domain
#############################

resource "aws_ses_domain_dkim" "domain" {
  domain = aws_ses_domain_identity.domain.domain
}

################################################
# Outputs to configure in your DNS provider
################################################

# TXT record for domain verification
output "ses_verification_txt_name" {
  value = "_amazonses.${aws_ses_domain_identity.domain.domain}"
}

output "ses_verification_txt_value" {
  value = aws_ses_domain_identity.domain.verification_token
}

# 3 DKIM CNAME records
output "ses_dkim_records" {
  value = [
    for token in aws_ses_domain_dkim.domain.dkim_tokens :
    {
      name  = "${token}._domainkey.${aws_ses_domain_identity.domain.domain}"
      type  = "CNAME"
      value = "${token}.dkim.amazonses.com"
    }
  ]
}