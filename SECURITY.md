# Security Policy

## Reporting a vulnerability in SecHound

If you find a security issue in SecHound itself (e.g. the tooling leaks
credentials, executes untrusted input unsafely, or the sanitization gate can be
bypassed), please report it privately:

- Open a [GitHub security advisory](https://github.com/lonerzee/sechound-open/security/advisories/new), or
- email **security@your-org.example** with details and a repro.

Please do not open a public issue for an unfixed vulnerability. We aim to
acknowledge within 3 business days.

## Leaked target data

This project must never contain data about a specific target. If you find such
data in the repo or its history, treat it as a credential leak:

1. Report it privately (above) — do not open a public issue quoting the data.
2. Any exposed credential must be rotated by its owner; removing the file in a
   later commit is **not** sufficient because git history retains it.

## Authorized use only

SecHound is offensive security tooling. Use it **only** against systems you own
or are explicitly authorized to test. Operating it outside an authorized scope
may be illegal. You are responsible for staying within scope and the law.
