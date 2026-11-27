# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## Reporting a Vulnerability

We take the security and privacy of our users seriously. Because Kio Usage Monitoring reads local AI agent sessions, maintaining a strict local-first boundary is essential.

If you discover a security vulnerability or privacy leak:

1. **Do not create a public GitHub issue.**
2. Send a responsible disclosure report directly via GitHub Security Advisories or email the maintainer.
3. Include:
   - Type of issue (e.g. credential leakage, unintended network transmission, local injection).
   - Step-by-step instructions or proof-of-concept to reproduce.
   - Potential impact.

We will acknowledge receipt within 48 hours and work with you to release a security advisory and patch promptly.

---

## Security Principles

- **Local-First**: Kio stores telemetry in local memory and SQLite cache. It never transmits prompt contents, source code, credentials, or telemetry to external servers.
- **Least Privilege**: The application only reads local log summaries and authorized provider endpoints.
- **Sanitized Logging**: All debug logs and error messages strip authorization headers, bearer tokens, and credentials before writing to disk.
