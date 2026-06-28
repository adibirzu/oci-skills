locals {
  project_name = "fixture-container-instances"
  common_tags = {
    managed-by = "terraform"
    project    = local.project_name
  }
}
