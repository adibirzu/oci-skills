variable "compartment_id" {
  type      = string
  sensitive = true
}

variable "project_name" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$", var.project_name))
    error_message = "project_name must be a safe 1-64 character name."
  }
}

variable "notification_topic_id" {
  description = "ONS topic for build and deployment notifications."
  type        = string
  sensitive   = true
}

variable "private_subnet_id" {
  type      = string
  sensitive = true
}

variable "network_security_group_ids" {
  type      = set(string)
  sensitive = true
  default   = []
}

variable "availability_domain" {
  type = string
}

variable "image_url" {
  description = "Immutable container image digest, not a mutable tag."
  type        = string
  validation {
    condition     = can(regex("@sha256:[A-Fa-f0-9]{64}$", var.image_url))
    error_message = "image_url must use an immutable sha256 digest."
  }
}
