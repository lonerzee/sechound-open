---
name: hunt-path-traversal
description: Path traversal / LFI hunt playbook — user input reaching filesystem paths (read, write, include, archive extraction).
domain: web
---

# hunt-path-traversal

Load when user input influences a filesystem path: downloads, uploads, includes,
template/file loads, or archive extraction (zip-slip).

## When to load
path traversal, directory traversal, LFI, RFI, arbitrary file read/write,
zip-slip, `../`, file download/upload, archive extraction.

## Where it lives
- Read: file download/serve endpoints, log/report fetch, template loaders.
- Write: upload handlers, export-to-path, log paths from input.
- Extraction: unzip/untar that trusts archive entry names (zip-slip).

## Neutralizing controls (check, don't assume)
- Canonicalize then verify the resolved path stays under an allowed base dir.
- Allow-list of filenames/ids (no raw path from input).
- Reject `..`, absolute paths, NUL, and symlink escapes *after* normalization.

## Probes
`../` sequences (and encoded variants `%2e%2e`, `....//`, overlong UTF-8) toward
a known file; for write/extraction, an entry that escapes the target dir.

## Validation bar
`confirmed` = you read/write a file outside the intended directory (show the
out-of-scope content or the planted file location).

## Known chains
Arbitrary read → secret/config exfil → wider compromise. Arbitrary write →
code execution (drop into a served/executed path).
