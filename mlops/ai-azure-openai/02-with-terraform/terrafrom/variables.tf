variable "resource_group_name" {
  default = "rg-openai-demo"
}

variable "location" {
  default = "swedencentral"
}

variable "cognitive_account_name" {
  default = "test-ai-tf"
}

variable "deployment_name" {
  default = "gpt-4-mini"
}

variable "model_name" {
  default = "gpt-4o-mini"
}

variable "model_version" {
  default = "2024-07-18"
}

variable "capacity" {
  default = 30
}
