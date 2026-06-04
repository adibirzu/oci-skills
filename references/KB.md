# OCI Administrator Knowledge Base

Known operational fixes. Search before deep debugging:

```bash
python3 scripts/kb_lookup.py "symptom words" [domain-tag]
```

Add a new `KB-<n>` entry whenever you resolve a new operational error.

---

## KB-001 — OKE kubectl Unauthorized right after create-kubeconfig (iam-oke)

**Symptom:** `kubectl` returns `Unauthorized` / "asked for credentials" immediately
after `oci ce cluster create-kubeconfig`.
**Root cause:** OKE has two authorization layers. The kubeconfig token mint
(IAM `manage cluster` / `use cluster`) is separate from in-cluster Kubernetes
RBAC. A token can be minted yet bound to no RBAC subject.
**Fix:** Ensure the caller's IAM principal maps to a Kubernetes RBAC subject
(a `ClusterRoleBinding` to the user/group OCID, or the `oci:` group mapping).
Verify with `kubectl auth can-i --list`.
**Status:** resolved.

## KB-002 — Identity Domains user filter returns nothing (iam)

**Symptom:** `identity-domains user list --filter "user-name eq \"x\""` returns empty
though the user exists.
**Root cause:** SCIM filters use camelCase attribute names; response fields are
kebab-case. The filter attribute was kebab-case.
**Fix:** Filter with `userName eq "x"` (camelCase). Read results as `user-name`.
**Status:** resolved.

## KB-003 — Service/quota limit exceeded on provision (iam-tenancy)

**Symptom:** Create call fails with `LimitExceeded` or capacity errors.
**Root cause:** Region/compartment has insufficient service-limit headroom.
**Fix:** Pre-check before provisioning:
`oci limits resource-availability get --service-name <svc> --limit-name <limit> --compartment-id <COMPARTMENT_OCID>`.
Request a limit increase or pick another AD/region if `available` is 0.
**Status:** resolved.

## KB-004 — WAF policy not blocking after attach (security)

**Symptom:** WAF policy created and attached to the load balancer but malicious
requests are not blocked.
**Root cause:** Policy attached but protection rules were left in `OBSERVE`
(detection) action rather than `BLOCK`, or the LB listener references a different
policy.
**Fix:** Set the protection-capability action to `BLOCK`, confirm the LB's WAF
association points at the intended policy OCID, and re-test.
**Status:** resolved.

## KB-005 — Vault secret base64 vs raw content (security)

**Symptom:** A secret read from Vault is garbled or fails to authenticate.
**Root cause:** `get_secret_bundle` returns base64-encoded content; it was used raw.
**Fix:** `base64.b64decode(bundle.secret_bundle_content.content).decode()` before use.
**Status:** resolved.

## KB-006 — Cross-tenancy OCIR pull fails on worker nodes (networking-compute)

**Symptom:** Pods stuck `ImagePullBackOff` pulling from `<region>.ocir.io/<ns>/...`
on an OKE cluster in a different tenancy than the registry.
**Root cause:** The image-pull secret (auth token for the registry tenancy) was
not replicated into the consuming cluster/namespace.
**Fix:** Create the docker-registry secret with a valid auth token for the
**registry** tenancy and reference it in `imagePullSecrets`.
**Status:** resolved.
