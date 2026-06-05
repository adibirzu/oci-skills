#!/usr/bin/env python3
"""oci_context.py — friendly named contexts for OCI so you never paste OCIDs.

A *context* binds a short name to the three things almost every OCI call needs:

    name  ->  { profile, compartment (OCID), region [, description] }

Instead of remembering `--profile prod-admin --compartment-id <COMPARTMENT_OCID>`
you say `dev` or `prod`, and the skill pack resolves the rest. Contexts live in
``~/.oci-skills/contexts.json`` (mode 0600), OUTSIDE this repo, so real OCIDs
never touch git.

Stdlib only — no PyYAML, no oci SDK needed for context bookkeeping.

Usage:
    oci_context.py list
    oci_context.py add dev   --profile DEFAULT --compartment <OCID> --region eu-frankfurt-1 \
                             --description "personal sandbox"
    oci_context.py add prod  --profile prod-admin --compartment <OCID> --region us-phoenix-1 --prod
    oci_context.py get dev                       # human summary (masked OCID)
    oci_context.py get dev --field compartment   # raw value for scripting (stdout)
    oci_context.py use dev                       # `eval "$(oci_context.py use dev)"`
    oci_context.py current                       # show the active context, if any
    oci_context.py rm dev

Exit codes: 0 ok, 1 usage/error, 3 context not found.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path

STORE = Path(
    os.environ.get("OCI_SKILLS_CONTEXTS")
    or (Path.home() / ".oci-skills" / "contexts.json")
)
VALID_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# Accept a compartment OCID or the tenancy-root OCID. The trailing unique part is
# intentionally not matched — we only validate the type prefix, never store a sample.
OCID_RE = re.compile(r"^ocid1\.(compartment|tenancy)\.oc1\.")


def _eprint(*a: object) -> None:
    print(*a, file=sys.stderr)


def _load() -> dict:
    if not STORE.exists():
        return {"contexts": {}, "current": None}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _eprint(f"[error] cannot read {STORE}: {exc}")
        sys.exit(1)
    data.setdefault("contexts", {})
    data.setdefault("current", None)
    return data


def _save(data: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 0600 — contains compartment OCIDs
    tmp.replace(STORE)
    os.chmod(STORE, stat.S_IRUSR | stat.S_IWUSR)


def _mask(ocid: str) -> str:
    """Show only enough of an OCID to recognize it; never the full value."""
    if not ocid:
        return "<unset>"
    tail = ocid.rsplit(".", 1)[-1]
    return f"…{tail[-6:]}" if len(tail) > 6 else "…"


def _require(data: dict, name: str) -> dict:
    ctx = data["contexts"].get(name)
    if ctx is None:
        _eprint(f"[error] no context named '{name}'. Try: oci_context.py list")
        sys.exit(3)
    return ctx


def cmd_list(args: argparse.Namespace, data: dict) -> int:
    ctxs = data["contexts"]
    if not ctxs:
        _eprint("no contexts yet. Create one:")
        _eprint("  oci_context.py add dev --profile DEFAULT --compartment <OCID> --region <region>")
        return 0
    cur = data.get("current")
    print(f"{'':2}{'NAME':<16}{'PROFILE':<16}{'REGION':<18}{'COMPARTMENT':<14}{'FLAGS'}")
    for name in sorted(ctxs):
        c = ctxs[name]
        marker = "*" if name == cur else " "
        flags = "PROD" if c.get("prod") else ""
        print(
            f"{marker} {name:<16}{c.get('profile', 'DEFAULT'):<16}"
            f"{c.get('region', '<profile>'):<18}{_mask(c.get('compartment', '')):<14}{flags}"
        )
    return 0


def cmd_add(args: argparse.Namespace, data: dict) -> int:
    if not VALID_NAME.match(args.name):
        _eprint(f"[error] invalid context name '{args.name}' (use letters, digits, . _ -)")
        return 1
    if not OCID_RE.match(args.compartment):
        _eprint("[error] --compartment must be a compartment or tenancy OCID "
                "(an ocid1.compartment.* or ocid1.tenancy.* value)")
        return 1
    existed = args.name in data["contexts"]
    data["contexts"][args.name] = {
        "profile": args.profile,
        "compartment": args.compartment,
        "region": args.region,
        "description": args.description or "",
        "prod": bool(args.prod),
    }
    if data.get("current") is None and not existed:
        data["current"] = args.name
    _save(data)
    _eprint(f"[ok] {'updated' if existed else 'added'} context '{args.name}' "
            f"(profile={args.profile}, region={args.region}, compartment={_mask(args.compartment)})")
    return 0


def cmd_get(args: argparse.Namespace, data: dict) -> int:
    ctx = _require(data, args.name)
    if args.field:
        val = ctx.get(args.field, "")
        if not val:
            _eprint(f"[error] context '{args.name}' has no field '{args.field}'")
            return 1
        print(val)  # raw value to stdout — intended for command substitution
        return 0
    _eprint(f"context     : {args.name}{'  (PROD)' if ctx.get('prod') else ''}")
    _eprint(f"profile     : {ctx.get('profile', 'DEFAULT')}")
    _eprint(f"region      : {ctx.get('region', '<profile default>')}")
    _eprint(f"compartment : {_mask(ctx.get('compartment', ''))}  (full value via --field compartment)")
    if ctx.get("description"):
        _eprint(f"description : {ctx['description']}")
    return 0


def cmd_use(args: argparse.Namespace, data: dict) -> int:
    ctx = _require(data, args.name)
    data["current"] = args.name
    _save(data)
    # Emit shell exports for `eval "$(oci_context.py use NAME)"`.
    print(f"export OCI_SKILLS_CONTEXT={args.name}")
    print(f"export OCI_CLI_PROFILE={ctx.get('profile', 'DEFAULT')}")
    if ctx.get("region"):
        print(f"export OCI_REGION={ctx['region']}")
    print(f"export OCI_SKILLS_COMPARTMENT={ctx.get('compartment', '')}")
    _eprint(f"[ok] active context -> {args.name}")
    return 0


def cmd_current(args: argparse.Namespace, data: dict) -> int:
    cur = os.environ.get("OCI_SKILLS_CONTEXT") or data.get("current")
    if not cur:
        _eprint("no active context. Set one: oci_context.py use <name>")
        return 0
    return cmd_get(argparse.Namespace(name=cur, field=None), data)


def cmd_rm(args: argparse.Namespace, data: dict) -> int:
    _require(data, args.name)
    del data["contexts"][args.name]
    if data.get("current") == args.name:
        data["current"] = None
    _save(data)
    _eprint(f"[ok] removed context '{args.name}'")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Friendly named contexts for OCI (no OCIDs to memorize).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all contexts (OCIDs masked)").set_defaults(func=cmd_list)

    a = sub.add_parser("add", help="add or update a context")
    a.add_argument("name")
    a.add_argument("--profile", default="DEFAULT", help="~/.oci/config profile name")
    a.add_argument("--compartment", required=True, help="compartment or tenancy OCID")
    a.add_argument("--region", default="", help="region identifier, e.g. eu-frankfurt-1")
    a.add_argument("--description", default="", help="free-text note")
    a.add_argument("--prod", action="store_true", help="mark as production (extra-careful prompts)")
    a.set_defaults(func=cmd_add)

    g = sub.add_parser("get", help="show a context (or one --field for scripting)")
    g.add_argument("name")
    g.add_argument("--field", choices=["profile", "compartment", "region", "description"],
                   help="print a single raw field value to stdout")
    g.set_defaults(func=cmd_get)

    u = sub.add_parser("use", help="print exports to activate a context")
    u.add_argument("name")
    u.set_defaults(func=cmd_use)

    sub.add_parser("current", help="show the active context").set_defaults(func=cmd_current)

    r = sub.add_parser("rm", help="remove a context")
    r.add_argument("name")
    r.set_defaults(func=cmd_rm)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = _load()
    return args.func(args, data)


if __name__ == "__main__":
    sys.exit(main())
