# Third-party notices

## Aderyn 0.6.8

AEGIS includes the Aderyn Solidity static analyzer in the isolated analysis-worker image.

- Project: https://github.com/Cyfrin/aderyn
- Release: https://github.com/Cyfrin/aderyn/releases/tag/aderyn-v0.6.8
- License: GNU General Public License v3.0 (GPL-3.0)
- License text: https://github.com/Cyfrin/aderyn/blob/dev/LICENSE
- The x86_64 Linux release archive is pinned by SHA-256 in `backend/Dockerfile.worker`.

Aderyn is an independent third-party tool. AEGIS does not modify its source. If you redistribute the worker image, review and satisfy the applicable GPL-3.0 source and notice obligations for the Aderyn binary.

## Slither

- Project: https://github.com/crytic/slither
- AEGIS pins the Slither Analyzer Python package version in `backend/Dockerfile.worker`.
- Review the upstream project license and notices before redistributing images.
