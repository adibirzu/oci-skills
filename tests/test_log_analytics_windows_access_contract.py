from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_log_analytics_skill_routes_windows_access_monitoring():
    skill = (ROOT / "skills" / "oci-log-analytics" / "SKILL.md").read_text()

    assert "Windows access monitoring" in skill
    assert "Host (Windows)" in skill
    assert "three Oracle-defined Windows sources" in skill


def test_windows_access_reference_has_current_native_and_install_contracts():
    reference = (ROOT / "references" / "log-analytics.md").read_text()

    for required in (
        "Service.plugin.logan.download=true",
        "installer.bat <full_path_of_response_file>",
        "MsftWinEventSecurityLogSource",
        "MsftWinEventSystemLogSource",
        "MsftWinEventApplicationLogSource",
        "logan_windows_access",
        "WINDOWS_ACCESS_MANUAL_RUNBOOK.md",
        "management_agent_access_setup.ps1",
    ):
        assert required in reference


def test_oracle_docs_index_covers_windows_collection_to_alert_path():
    docs = (ROOT / "references" / "oracle-docs.md").read_text()

    for slug in (
        "perform-prerequisites-deploying-management-agents.html",
        "install-management-agent-chapter.html",
        "oracle-defined-sources.html",
        "manage-source-entity-association.html",
        "create-schedule-run-saved-search.html",
        "create-alerts-detected-events.html",
    ):
        assert slug in docs
