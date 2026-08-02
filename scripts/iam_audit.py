#!/usr/bin/env python3
"""iam_audit.py — read-only IAM posture snapshot for an OCI tenancy.

A generic, tenancy-agnostic audit that any administrator can run. It enumerates
compartments, policies, users, groups, and dynamic groups, then flags a few
common risks (broad `manage all-resources` grants, MFA-less users). It makes
ONLY read calls and prints redacted output.

Usage:
    python3 iam_audit.py                       # uses DEFAULT profile
    python3 iam_audit.py --profile cap         # named config profile
    python3 iam_audit.py --auth instance_principal
    python3 iam_audit.py --json                # machine-readable summary

Requires the `oci` Python SDK:  pip install oci
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    import oci  # type: ignore
except ImportError:  # pragma: no cover - import guard
    print("iam_audit: the 'oci' Python SDK is required (pip install oci)", file=sys.stderr)
    raise SystemExit(2)


def build_identity_client(profile: str, auth: str) -> tuple[oci.identity.IdentityClient, str]:
    """Return (identity_client, tenancy_ocid) for the requested auth mode."""
    if auth == "instance_principal":
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        return oci.identity.IdentityClient({}, signer=signer), signer.tenancy_id
    if auth == "resource_principal":
        signer = oci.auth.signers.get_resource_principals_signer()
        return oci.identity.IdentityClient({}, signer=signer), signer.tenancy_id
    config = oci.config.from_file(profile_name=profile)
    oci.config.validate_config(config)
    return oci.identity.IdentityClient(config), config["tenancy"]


def list_all(list_fn: Any, **kwargs: Any) -> list[Any]:
    """Page through any list_* SDK call and return every item."""
    return oci.pagination.list_call_get_all_results(list_fn, **kwargs).data


def audit(client: oci.identity.IdentityClient, tenancy_id: str) -> dict[str, Any]:
    compartments = list_all(
        client.list_compartments,
        compartment_id=tenancy_id,
        compartment_id_in_subtree=True,
        lifecycle_state="ACTIVE",
    )
    scopes = [tenancy_id] + [c.id for c in compartments]

    policies: list[Any] = []
    for scope in scopes:
        try:
            policies.extend(list_all(client.list_policies, compartment_id=scope))
        except oci.exceptions.ServiceError as exc:  # keep going, record nothing secret
            print(f"iam_audit: skipped a compartment ({exc.status})", file=sys.stderr)

    users = list_all(client.list_users, compartment_id=tenancy_id)
    groups = list_all(client.list_groups, compartment_id=tenancy_id)
    dyn_groups = list_all(client.list_dynamic_groups, compartment_id=tenancy_id)

    broad_policies = []
    for pol in policies:
        for stmt in getattr(pol, "statements", []) or []:
            low = stmt.lower()
            if "manage all-resources" in low and "tenancy" in low:
                broad_policies.append(pol.name)
                break

    mfa_disabled = [u.name for u in users if getattr(u, "is_mfa_activated", True) is False]

    return {
        "compartments": len(compartments),
        "policies": len(policies),
        "users": len(users),
        "groups": len(groups),
        "dynamic_groups": len(dyn_groups),
        "risks": {
            "tenancy_wide_manage_all": sorted(set(broad_policies)),
            "users_without_mfa": sorted(mfa_disabled),
        },
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "OCI IAM posture snapshot",
        "------------------------",
        f"compartments     : {summary['compartments']}",
        f"policies         : {summary['policies']}",
        f"users            : {summary['users']}",
        f"groups           : {summary['groups']}",
        f"dynamic groups   : {summary['dynamic_groups']}",
        "",
        "Risks",
        f"  tenancy-wide 'manage all-resources' : {len(summary['risks']['tenancy_wide_manage_all'])} policy(ies)",
    ]
    for name in summary["risks"]["tenancy_wide_manage_all"]:
        lines.append(f"    - {name}")
    lines.append(f"  users without MFA                   : {len(summary['risks']['users_without_mfa'])}")
    for name in summary["risks"]["users_without_mfa"]:
        lines.append(f"    - {name}")
    return "\n".join(lines)


def _print_self_lockout_guidance(exc: Any, profile: str) -> None:
    """Explain an IAM authorization denial as a likely self-lockout, with next steps.

    A 401/403/404 (NotAuthorized) while enumerating users/groups/policies means
    the principal running this audit has no IAM read. If it used to be an admin,
    it was probably removed from a privileged group. We surface that explicitly
    instead of a bare "service error", and hand off the two follow-up actions:
    confirm your own group membership, then have an admin query Audit for the
    actor who changed it.
    """
    msg = [
        f"iam_audit: authorization denied enumerating IAM ({exc.status} {exc.code}).",
        "  The principal running this audit lacks IAM read (inspect users/groups/",
        "  policies in the tenancy). If you previously had admin here, you may have",
        "  been removed from a privileged group (e.g. Administrators).",
        "",
        "  1) Confirm your own membership (empty output = you were removed):",
        "       oci iam user list-groups --user-id <your-user-ocid> \\",
        f"         --compartment-id <tenancy-ocid> --profile {profile}",
        "",
        "  2) Find WHO changed it — an admin who still has access queries OCI Audit",
        "     for identity events (see the /audit and /logan skill commands):",
        "       event-type com.oraclecloud.identityControlPlane.RemoveUserFromGroup",
    ]
    print("\n".join(msg), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only OCI IAM posture snapshot.")
    parser.add_argument("--profile", default="DEFAULT", help="OCI config profile (default: DEFAULT)")
    parser.add_argument("--auth", default="config",
                        choices=["config", "instance_principal", "resource_principal"],
                        help="authentication mode (default: config)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    try:
        client, tenancy_id = build_identity_client(args.profile, args.auth)
        summary = audit(client, tenancy_id)
    except oci.exceptions.ServiceError as exc:
        if exc.status in (401, 403, 404) or "NotAuthorized" in str(getattr(exc, "code", "")):
            _print_self_lockout_guidance(exc, args.profile)
            return 1
        print(f"iam_audit: OCI service error: {exc.status} {exc.code}", file=sys.stderr)
        return 1
    except (oci.exceptions.ConfigFileNotFound, oci.exceptions.InvalidConfig) as exc:
        print(f"iam_audit: config problem: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render_text(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
