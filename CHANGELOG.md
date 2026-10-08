# Changelog

## 0.6.0 — Unreleased

### Compatibility

- Require Python 3.12+. Drop Python 3.7–3.11 support.
- Move metadata to `pyproject.toml`, correct repository links and update Requests,
  Beautiful Soup and lxml dependency ranges.
- Add CI for Python 3.12–3.14 and Windows/macOS on 3.14. Gate tagged publication
  on the full matrix, wheel installation tests and distribution metadata checks.

### Fixes and additions

- Isolate HTTP sessions and add context-manager/`close()` cleanup.
- Return XML bytes/saved filenames from public XML methods.
- Correct received PDF routing and propagate `received=False` through individual
  download/model methods and bulk model parsing.
- Return decoded establishment JSON. Add `get_establishments()` and
  `set_credentials()` while retaining legacy aliases.
- Bootstrap the FEL access token during initialization and parse JSF responses explicitly.
- Raise HTTP errors before writing files. Restrict contingency to PDFs and validate
  its HTTP status and decoded PDF signature.
- Create output directories and remove directory components from response filenames.
- Correct ISO dates, issuer street text, email attributes and numeric tax totals.
- Remove invoice/session debug prints and hide passwords in credential repr.

### Migration

Existing query signatures, model builders and `setCredentials()` /
`get_stablisments()` aliases remain. Pass `received=False` to individual methods
for issued invoices. Use a context manager or call `close()` after operations.

`get_xml()` now returns XML bytes without a directory and a saved filename with
one, replacing an accidental `None`. HTTP failures raise `requests` exceptions;
reversed ranges raise `ValueError`. Log out before changing active credentials.
Resolved model types now reflect parsed data: `datetime` dates, string postal
codes and nullable emails.

Users needing Python below 3.12 must upgrade their interpreter before installing
0.6.0. SAT endpoints, pagination and cancelled-invoice contingency support still
require external/manual verification.
