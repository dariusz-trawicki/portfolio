variable "region" {
  description = "AWS region (Bedrock supported)"
  type        = string
  default     = "us-east-1" # in eu-central-1 Bedrock is not yet supported
}

variable "model_id" {
  description = "Bedrock foundation model ID"
  type        = string
  default     = "meta.llama3-70b-instruct-v1:0"
}
