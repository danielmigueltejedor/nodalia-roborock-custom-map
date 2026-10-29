# Agent instructions — nodalia-roborock-custom-map

## Repository-specific deterministic quality contract (2026-10-26)

**Project:** Home Assistant custom component for Roborock map rendering.

**Engineering requirements:** Never break manifest metadata, entity lifecycle, locale and map data fallback; do not assume physical vacuum availability in CI.

**Verification commands:** python -m compileall -q custom_components; validate hacs.json and each manifest.json.

Run relevant tests and give actual outputs, including failures. Add regression coverage for behavior, edges and error paths. Never weaken/delete/skip tests, suppress errors or reduce thresholds solely to get CI green. Changes to this file, `QUALITY_GATES.md`, workflows and test policy require human review. Make the `quality` check required on protected branches. Disclose missing system dependencies. Preserve existing instructions.
