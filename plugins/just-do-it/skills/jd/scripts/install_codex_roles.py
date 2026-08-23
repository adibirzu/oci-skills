#!/usr/bin/env python3
"""Safely check or install JD's optional Codex role configuration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import tomllib
from datetime import UTC, datetime


VERSION = "1.5.0"
BEGIN = "# BEGIN JD MANAGED ROLES"
END = "# END JD MANAGED ROLES"
SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
ROLE_SOURCE = SKILL_ROOT / "assets" / "roles"
REGISTRATION_SOURCE = ROLE_SOURCE / "agents.toml"


class InstallError(RuntimeError):
    pass


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: pathlib.Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _refuse_symlink(path: pathlib.Path, label: str) -> None:
    if path.is_symlink():
        raise InstallError(f"refusing symlinked {label}: {path}")


def _sources() -> tuple[dict[str, dict[str, str]], dict[pathlib.Path, bytes]]:
    _refuse_symlink(ROLE_SOURCE, "role source directory")
    registrations = tomllib.loads(REGISTRATION_SOURCE.read_text(encoding="utf-8"))["agents"]
    roles: dict[pathlib.Path, bytes] = {}
    for name, registration in registrations.items():
        relative = pathlib.PurePosixPath(registration["config_file"])
        if relative.parts[:1] != ("agents",) or len(relative.parts) != 2:
            raise InstallError(f"unsafe role path for {name}: {relative}")
        source = ROLE_SOURCE / relative.name
        _refuse_symlink(source, f"role source {name}")
        data = source.read_bytes()
        parsed = tomllib.loads(data.decode("utf-8"))
        if parsed.get("name") != name:
            raise InstallError(f"role name mismatch: {source.name}")
        roles[pathlib.Path(*relative.parts)] = data
    return registrations, roles


def _config_block(registrations: dict[str, dict[str, str]]) -> str:
    lines = [f"{BEGIN} {VERSION}"]
    for name, registration in registrations.items():
        description = json.dumps(registration["description"])
        config_file = json.dumps(registration["config_file"])
        lines.extend(
            (
                f"[agents.{name}]",
                f"description = {description}",
                f"config_file = {config_file}",
                "",
            )
        )
    lines.append(END)
    return "\n".join(lines).rstrip() + "\n"


def _managed_slice(config: str) -> tuple[int, int, str] | None:
    start = config.find(BEGIN)
    if start < 0:
        if END in config:
            raise InstallError("orphan JD managed-role end marker")
        return None
    end_marker = config.find(END, start)
    if end_marker < 0 or config.find(BEGIN, start + len(BEGIN)) >= 0:
        raise InstallError("malformed JD managed-role markers")
    end = config.find("\n", end_marker)
    end = len(config) if end < 0 else end + 1
    return start, end, config[start:end]


def _load_manifest(path: pathlib.Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    _refuse_symlink(path, "JD install manifest")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallError(f"invalid JD install manifest: {error}") from error


def _check(home: pathlib.Path) -> int:
    if not home.exists():
        print("JD Codex roles are not installed")
        return 1
    _refuse_symlink(home, "Codex home")
    registrations, roles = _sources()
    config_path = home / "config.toml"
    manifest_path = home / "state" / "jd" / "role-install.json"
    manifest = _load_manifest(manifest_path)
    if not config_path.is_file() or manifest is None:
        print("JD Codex roles are not installed")
        return 1
    _refuse_symlink(config_path, "Codex config")
    config = config_path.read_text(encoding="utf-8")
    managed = _managed_slice(config)
    expected_block = _config_block(registrations)
    problems: list[str] = []
    if managed is None or managed[2] != expected_block:
        problems.append("managed config block is missing or stale")
    for relative, source in roles.items():
        target = home / relative
        if not target.is_file() or target.is_symlink() or target.read_bytes() != source:
            problems.append(f"role is missing or stale: {relative}")
    if problems:
        print("JD Codex role check failed: " + "; ".join(problems))
        return 1
    if manifest.get("version") != VERSION:
        print("JD Codex role check failed: install manifest is stale")
        return 1
    print(f"JD Codex roles {VERSION} are installed and current")
    return 0


def _install(home: pathlib.Path) -> int:
    _refuse_symlink(home, "Codex home")
    registrations, roles = _sources()
    config_path = home / "config.toml"
    agents_path = home / "agents"
    state_path = home / "state" / "jd"
    for path, label in ((config_path, "Codex config"), (agents_path, "agents directory"), (state_path, "JD state directory")):
        _refuse_symlink(path, label)

    manifest_path = state_path / "role-install.json"
    previous = _load_manifest(manifest_path)
    previous_hashes = previous.get("role_hashes", {}) if previous else {}
    if not isinstance(previous_hashes, dict):
        raise InstallError("invalid role hashes in JD install manifest")

    for relative, source in roles.items():
        target = home / relative
        _refuse_symlink(target, f"role file {relative}")
        if target.exists() and target.read_bytes() != source:
            installed_hash = previous_hashes.get(str(relative))
            if installed_hash != _digest(target.read_bytes()):
                raise InstallError(f"unmanaged role file conflict: {target}")

    existing_config = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    try:
        parsed = tomllib.loads(existing_config) if existing_config.strip() else {}
    except tomllib.TOMLDecodeError as error:
        raise InstallError(f"existing config.toml is invalid: {error}") from error
    expected_block = _config_block(registrations)
    managed = _managed_slice(existing_config)
    if managed:
        previous_block_hash = previous.get("config_block_sha256") if previous else None
        if managed[2] != expected_block and previous_block_hash != _digest(managed[2].encode()):
            raise InstallError("JD managed config block was edited; refusing to overwrite it")
        new_config = existing_config[: managed[0]] + expected_block + existing_config[managed[1] :]
    else:
        configured = parsed.get("agents", {})
        collisions = sorted(set(registrations).intersection(configured)) if isinstance(configured, dict) else []
        if collisions:
            raise InstallError("unmanaged agent registration conflict: " + ", ".join(collisions))
        separator = "" if not existing_config or existing_config.endswith("\n\n") else "\n"
        new_config = existing_config + separator + expected_block
    try:
        tomllib.loads(new_config)
    except tomllib.TOMLDecodeError as error:
        raise InstallError(f"generated config.toml is invalid: {error}") from error

    changes = config_path.read_bytes() != new_config.encode() if config_path.exists() else True
    role_changes = [(relative, data) for relative, data in roles.items() if not (home / relative).exists() or (home / relative).read_bytes() != data]
    backup_dir: pathlib.Path | None = None
    if changes or role_changes:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_dir = home / "backups" / "jd" / stamp
        backup_dir.mkdir(parents=True, mode=0o700)
        os.chmod(backup_dir, 0o700)
        if config_path.exists():
            shutil.copy2(config_path, backup_dir / "config.toml")
            os.chmod(backup_dir / "config.toml", 0o600)
        for relative, _ in role_changes:
            target = home / relative
            if target.exists():
                backup = backup_dir / relative
                backup.parent.mkdir(parents=True, mode=0o700)
                shutil.copy2(target, backup)
                os.chmod(backup, 0o600)

    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    agents_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(agents_path, 0o700)
    for relative, data in role_changes:
        _atomic_write(home / relative, data)
    if changes:
        _atomic_write(config_path, new_config.encode())
    manifest = {
        "version": VERSION,
        "managed_roles": sorted(registrations),
        "role_hashes": {str(relative): _digest(data) for relative, data in roles.items()},
        "config_block_sha256": _digest(expected_block.encode()),
        "installed_at": datetime.now(UTC).isoformat(),
        "backup": str(backup_dir.relative_to(home)) if backup_dir else None,
    }
    _atomic_write(manifest_path, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    print(f"Installed JD Codex roles {VERSION} into {home}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install"), nargs="?", default="check")
    parser.add_argument(
        "--codex-home",
        type=pathlib.Path,
        default=pathlib.Path(os.environ.get("CODEX_HOME", pathlib.Path.home() / ".codex")),
    )
    args = parser.parse_args()
    try:
        return _check(args.codex_home) if args.action == "check" else _install(args.codex_home)
    except InstallError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
