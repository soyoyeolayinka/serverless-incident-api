variable "aws_region" {
  type    = string
  default = "eu-west-1"
}
variable "project_name" {
  type    = string
  default = "serverless-incident-api"
}
variable "tags" {
  type = map(string)
  default = { Project = "serverless-incident-api", ManagedBy = "Terraform", Environment = "portfolio" }
}
