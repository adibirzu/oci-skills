# fixture-adb-service platform runbook

1. Select and preflight the named context; verify tenancy and compartment names.
2. Validate `platform-bundle.yaml`, Terraform, CLI plans, IAM, quota, and private networking.
3. Run `oci_tf.sh plan`; inspect create/update/replace/delete and public/secret signals.
4. Apply only the unchanged reviewed plan with a context-bound `run_action` approval.
5. Run every named verification check, inspect logs/alarms, and record the result.
6. Roll back with the last known-good DevOps deployment. Reconcile Terraform after any CLI break-glass action.

Nested JSON and credentials are written only to a temporary `0600` file, passed as `file://...`, and deleted in a trap/finally block.
