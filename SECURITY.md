# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 3.x     | Yes       |
| < 3.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Email the maintainers or use [GitHub Security Advisories](https://github.com/jaim12005/Mistral_Markitdown/security/advisories/new) to report privately.
3. Include steps to reproduce, impact assessment, and any suggested fixes.
4. You will receive an acknowledgment within 48 hours and a detailed response within 7 days.

## Security Considerations

### API Key Handling

- **Never** commit API keys to version control.
- Store your `MISTRAL_API_KEY` in a `.env` file (already in `.gitignore`).
- Use environment variables or a secrets manager in production/CI environments.
- The application loads keys via `python-dotenv` and never logs or prints them.

### File Upload Security

- Documents uploaded for OCR are sent to Mistral's servers via their Files API.
- Uploaded files are subject to Mistral's [data retention policy](https://mistral.ai/terms/).
- The application auto-deletes uploaded files after a configurable retention period (`UPLOAD_RETENTION_DAYS`, default: 7 days).
- Review Mistral's terms of service before processing sensitive or regulated documents.

### URL Validation (SSRF Protection)

All document URLs (for QnA and streaming) are validated before use:

- Only HTTPS URLs are accepted.
- URLs with embedded credentials are rejected.
- Private/internal network addresses are blocked (RFC 1918, link-local, loopback, cloud metadata endpoints).
- IPv6-mapped IPv4 addresses are checked for private ranges.
- DNS resolution is verified to prevent DNS rebinding attacks.

### Dependency Security

Run periodic dependency audits:

```bash
# Using pip-audit
pip install pip-audit
pip-audit

# Using safety
pip install safety
safety check
```

### Input Validation

- File paths are validated before processing.
- Batch job IDs are validated against a strict regex pattern.
- Configuration values use safe parsing with bounds checking and defaults.

## Best Practices

- Keep dependencies up to date (`pip install --upgrade -r requirements.txt`).
- Run `make check` before deploying changes (includes linting and tests).
- Use the principle of least privilege for API keys — only grant OCR access if that's all you need.
- Monitor the [GitHub Security Advisories](https://github.com/jaim12005/Mistral_Markitdown/security) page for updates.
