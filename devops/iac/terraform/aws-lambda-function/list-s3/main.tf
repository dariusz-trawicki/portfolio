module "Lambda" {
  source               = "./modules/Lambda"
  lambda_function_name = var.lambda_function_name
  source_function_file_name = var.source_function_file_name
  source_function_name = var.source_function_name
  role_name            = var.role_name
  policy_name          = var.policy_name
}
