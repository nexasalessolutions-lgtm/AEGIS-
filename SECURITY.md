# AEGIS security policy

## Scope and safe operation
AEGIS is intended for authorized defensive research. Live chain integrations are read-only. Do not add wallet signing, private-key collection, transaction broadcasting, automated fund movement, or live exploit execution to the production service.

## Evidence classification
1. Provider metadata is an index hint, not ownership attestation.
2. Bytecode, storage slots and account state must include chain and block context.
3. Source verification is not proof that source is correct or matches every deployed component.
4. Static-analysis output is a signal requiring review.
5. Fork reproduction is a local simulation tied to a specific block and RPC state. It does not alone establish current live exploitability.

## Reporting
Reports should include chain ID, block number, address, runtime code hash, source provenance, tool/version, command/configuration, finding confidence, reproduction status and limitations. Never label an unverified candidate or heuristic as a confirmed vulnerability.

## Worker isolation
Untrusted Solidity source bundles must be size-limited, safely extracted, processed with fixed commands, run under resource limits, and kept away from production credentials and live RPC write access.
