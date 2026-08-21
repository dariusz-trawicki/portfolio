variable "prefix" {
  description = "Prefix for all resources"
  type        = string
  default     = "pjm"
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "rg-pjm-ml"
}

variable "location" {
  description = "Region Azure"
  type        = string
  default     = "West Europe"
}

variable "storage_account_name" {
  description = "Storage account name"
  type        = string
  default     = "pjmmlstorage"
}
