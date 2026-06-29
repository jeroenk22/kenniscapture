## Wat veranderd er?

<!-- Beschrijf bondig wat je hebt gedaan en waarom -->

## Type wijziging

- [ ] `feat:` Nieuwe functionaliteit
- [ ] `fix:` Bugfix
- [ ] `chore:` Onderhoud / tooling
- [ ] `docs:` Documentatie
- [ ] `refactor:` Refactoring

## Pre-PR checklist

### Python (backend)
- [ ] `ruff check backend/` → 0 errors
- [ ] `ruff format --check backend/` → 0 diffs
- [ ] `pytest --cov --cov-fail-under=90` → geslaagd

### TypeScript (chatbot_ui)
- [ ] `pnpm biome check .` → 0 errors
- [ ] `pnpm typecheck` → geen fouten
- [ ] `pnpm test:coverage` → drempel gehaald

## Gerelateerde issues

<!-- Sluit: #123 -->
