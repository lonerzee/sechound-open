---
name: hunt-crypto
description: Cryptography hunt playbook — weak algorithms, bad modes, static IVs/keys, broken randomness, missing integrity.
domain: secrets
---

# hunt-crypto

Load when reviewing how the target encrypts, hashes, signs, or generates randomness.

## When to load
weak crypto, MD5/SHA1, ECB, static IV, hardcoded key, insecure random,
missing MAC, padding oracle, predictable token, JWT alg confusion.

## Where it lives
Encryption/signing helpers, password hashing, token/ID generation, TLS config,
key management.

## What to check (and the FP guards)
- **Algorithm:** MD5/SHA1 for security, DES/RC4, ECB mode → weak. (MD5 for a
  non-security checksum is fine — confirm the use.)
- **Keys/IVs:** hardcoded or reused keys; static/zero IV; key in source.
- **Randomness:** `rand()`/`Math.random()` for tokens/keys vs a CSPRNG.
- **Passwords:** fast hash (plain SHA) vs bcrypt/scrypt/argon2 with salt.
- **Integrity:** encryption without authentication (no MAC) → tampering/padding oracle.

## Validation bar
`confirmed` = demonstrate the consequence: forge/predict a token, decrypt/tamper
without the key, crack a recovered hash, or show key reuse enabling it. "Uses
MD5" alone is a candidate until impact is shown.

## Known chains
Weak token → session/account takeover; missing MAC → ciphertext tampering;
hardcoded key → mass decryption.
