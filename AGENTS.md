# AGENTS.md

<!-- repo-kit:begin v2 (managed, do not edit; https://github.com/bullitt186/repo-kit) -->
## How to work in this repository (all coding agents)

This block is shared by all repositories of this maintainer and kept in sync by
[repo-kit](https://github.com/bullitt186/repo-kit). Repository-specific
instructions follow below it. They add detail; where they contradict this block,
this block wins, unless an ADR in `docs/adr/` records the exception.

A pull request that follows this block passes review without rework. The
maintainer reviews against the same rules: the **Definition of Done** in
`CONTRIBUTING.md`.

### Build the right thing

1. Read this file to the end, `CONTRIBUTING.md`, `docs/SCOPE.md` and the
   architecture decision records in `docs/adr/` (start with `docs/adr/README.md`).
   An *Accepted* ADR and the scope are binding. If your change needs a different
   decision, write a new ADR that supersedes the old one, in the same pull request.
2. Work from an issue. A feature or behaviour change needs an issue the maintainer
   has labelled `accepted`; if there is none, open one, describe the problem (not
   only the solution) and wait. Only a **small fix** may skip the issue: it repairs
   documented behaviour, changes fewer than about 50 lines of code, and adds no
   dependency, interface, setting or file format.
3. Build what the issue asks for and nothing else. Ideas you have on the way become
   a new issue, not part of this pull request. No reformatting, renaming or
   refactoring that the change does not need.
4. Prefer the smallest complete change: reuse what the repository already has
   (helpers, patterns, dependencies) before adding anything; no new dependency for
   a few lines. Fix the root cause, not the symptom.
5. Never guess protocol values, API fields or hardware behaviour. Take them from a
   source and name it; mark anything unconfirmed as an assumption.

### Design first

Write the design down before the code: the behaviour that changes, the modules
and interfaces involved, and how it is tested. Put it in the issue or the pull
request description; for a small change the commit message is enough.

Write an ADR (`docs/adr/`, see its README) when the change:

- adds, removes or replaces a runtime dependency or external service,
- changes a public interface: API, CLI, configuration keys, file or data formats,
  entity or topic names, anything users or other systems rely on,
- changes the architecture: module boundaries, data flow, persistence, threading,
- sets a security, privacy or compatibility rule,
- reverses or replaces an earlier ADR, or changes `docs/SCOPE.md`.

Bug fixes and refactorings inside existing decisions need no ADR.

### Tests

Design the test cases from the specification, then implement the change together
with them. A one-test-at-a-time red/green cycle is not required.

- A bug fix starts with a regression test that reproduces the bug. Run it and
  confirm it fails **for the reason the bug describes**, not because of a build,
  import or signature error. Then fix the bug and commit the test with the fix.
- Expected values come from the specification: documentation, a protocol table,
  a manual, the issue, or a recorded real payload. Never from running the code
  under test and copying its output; such a test only proves the code does what
  it does.
- Assert observable results (output, state, sent request, raised error), not only
  that something was called.
- Tests are fast, deterministic and offline. A flaky test is a bug to fix, not to
  re-run.
- Changing an expected value in an existing test needs a reason in the commit
  message that names the source of the new value.
- Coverage shows what ran, not whether a test notices a wrong result. Run mutation
  testing on every line your change touches, including the callers you edited,
  not only new functions (see Commands below); kill a surviving mutant
  with a test, or say in the pull request why it is equivalent. Without a
  mutation tool, mutate by hand: for each changed branch or condition, break it
  (invert, drop, return a constant), run the tests, revert, and list each mutant
  with its result in the pull request. Reasoning about mutants without running
  them does not count.
- Do not weaken lint rules, thresholds or checks to make a change pass; fix the
  code. A justified exception gets a comment next to it and a note in the commit
  message. Thresholds are only ever raised.

### Documentation

Documentation changes in the same pull request as the behaviour it describes:
README, `docs/`, configuration examples, the ADRs and `CHANGELOG.md`. Outdated
documentation counts as a bug. Relative links in Markdown must point to files
that exist.

Changelog entries go under `[Unreleased]`, in the Keep a Changelog sections in
this order: Added, Changed, Deprecated, Removed, Fixed, Security. Write them for the user of the
project: what changes for them and what they have to do, not which functions
moved. A breaking change gets an entry under "Upgrade notes" with the steps.
Name outside contributors and link their issue or pull request: write the issue
reference with your entry (on GitHub a link; on Forgejo the bare `#N`, because a
link would put the forge's host name into the repository), and add your handle and the pull request link to it as soon
as the pull request exists. Releases, tags
and version numbers are the maintainer's
([release standard](https://github.com/bullitt186/repo-kit/blob/main/docs/RELEASING.md)).

### Commits and branches

- One branch per topic from the current default branch; never commit to the
  default branch. Agents working in parallel use their own git worktree; never
  run checkout, switch, reset, stash or clean in a checkout someone else uses.
- Commit each completed step with a Conventional Commits message (`feat:`,
  `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `ci:`); the body says why.
  Code, comments, commit messages and pull requests are in English.
- Reference the issue: `Closes #N` on GitHub; `Refs #N` on Forgejo, which closes
  an issue as soon as a commit with `Closes` is pushed.
- Never commit or push on red; never use `--no-verify` or skip hooks; treat every
  hook finding as work to do.

### Before you open the pull request

- Run the repository's **fast check** before every commit and the **full check**
  when your change can affect what it covers (see Commands below). Both must pass.
- Merge or rebase onto the current default branch and run the checks again.
- Fill in the pull request template completely; tick only what you did and say
  why anything stays unticked.
- After pushing, watch CI yourself. A red check on your pull request is your work,
  also when it looks unrelated.
- No secrets, tokens, personal data, local paths, host names or IP addresses in
  code, tests, fixtures, logs, commits or pull request text.

### Continuous integration

CI follows the repo-kit [CI standard](https://github.com/bullitt186/repo-kit/blob/main/docs/CI_STANDARD.md):
tests, lint and format, type check, build, secret scan, dependency review, static
analysis and `PR hygiene`. PR hygiene fails when code changes come without a test
change or a `CHANGELOG.md` entry, when `docs/SCOPE.md` changes without an ADR,
when an ADR is malformed or missing from the index, when a changed Markdown file
has a broken relative link, when code from an outside contributor links no issue,
or when a pull request changes more than about 800 lines of code and tests. Only
the maintainer can waive a rule (labels `no-test-change`, `skip-changelog`,
`large-change`). Do not ask for a waiver when a test, entry or split is possible.

### Respect

Do not change CI configuration, branch protection, release workflows, licence,
`docs/SCOPE.md` or this block unless the issue asks for it. Maintainer decisions
recorded in issues and ADRs are not up for silent change.
<!-- repo-kit:end -->

## This repository

### Purpose

Scope and non-goals: [docs/SCOPE.md](docs/SCOPE.md).

WattWise is an AppDaemon app for Home Assistant that plans when a home battery charges from the
grid or the sun and when it discharges to the house. Every 15 minutes it builds consumption,
solar and price forecasts from Home Assistant sensors, solves a linear program (PuLP with the CBC
solver) over a 48-hour horizon and writes the plan back to Home Assistant entities. Users run it
in the AppDaemon add-on; see the [README](README.md).

### Layout

| Path | Content |
|---|---|
| `wattwise.py` | the whole app: class `WattWise(hass.Hass)`, forecasts, optimisation, Home Assistant updates |
| `apps.yaml` | example AppDaemon configuration (settings and entity IDs, placeholders only) |
| `wattwise.yaml` | Home Assistant package with the helper entities and template sensors the app uses |
| `example_automation_*.yaml`, `wattwise-history-forecast-chart.yaml`, `configuration.yaml` | examples for battery control automations, the ApexCharts card and the HA configuration |
| `images/` | screenshots for the README |
| `.github/workflows/` | CI: `lint.yml` (Ruff, Black, yamllint), `tests.yml` (pytest, mypy), `mutation.yml` (weekly mutmut, reporting only) |
| `tests/` | pytest suite; `conftest.py` replaces AppDaemon's `hass.Hass` with a stub, so the tests run offline |
| `scripts/` | `check.sh` (fast and full check), `mutate.sh` (mutation testing), `agent-stop-check.sh` (stop hook) |
| `docs/` | scope and architecture decisions |

### Commands

| Task | Command |
|---|---|
| Install / set up | Python 3.11 or newer and [uv](https://docs.astral.sh/uv/) (`scripts/check.sh` runs the linters of `requirements-dev.txt` through uv without installing them); running the app needs AppDaemon, `pulp`, `numpy`, `tzlocal` and the CBC solver, see the README |
| Fast check (before every commit, also the stop hook) | `scripts/check.sh` (Ruff, Black in check mode, yamllint, mypy and the pytest suite; the versions of `requirements-dev.txt`, as in CI) |
| Full check | `scripts/check.sh`; CI also runs the tests on Python 3.12 and 3.13 |
| Mutation testing of changed code | `scripts/mutate.sh` (mutmut on `wattwise.py` when it changed against `origin/main`; `scripts/mutate.sh --results` lists survivors) |

### Rules specific to this repository

- Tell AppDaemon code from Home Assistant code and follow each one's own API. Use only methods
  and functions from the official [AppDaemon](https://appdaemon.readthedocs.io/en/latest/) and
  Home Assistant documentation.
- Match the style, structure and conventions of `wattwise.py`; log through AppDaemon's logging.
- Example files (`apps.yaml`, `wattwise.yaml`, the example automations) are what users copy:
  keep them in sync with the settings and entity IDs the code reads, and keep placeholders such as
  `<your-token>` instead of real values.
- Expected sensor formats come from the integrations the app reads (Solcast, EPEX Spot, as linked
  in the README); never guess a payload field.
- Tests replace AppDaemon with the stub in `tests/conftest.py` and freeze the clock; add the
  AppDaemon methods a change needs to `FakeHass`, with the signature from the AppDaemon docs.
  Expected sensor values in tests follow the formats of the integrations (Solcast
  `detailedForecast`, the EPEX Spot data that `wattwise.yaml` turns into `today`/`tomorrow`).
- Type check: `[tool.mypy]` in `pyproject.toml` is strict except for untyped methods (annotate
  a method when you change it) and the AppDaemon base class, which is not installed for the
  checks.
