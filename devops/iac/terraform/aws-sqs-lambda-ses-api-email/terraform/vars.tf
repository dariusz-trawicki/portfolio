variable "region" {
  description = "AWS region to deploy resources in"
  type        = string
  default     = "eu-central-1"
}

variable "domain" {
  description = "Domain name to verify in SES"
  type        = string
  default     = "dartit.pl"
}

variable "sender_address" {
  description = "Sender email address (must be verified in SES)"
  type        = string
  default     = "dariusz.trawicki@dartit.pl"
}
