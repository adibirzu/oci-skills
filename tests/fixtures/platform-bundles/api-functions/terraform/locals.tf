locals {
  project_name = "fixture-api-functions"
  common_tags = {
    managed-by = "terraform"
    project    = local.project_name
  }
}
