---
name: hunt-deserialization
description: Insecure deserialization hunt playbook — untrusted bytes into a native deserializer / object factory.
domain: web
---

# hunt-deserialization

Load when untrusted input is deserialized into language objects.

## When to load
insecure deserialization, pickle, `ObjectInputStream`/Java serialization,
PHP `unserialize`, YAML `load`, Marshal, gadget chains, BinaryFormatter.

## Where it lives
Endpoints/handlers that accept serialized blobs (cookies, caches, queues, RPC,
import features) and feed them to a native deserializer or unsafe loader.

## Neutralizing controls (check, don't assume)
- Data-only formats (JSON/protobuf) with schema validation — no object instantiation.
- Type/class allow-lists on the deserializer; safe loaders (`yaml.safe_load`).
- Integrity (signed/encrypted blobs) so attacker can't supply arbitrary bytes.

## Probes
Confirm the format is a native-object serializer and that input reaches it
unauthenticated/unsigned. Use a *non-destructive* sentinel gadget (e.g. one that
triggers an observable benign side effect / OOB ping), never a destructive payload.

## Validation bar
`confirmed` = attacker-supplied serialized data causes object instantiation/side
effects beyond plain data parsing (ideally an OOB signal you control).

## Known chains
Deserialization → RCE (gadget chain) → full host compromise.
