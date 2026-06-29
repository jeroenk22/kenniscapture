# Git & GitHub Best Practices

## Branch strategie
- `main` — altijd stabiel, protected, nooit direct committen
- `develop` — integratiebranch, protected, alle tests moeten slagen voor merge
- `feature/xxx`, `fix/xxx`, `chore/xxx` — werkt altijd vanuit develop

## Branch protection: main
Stel in via GitHub → Settings → Branches → Add rule voor `main`:
- ✅ Require a pull request before merging
- ✅ Require status checks to pass → selecteer: `test`
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings

## Branch protection: develop
Stel in via GitHub → Settings → Branches → Add rule voor `develop`:
- ✅ Require a pull request before merging
- ✅ Require status checks to pass → selecteer: `test`
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings

## Pre-PR checklist — verplicht voordat je een PR aanmaakt

### Python
```bash
ruff check .            # moet 0 errors teruggeven
ruff format --check .   # moet 0 diffs teruggeven
pytest --cov --cov-fail-under=90
```

### JavaScript / TypeScript
```bash
pnpm biome check .
pnpm test:coverage
```

## Commit conventies (Conventional Commits)
- `feat:` nieuwe functionaliteit
- `fix:` bugfix
- `chore:` onderhoud, tooling, dependencies
- `docs:` documentatie
- `test:` toevoegen of aanpassen van tests
- `refactor:` code herstructurering zonder gedragswijziging

## Regels
- Nooit force-pushen naar main of develop
- PR beschrijving altijd invullen met wat er veranderd is en waarom
- Zorg dat de CI groen is vóórdat je een reviewer vraagt
