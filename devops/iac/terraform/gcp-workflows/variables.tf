variable "project_name" {
  type    = string
  default = "sub-workflows-exp"
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "instance_name" {
  type    = string
  default = "main"
}


variable "db_version" {
  type    = string
  default = "POSTGRES_14"
}

variable "dbs" {
  description = "List of database names"
  type        = list(string)
  default     = ["db1", "db2", "db3"]
}

variable "users" {
  description = "List of user definitions (name, password)"
  type = list(object({
    name     = string
    password = string
  }))
  default = [
    {
      name     = "user1"
      password = "password1"
    },
    {
      name     = "user2"
      password = "password2"
    },
    {
      name     = "user3"
      password = "password3"
    }
  ]
}

variable "tier" {
  type    = string
  default = "db-f1-micro"
}

variable "workflow_name" {
  type    = string
  default = "workflow"
}

