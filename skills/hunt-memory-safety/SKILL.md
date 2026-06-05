---
name: hunt-memory-safety
description: Native memory-safety hunt playbook — overflows, use-after-free, integer overflow, format strings in C/C++/unsafe code.
domain: binary
---

# hunt-memory-safety

Load when auditing native code (C/C++/Rust `unsafe`/CGo) or binaries for
memory-corruption bugs.

## When to load
buffer overflow, heap overflow, use-after-free, double free, integer overflow,
out-of-bounds, format string, OOB read/write, stack smashing.

## Where it lives
- Overflows: `strcpy`/`memcpy`/`sprintf`/`gets`, manual length math, fixed buffers.
- UAF/double-free: pointer kept after `free`; ownership/lifetime confusion.
- Integer: size/length arithmetic that can wrap before an allocation or bound.
- Format string: user data as the format argument to `printf`-family.

## Neutralizing controls (check, don't assume)
- Bounded APIs (`strncpy`/`snprintf` used *correctly*), `std::string`/`vector`, Rust safe types.
- Mitigations (ASLR/DEP/stack canaries/CFI) — they raise the bar but aren't a fix.
- Sanitizers in CI (ASan/UBSan) and fuzzing already covering the path.

## Probes
Static: trace attacker-controlled size/index/pointer to the unsafe op.
Dynamic: fuzz the parser/entry point (AFL++/libFuzzer) under ASan; oversized or
malformed input to trigger a crash; inspect the crash for exploitability.

## Validation bar
`confirmed` = a reproducible crash/corruption from attacker-controlled input,
with a triaged primitive (OOB read/write, control of a pointer/PC). A static hit
without a reachable, triggerable path is a candidate.

## Known chains
Memory corruption → control-flow hijack → RCE; OOB read → info leak defeating ASLR.
