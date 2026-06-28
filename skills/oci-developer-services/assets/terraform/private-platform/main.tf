locals {
  common_tags = {
    managed-by = "terraform"
    project    = var.project_name
  }
}

resource "oci_devops_project" "delivery" {
  compartment_id = var.compartment_id
  name           = "${var.project_name}-delivery"
  description    = "Delivery resources for ${var.project_name}"
  freeform_tags  = local.common_tags

  notification_config {
    topic_id = var.notification_topic_id
  }
}

resource "oci_apigateway_gateway" "private" {
  compartment_id             = var.compartment_id
  display_name               = "${var.project_name}-gateway"
  endpoint_type              = "PRIVATE"
  subnet_id                  = var.private_subnet_id
  network_security_group_ids = var.network_security_group_ids
  freeform_tags              = local.common_tags
}

resource "oci_container_instances_container_instance" "application" {
  availability_domain      = var.availability_domain
  compartment_id           = var.compartment_id
  display_name             = "${var.project_name}-application"
  shape                    = "CI.Standard.E4.Flex"
  container_restart_policy = "ALWAYS"
  freeform_tags            = local.common_tags

  shape_config {
    ocpus         = 1
    memory_in_gbs = 4
  }

  vnics {
    subnet_id             = var.private_subnet_id
    nsg_ids               = var.network_security_group_ids
    is_public_ip_assigned = false
  }

  containers {
    display_name = "${var.project_name}-application"
    image_url    = var.image_url

    health_checks {
      name                     = "http-health"
      health_check_type        = "HTTP"
      path                     = "/health"
      port                     = 8080
      initial_delay_in_seconds = 10
      interval_in_seconds      = 30
      timeout_in_seconds       = 5
      failure_threshold        = 3
      success_threshold        = 1
      failure_action           = "KILL"
    }

    security_context {
      is_non_root_user_check_enabled = true
      is_root_file_system_readonly   = true
      run_as_user                    = 10001
      run_as_group                   = 10001
    }
  }
}
