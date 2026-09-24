# Third-party notices

This distribution is governed by the repository's `LICENSE`. The following
third-party GitHub Actions are referenced by the hosted CI workflow. They are
not bundled into copy-install payloads; the pinned revision is recorded here so
recipients can inspect the exact upstream source and its license before use.

| Component | Pinned revision | License source |
| --- | --- | --- |
| actions/checkout | `11d5960a326750d5838078e36cf38b85af677262` | <https://github.com/actions/checkout/blob/11d5960a326750d5838078e36cf38b85af677262/LICENSE> |
| actions/setup-python | `a26af69be951a213d495a4c3e4e4022e16d87065` | <https://github.com/actions/setup-python/blob/a26af69be951a213d495a4c3e4e4022e16d87065/LICENSE> |
| gitleaks/gitleaks-action | `ff98106e4c7b2bc287b24eaf42907196329070c7` | <https://github.com/gitleaks/gitleaks-action/blob/ff98106e4c7b2bc287b24eaf42907196329070c7/LICENSE> |
| hashicorp/setup-terraform | `b9cd54a3c349d3f38e8881555d616ced269862dd` | <https://github.com/hashicorp/setup-terraform/blob/b9cd54a3c349d3f38e8881555d616ced269862dd/LICENSE> |

The release-attestation verifier uses `cryptography==44.0.3` only in the
development/release-validation environment; it is not copied into harness
payloads. Its upstream license is Apache-2.0/BSD-3-Clause:
<https://github.com/pyca/cryptography/blob/44.0.3/LICENSE>.

The CI validation environment also pins the OCI Python SDK (`oci==2.181.1`),
ReportLab (`reportlab==4.4.10`), and pypdf (`pypdf==6.7.1`) for read-only
helper and document fixture tests. These packages are development/test
dependencies only and are not copied into harness payloads. Their upstream
license sources are:

- <https://github.com/oracle/oci-python-sdk/blob/v2.181.1/LICENSE.txt>
- <https://hg.reportlab.com/hg-public/reportlab/file/4.4.10/LICENSE.txt>
- <https://github.com/py-pdf/pypdf/blob/6.7.1/LICENSE>

The list covers checked-in distribution/runtime references as of the candidate
revision. Regenerate or review it whenever a bundled dependency, binary, asset,
or hosted action changes. It is an attribution and provenance record, not a
claim that an upstream project endorses this skill pack.
