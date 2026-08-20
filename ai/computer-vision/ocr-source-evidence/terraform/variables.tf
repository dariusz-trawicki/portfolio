variable "subscription_id" {
  description = "Target subscription ID. Find it with: az account list --output table"
  type        = string
}

variable "location" {
  description = "Azure region. Defaults to the EU - with sensitive documents, data residency is a requirement rather than a preference."
  type        = string
  default     = "westeurope"
}

variable "sku" {
  description = "F0 is the free tier (500 pages/month). S0 is pay-as-you-go with no page cap."
  type        = string
  default     = "F0"
}
