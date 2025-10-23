# DocStyle Guide

This guide defines the documentation rules enforced by `scripts/ci/check_docs.py`.

## Title conventions
- Each markdown file starts with a stable `#` heading.
- H1 titles **must not** include delivery phases or transient project codes.

## Footer contract
- The final line of every doc is the exact footer: `Doc last updated: 2025-10-22 (v0.9.5)`.
- Do not append extra whitespace or commentary after the footer.

## Environment source of truth
- Reference environment variables exclusively through [`docs/ops/Config.md`](../ops/Config.md#environment-keys).
- `.env.example` must contain the same key set as the Config table (order may differ).

## Index discipline
- [`docs/README.md`](../README.md) lists every markdown file in the tree.
- When adding a new document, update the index in the same change.

## Automation
- Run `python scripts/ci/check_docs.py` (or `make docs-check`) before opening a PR.
- The checker validates title rules, footers, index coverage, ENV parity, and in-doc links.

Doc last updated: 2025-10-22 (v0.9.5)
