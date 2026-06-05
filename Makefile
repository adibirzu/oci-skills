# OCI Administrator skill pack — install helpers.
# `make install` installs into every detected agent harness.

INSTALL := ./install.sh

.PHONY: help install install-claude install-codex install-gemini install-antigravity list dry-run check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install into every detected harness
	@$(INSTALL)

install-claude: ## Install into Claude Code only
	@$(INSTALL) claude

install-codex: ## Install into Codex only
	@$(INSTALL) codex

install-gemini: ## Install into Gemini CLI only
	@$(INSTALL) gemini

install-antigravity: ## Install into Antigravity only
	@$(INSTALL) antigravity

list: ## Show which harnesses are detected
	@$(INSTALL) --list

dry-run: ## Preview install actions without copying anything
	@DRY_RUN=true $(INSTALL) claude codex gemini antigravity

check: ## Lint scripts + run the secret/redaction gate
	@command -v shellcheck >/dev/null && shellcheck -x --severity=warning scripts/*.sh install.sh bootstrap.sh || echo "shellcheck not installed (skipped)"
	@for f in $$(git ls-files); do python3 scripts/redact.py --check "$$f" >/dev/null 2>&1 || echo "FLAGGED: $$f"; done; echo "redaction gate done"
