# Development and verification

## Setup

Use Python 3.12–3.14. `.python-version` selects the 3.14 series for tools that honour
it; it does not install an interpreter.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
ruff check src tests
ruff format --check src tests
python -m pytest -q
python -m build
python -m twine check dist/*
```

On Windows use `py -3.14 -m venv .venv` and `.venv\Scripts\Activate.ps1`.
The package metadata and dependency ranges live in `pyproject.toml`; there is no
`setup.py`. The `src/` layout and existing dataclass builders are retained.

## Tests

Tests block live `requests.Session.request` calls. Simulated HTTP responses and
cookies exercise login/menu fixtures, downloads and a synthetic FEL invoice.
Do not commit real credentials, cookies or invoices.

Coverage includes session isolation, authentication/menu parsing, token bootstrap,
received/issued routing, PDF/XML returns, PDF contingency, HTTP failures, safe
filenames, model parsing and logout cleanup. The composed integration test runs
login through download and logout with simulated HTTP, not a live SAT service.

CI covers Python 3.12–3.14 on Linux and 3.14 on Windows/macOS. Each job checks
lint/format, builds and validates distributions, installs the wheel, runs offline
tests and checks dependencies. To repeat the wheel check after building:

```sh
python -m pip install --force-reinstall --no-deps dist/*.whl
python -m pytest -q
python -m pip check
```

## Manual SAT verification

Use a dedicated account/session and a narrow range containing a known invoice.
Run the README example from a source install using environment credentials. Check
that the result contains the known invoice, open PDF/XML and compare UUID, issuer,
receiver, amount and date with Agencia Virtual. Repeat with an issued invoice and
`received=False`. Confirm browser login after client cleanup. Avoid overlapping
browser/automation sessions and redact evidence before sharing.

This check is necessary before claiming compatibility with SAT's current portal.
Offline tests prove behaviour against recorded/synthetic responses only.

## Releases

Update version/changelog and review the diff. A `v<version>` tag matching
`pyproject.toml` triggers publication only after every CI test job passes. The
release job rebuilds/checks the package, publishes with the existing `PYPI_TOKEN`
repository secret and attaches distributions to a GitHub release. A missing or
invalid token fails publication.

Branches and pull requests do not publish a package. Create release tags only when
publication is intended. Published PyPI versions cannot be overwritten; corrections
require a new version.
