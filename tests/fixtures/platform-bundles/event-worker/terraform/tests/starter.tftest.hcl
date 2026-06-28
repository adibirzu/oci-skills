mock_provider "oci" {}

run "starter_contract" {
  command = plan

  variables {
    compartment_id = "<COMPARTMENT_OCID>"
    region         = "<OCI_REGION>"
  }

  assert {
    condition     = output.state_owner == "terraform"
    error_message = "Terraform must remain the declared durable-resource owner."
  }
}
