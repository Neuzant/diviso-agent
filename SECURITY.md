# Security Policy

## Reporting a vulnerability

Please report security issues privately using GitHub's "Report a
vulnerability" (Security Advisories) on this repository. Do not open a
public issue for a vulnerability. We aim to acknowledge reports within
7 days.

## Security model

- Diviso runs locally; your data stays on your device unless you configure
  a cloud provider yourself.
- API keys are read only from environment variables, never stored in the
  repo or in Diviso's data files, and are redacted from logs/traces.
- File writes are confined to the workspace (sandbox) and shell/network
  actions require approval unless you explicitly enable auto-approve.
- Skills and plugins are loaded from local files only. Diviso never
  downloads a skill or plugin from the internet.
- Scheduled jobs have per-job token/cost guards and are skipped when a
  run would exceed them.
