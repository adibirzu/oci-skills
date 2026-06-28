locals {
  project_name = "__PROJECT_NAME__"
  common_tags = {
    managed-by = "terraform"
    project    = local.project_name
  }
}
