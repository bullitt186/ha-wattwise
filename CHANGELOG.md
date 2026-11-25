# Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer](https://semver.org/).

## [Unreleased]

### Changed

- Contributing: one setup for people and coding agents from
  [repo-kit](https://github.com/bullitt186/repo-kit). `CONTRIBUTING.md` has the Definition of Done
  every pull request is reviewed against, `docs/SCOPE.md` says what belongs in the project, and
  feature work starts from an issue the maintainer has labelled `accepted`. New checks on pull
  requests: `PR hygiene`, a secret scan and dependency review. Nothing changes for users of the app.
- Contributing: an offline test suite (pytest, `tests/`) covers the consumption, Solcast and EPEX
  Spot forecasts and the constraints of the battery optimisation. CI runs it and the linters in
  pinned versions (`requirements-dev.txt`, `scripts/check.sh`); the Ruff settings in
  `pyproject.toml` now take effect. Only docstrings changed in `wattwise.py`; nothing changes for
  users of the app.
- Contributing: CI type-checks `wattwise.py` with mypy (strict, except for the methods that are
  not annotated yet), and a weekly mutation run (mutmut) reports how well the tests catch changes;
  `scripts/mutate.sh` runs it locally. Only type annotations and one local variable name changed in
  `wattwise.py`; nothing changes for users of the app.
