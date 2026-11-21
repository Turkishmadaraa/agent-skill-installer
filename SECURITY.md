# Güvenlik Politikası / Security Policy

## Açık bildirme / Reporting

Lütfen güvenlik açıklarını herkese açık issue olarak değil, GitHub'ın
**Security → Report a vulnerability** (private advisory) özelliğiyle bildirin.
Please report vulnerabilities privately via GitHub *Security → Report a vulnerability*.

## Tasarım ilkeleri / Design

- Downloaded content is never executed; files are copied without permission bits.
- HTTPS only, HTTPS-only redirects; `GITHUB_TOKEN` sent only to GitHub hosts, never forwarded on redirect.
- Archive extraction blocks path traversal, absolute paths, symlinks/hardlinks; enforces real-size,
  file-count and download limits (zip-bomb safe).
- Static content scan blocks pipe-to-shell, obfuscated shell, destructive `rm`, credential paths,
  reverse shells, prompt-injection phrases and binaries unless `--allow-risky` is passed.
- `allowed-tools` frontmatter is stripped so third-party skills cannot pre-approve tools.

Static scanning is a safety net, not a guarantee. Review unknown skills with `--dry-run`.
