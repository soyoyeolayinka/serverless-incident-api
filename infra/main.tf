terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
}
provider "aws" { region = var.aws_region }
data "archive_file" "lambda" {
  type = "zip"
  source_dir = "${path.module}/../src"
  output_path = "${path.module}/incident-api.zip"
}
resource "aws_dynamodb_table" "incidents" {
  name = "${var.project_name}-incidents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "incident_id"
  attribute { name = "incident_id" type = "S" }
  tags = var.tags
}
resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "lambda" {
  role = aws_iam_role.lambda.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Scan"], Resource = aws_dynamodb_table.incidents.arn },
    { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = "*" }
  ] })
}
resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-handler"
  role = aws_iam_role.lambda.arn
  filename = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  runtime = "python3.12"
  handler = "handler.lambda_handler"
  timeout = 10
  memory_size = 128
  environment { variables = { TABLE_NAME = aws_dynamodb_table.incidents.name } }
  tags = var.tags
}
resource "aws_cloudwatch_log_group" "lambda" {
  name = "/aws/lambda/${aws_lambda_function.api.function_name}"
  retention_in_days = 7
  tags = var.tags
}
resource "aws_apigatewayv2_api" "api" { name = var.project_name protocol_type = "HTTP" }
resource "aws_apigatewayv2_integration" "lambda" {
  api_id = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_uri = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}
resource "aws_apigatewayv2_route" "routes" {
  for_each = toset(["POST /incidents", "GET /incidents", "GET /incidents/{id}", "PATCH /incidents/{id}"])
  api_id = aws_apigatewayv2_api.api.id
  route_key = each.value
  target = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}
resource "aws_apigatewayv2_stage" "default" { api_id = aws_apigatewayv2_api.api.id name = "$default" auto_deploy = true }
resource "aws_lambda_permission" "api" {
  statement_id = "AllowApiGateway"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal = "apigateway.amazonaws.com"
  source_arn = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
output "api_endpoint" { value = aws_apigatewayv2_api.api.api_endpoint }
