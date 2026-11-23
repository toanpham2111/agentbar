# Provider Adapter Specification

Each adapter implements detection and normalized collection independently. Status is available, partially supported, not installed, authentication required, permission required, unsupported, or error.

- Claude Code: installation and local session token logs. Subscription quota is unavailable.
- OpenAI Codex: installation and local cumulative session token logs. Account quota is unavailable.
- Gemini CLI: installation only until a documented non-interactive statistics interface is verified.
- Cursor: installation only.
- GitHub Copilot: installation only unless the user explicitly authorizes a supported metrics API.
- Antigravity: installation only; private process CSRF/RPC collection is prohibited.

Malformed lines are ignored safely, permission failures are surfaced, and missing metrics are not converted to zero. Sanitized fixtures cover supported parsers.
