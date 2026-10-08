# Guatemala SAT FEL invoice downloader

A Python library for querying received and issued FEL (Factura Electrónica en Línea)
invoices in Guatemala's SAT Agencia Virtual. Download PDF/XML files or parse FEL
XML into Python dataclasses.

Requires **Python 3.12 or newer**. The compatibility matrix covers CPython
**3.12, 3.13 and 3.14**, with Windows/macOS checks on 3.14.
Python 3.14 is recommended. Python 3.15 prereleases and free-threaded builds
are not part of the compatibility matrix.

This independent project uses SAT's web login and FEL endpoints. Changes to SAT
pages, authentication or response formats can break the integration. Automated
tests run offline and do not establish that the current SAT portal works.

## Installation

Use a virtual environment. On macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install sat_gt_fel_invoices_downloader
```

On Windows PowerShell:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install sat_gt_fel_invoices_downloader
```

The PyPI command installs the latest **published** release. To use these changes
before 0.6.0 is published, install from source:

```sh
git clone https://github.com/Charlisim/sat_gt_fel_invoices_downloader.git
cd sat_gt_fel_invoices_downloader
# Check out the branch or tag containing the version you want.
python -m pip install .
```

## Download received invoices

Set `SAT_USERNAME` and `SAT_PASSWORD` in your process environment using your
preferred secret manager. These are your SAT Agencia Virtual credentials.
The library does not load `.env` files automatically.

```python
import os
from datetime import date
from pathlib import Path

from sat_gt_fel_invoices_downloader import SATDownloader, SatCredentials

credentials = SatCredentials(os.environ["SAT_USERNAME"], os.environ["SAT_PASSWORD"])
output_dir = Path.home() / "Downloads" / "sat-fel"

with SATDownloader() as sat:
    sat.set_credentials(credentials)
    invoices = sat.get_invoices(date(2026, 1, 1), date(2026, 1, 31), received=True)
    for invoice in invoices:
        pdf_path = sat.get_pdf(invoice, save_in_dir=output_dir)
        xml_path = sat.get_xml(invoice, save_in_dir=output_dir)
        print(pdf_path, xml_path)
```

Authentication happens on the first operation. The context manager logs out and
closes the HTTP session when the block ends. Without it, call `sat.close()` in a
`finally` block. Each downloader creates its own session; do not share a downloader
between concurrent workers.

Output directories are created as needed. Filenames come from the server, with
directory components removed, or fall back to `<numeroUuid>.pdf` / `.xml`.
Existing same-name files are overwritten.

## Download issued invoices

Pass `received=False` to **both** the query and each download/model operation:

```python
with SATDownloader() as sat:
    sat.set_credentials(credentials)
    invoices = sat.get_invoices(date(2026, 1, 1), date(2026, 1, 31), received=False)
    for invoice in invoices:
        sat.get_pdf(invoice, output_dir, received=False)
        sat.get_xml(invoice, output_dir, received=False)
```

Invoice dictionaries are the headers returned by `get_invoices()`. Pass them
unchanged to download methods rather than constructing them manually.

## Read content or structured models

```python
from dataclasses import asdict

with SATDownloader() as sat:
    sat.set_credentials(credentials)
    invoices = sat.get_invoices(date(2026, 1, 1), date(2026, 1, 31))
    for invoice in invoices:
        pdf_bytes = sat.get_pdf_content(invoice)
        xml_bytes = sat.get_xml_content(invoice)
        model = sat.get_model(invoice)
        print(model.headers.issue_date, model.totals.grand_total)
        invoice_dict = asdict(model)
```

Models contain headers, issuer/receiver details, lines, totals and certification.
They retain legacy floating-point monetary fields; use decimal-based values in
your accounting layer when exact arithmetic is required. `asdict()` preserves
`datetime` values rather than converting them into JSON-ready strings.
Bulk parsing is available through `get_invoices_models(start, end, received=True)`.

## Filters

```python
from sat_gt_fel_invoices_downloader.models import EstadoDTE, SATFELFilters, TypeFEL

filters = SATFELFilters(
    establecimiento=0,
    estadoDte=EstadoDTE.VIGENTES,
    fechaInicio=date(2026, 1, 1),
    fechaFin=date(2026, 1, 31),
    tipo=TypeFEL.RECIBIDA,
)

with SATDownloader() as sat:
    sat.set_credentials(credentials)
    invoices = sat.get_invoices_with_filters(filters)
    establishments = sat.get_establishments()
```

`EstadoDTE` supports `TODOS`, `VIGENTES` and `ANULADAS`. The legacy
`establecimiento` field is retained but is not sent to the current query endpoint.
Results are SAT's `detalle.data`; the library does not implement pagination or
automatic date-window splitting.

See the [API reference](docs/api.md), [migration notes](CHANGELOG.md) and
[contributor guide](docs/development.md).

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Unsupported Python | Use Python 3.12–3.14. |
| Login fails | Check Agencia Virtual credentials/access. A changed SAT login page can produce the same error. |
| FEL menu or `ACCESS_TOKEN` missing | Check account FEL access; SAT may have changed its menu/authentication flow. |
| HTTP 401/403 | End the session and retry with a new downloader after checking account access. |
| Timeout or HTTP 5xx | Check SAT availability. Requests use a 20-second timeout with no general automatic retries. |
| XML returns HTTP 500 | The error propagates. Only PDF requests use the legacy PDF contingency endpoint. |
| Empty result | Check dates, issued/received direction and invoice state. |

HTTP/network errors propagate as `requests` exceptions. Invalid dates, missing
authentication state and invalid FEL data can raise `ValueError`. Failed HTTP
responses are not written to disk. PDF contingency decoding checks the `%PDF`
signature; normal successful downloads are returned as supplied by SAT.

Keep credentials, cookies, token-bearing URLs and downloaded invoices out of
logs and version control. Use redacted samples in bug reports.

## License

GNU General Public License v3. See [LICENSE](LICENSE).
