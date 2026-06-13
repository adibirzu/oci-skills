#!/usr/bin/env python3
"""Unit fence for scripts/iam_audit.py risk-detection + rendering.

iam_audit imports the `oci` SDK at module load (and exits 2 if absent). CI has no
SDK, so we inject a minimal fake `oci` into sys.modules BEFORE importing — enough
for the pure logic (audit/render_text) which only touches oci.pagination and
oci.exceptions. The live SDK paths (build_identity_client/main) are out of scope.
"""
from __future__ import annotations

import pathlib
import sys
import types

# --- fake oci SDK (pagination + exceptions only) ---------------------------
_fake = types.ModuleType("oci")
_pag = types.ModuleType("oci.pagination")
_exc = types.ModuleType("oci.exceptions")


class _ServiceError(Exception):
    def __init__(self, status: int = 403, code: str = "NotAuthorized") -> None:
        super().__init__(code)
        self.status = status
        self.code = code


_exc.ServiceError = _ServiceError
_exc.ConfigFileNotFound = type("ConfigFileNotFound", (Exception,), {})
_exc.InvalidConfig = type("InvalidConfig", (Exception,), {})
# list_all -> oci.pagination.list_call_get_all_results(fn, **kw).data ; fake just calls fn.
_pag.list_call_get_all_results = lambda fn, **kw: types.SimpleNamespace(data=fn(**kw))
_fake.pagination = _pag
_fake.exceptions = _exc
sys.modules["oci"] = _fake
sys.modules["oci.pagination"] = _pag
sys.modules["oci.exceptions"] = _exc

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import iam_audit  # noqa: E402


class _Pol:
    def __init__(self, name, statements):
        self.name = name
        self.statements = statements


class _User:
    def __init__(self, name, mfa):
        self.name = name
        self.is_mfa_activated = mfa


class _Cmpt:
    def __init__(self, cid):
        self.id = cid


class _Client:
    def __init__(self, policies, users, compartments=None):
        self._policies = policies
        self._users = users
        self._compartments = compartments or []

    def list_compartments(self, **kw):
        return self._compartments

    def list_policies(self, **kw):
        return self._policies

    def list_users(self, **kw):
        return self._users

    def list_groups(self, **kw):
        return []

    def list_dynamic_groups(self, **kw):
        return []


def test_audit_flags_tenancy_wide_manage_and_mfa_gaps() -> None:
    client = _Client(
        policies=[
            _Pol("broad-admins", ["Allow group admins to manage all-resources in tenancy"]),
            _Pol("scoped-devs", ["Allow group devs to read buckets in compartment apps"]),
        ],
        users=[_User("alice", False), _User("bob", True)],
    )
    summary = iam_audit.audit(client, "fake-tenancy")
    assert summary["policies"] == 2
    assert summary["risks"]["tenancy_wide_manage_all"] == ["broad-admins"]
    assert summary["risks"]["users_without_mfa"] == ["alice"]


def test_audit_skips_unauthorized_scope_but_continues() -> None:
    class _C(_Client):
        def __init__(self):
            super().__init__([], [], compartments=[_Cmpt("c1")])
            self._calls = 0

        def list_policies(self, **kw):
            self._calls += 1
            if self._calls == 1:                  # tenancy scope: access denied
                raise _ServiceError(403, "NotAuthorized")
            return [_Pol("ok", ["allow group x to read all"])]

    summary = iam_audit.audit(_C(), "fake-tenancy")
    assert summary["policies"] == 1                # the second scope still counted


def test_render_text_includes_counts_and_named_risks() -> None:
    summary = {
        "compartments": 1, "policies": 2, "users": 2, "groups": 0, "dynamic_groups": 0,
        "risks": {"tenancy_wide_manage_all": ["broad-admins"], "users_without_mfa": ["alice"]},
    }
    out = iam_audit.render_text(summary)
    assert "policies         : 2" in out
    assert "- broad-admins" in out
    assert "- alice" in out


# --- main(): faked identity client so we exercise rendering + error handling --

def _client_ok() -> _Client:
    return _Client(
        policies=[_Pol("broad-admins", ["Allow group a to manage all-resources in tenancy"])],
        users=[_User("alice", False)],
    )


def test_main_text_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(iam_audit, "build_identity_client", lambda p, a: (_client_ok(), "ten"))
    assert iam_audit.main([]) == 0
    assert "IAM posture snapshot" in capsys.readouterr().out


def test_main_json_output(monkeypatch, capsys) -> None:
    import json
    monkeypatch.setattr(iam_audit, "build_identity_client", lambda p, a: (_client_ok(), "ten"))
    assert iam_audit.main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["risks"]["users_without_mfa"] == ["alice"]


def test_main_service_error_returns_1(monkeypatch) -> None:
    def boom(profile, auth):
        raise _ServiceError(403, "NotAuthorized")
    monkeypatch.setattr(iam_audit, "build_identity_client", boom)
    assert iam_audit.main([]) == 1


def test_main_config_problem_returns_2(monkeypatch) -> None:
    def boom(profile, auth):
        raise _exc.ConfigFileNotFound("no config file")
    monkeypatch.setattr(iam_audit, "build_identity_client", boom)
    assert iam_audit.main([]) == 2
