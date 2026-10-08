# API reference

## Client and authentication

`SATDownloader(request_session=None)` creates a separate `requests.Session` unless
one is supplied. The caller owns an injected session: `close()` logs out but does
not close that session. Logout clears its cookies; use a dedicated SAT session.

`SatCredentials(username, password)` is a dataclass. Its repr excludes the password,
but its fields still contain credentials.

| Method | Return | Behaviour |
| --- | --- | --- |
| `set_credentials(credentials)` | `SATDownloader` | Set credentials before initialization. Log out before changing credentials during an active session. |
| `setCredentials(credentials)` | `SATDownloader` | Legacy alias for `set_credentials()`. |
| `initialize()` | `None` | Login, parse the FEL menu and open its link to obtain `ACCESS_TOKEN`. Called lazily. |
| `logout()` | `None` | Log out and clear local authentication even on failure. Repeated logout without an active session makes no request. |
| `close()` | `None` | Log out and close an internally created HTTP session. |

The context manager provides cleanup. If a body error and a network logout error
both occur, the body error is preserved. Otherwise logout errors propagate.
Initialization failures after successful login attempt logout.

## Queries

| Method | Return |
| --- | --- |
| `get_invoices(date_start, date_end, received=True)` | SAT invoice header dictionaries |
| `get_invoices_with_filters(filters)` | SAT invoice header dictionaries |
| `get_invoices_models(date_start, date_end, received=True)` | `list[Invoice]` |
| `get_establishments()` | Decoded JSON from SAT's establishment catalogue |
| `get_stablisments()` | Legacy alias for `get_establishments()` |

Pass `datetime.date` values for dates. Reversed ranges raise `ValueError` before
any authentication request. Dates are sent as `DD-MM-YYYY`. SAT determines range
limits and result completeness. There is no pagination, splitting, caching or
general retry policy.

`SATFELFilters(establecimiento, estadoDte, fechaInicio, fechaFin, tipo)` retains its
legacy constructor and field names. `establecimiento` currently has no effect.

## Individual invoices

| Method | Return | Disk effect |
| --- | --- | --- |
| `get_pdf(invoice, save_in_dir=None, received=True)` | Filename as `str` | Writes to the directory or current working directory. |
| `get_pdf_content(invoice, save_in_dir=None, received=True)` | `bytes` | None; `save_in_dir` remains an unused compatibility parameter. |
| `get_xml(invoice, save_in_dir=None, received=True)` | `bytes` without a directory; filename `str` with one | Writes only when a directory is supplied. |
| `get_xml_content(invoice, received=True)` | `bytes` | None |
| `get_model(invoice, received=True)` | `Invoice` | None |

Use `received=False` consistently for issued invoices. Headers do not carry a
library-managed direction. Directories accept strings or `pathlib.Path`.
Downloads overwrite same-name files.

PDF requests returning HTTP 500 try the legacy public PDF contingency endpoint.
This retains the legacy `estado="V"` request field and is not verified for cancelled
invoices. XML requests never use this PDF fallback.

## Models

Import `Invoice`, `InvoiceHeaders`, `InvoiceLine`, `InvoiceTotals`, `TotalTax`,
`IssuingModel`, `ContactModel` and `Address` from
`sat_gt_fel_invoices_downloader.models`. Existing builder methods remain.

Issue dates are `datetime`, preserving supplied timezones. Postal codes are strings,
monetary fields are floats and optional emails are strings or `None`. The receiver
address retains the legacy `"CIUDAD"` placeholder. Parsing targets certified FEL
XML with `DatosEmision` and `Certificacion`; there is no schema validation or
normalization of every document variant.
