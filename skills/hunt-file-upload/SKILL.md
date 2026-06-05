---
name: hunt-file-upload
description: File-upload hunt playbook — unrestricted upload, type/extension bypass, path control, leading to RCE or stored XSS.
domain: web
---

# hunt-file-upload

Load when the target accepts file uploads (avatars, attachments, imports).

## When to load
file upload, unrestricted upload, web shell, content-type bypass, double
extension, SVG XSS, image parsing, polyglot, upload to webroot.

## Where it lives & what to check
- **Type enforcement:** server-side (magic bytes) vs. trusting client
  `Content-Type` / extension only.
- **Stored location:** can the file land in a web-served/executable path?
- **Name/path control:** attacker-controlled filename → traversal or overwrite.
- **Parsing:** server-side image/doc processing (ImageMagick, ffmpeg) on the upload.
- **SVG/HTML:** served inline → stored XSS.

## Neutralizing controls (check, don't assume)
- Allow-list of types verified by content, not extension; random server-side names.
- Storage outside webroot / object store with no execution; `Content-Disposition: attachment`.
- Image re-encoding that strips active content; size/quota limits.

## Probes
Upload a benign file with a mismatched type/extension; an SVG with a marker; a
filename with `../`; check where it's stored and whether it executes/renders.

## Validation bar
`confirmed` = the uploaded file executes (RCE), renders as active content
(stored XSS), or lands outside its intended location. A stored-but-inert file is INFO.

## Known chains
Upload-to-webroot → web shell → RCE; SVG → stored XSS → session theft.
