locals {
  project_name = "fixture-oke-application"
  common_tags = {
    managed-by = "terraform"
    project    = local.project_name
  }
}
