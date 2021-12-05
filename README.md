# FEL Invoices Downloader for SAT of Guatemala

Downloads received and emited invoices in FEL (Factura En Linea) of Guatemala SAT

## How to use it

### Installation

`pip install sat_gt_fel_invoices_downloader`


### Example

#### How to download invoice in PDF

```python
from sat_gt_fel_invoices_downloader import SATDownloader
import datetime
import os.path
from sat_gt_fel_invoices_downloader.models import SatCredentials


sat_credentials = SatCredentials("YOUR AGENCIA DIGITAL USER", "YOUR AGENCIA DIGITAL PASSWORD")
sat = SATDownloader()
sat.setCredentials(credentials=sat_credentials)
invoices = sat.get_invoices(
    datetime.date(2021, 10, 1), date_end=datetime.date.today(), received=True
)
dir = os.path.dirname(
    'c:\\Users\\my-user\\Downloads\\"'
)
for invoice in invoices:
    sat.get_pdf(invoice, save_in_dir=dir)
```
#### How to download invoice in XML

```python
from sat_gt_fel_invoices_downloader import SATDownloader
import datetime
import os.path
from sat_gt_fel_invoices_downloader.models import SatCredentials


sat_credentials = SatCredentials("YOUR AGENCIA DIGITAL USER", "YOUR AGENCIA DIGITAL PASSWORD")
sat = SATDownloader()
sat.setCredentials(credentials=sat_credentials)
invoices = sat.get_invoices(
    datetime.date(2021, 10, 1), date_end=datetime.date.today(), received=True
)
dir = os.path.dirname(
    'c:\\Users\\my-user\\Downloads\\"'
)
for invoice in invoices:
    sat.get_xml(invoice, save_in_dir=dir)
```

#### How to get invoices in model structure

```python
from sat_gt_fel_invoices_downloader import SATDownloader
import datetime
import os.path
from sat_gt_fel_invoices_downloader.models import SatCredentials


sat_credentials = SatCredentials("YOUR AGENCIA DIGITAL USER", "YOUR AGENCIA DIGITAL PASSWORD")
sat = SATDownloader()
sat.setCredentials(credentials=sat_credentials)
invoices = sat.get_invoices(
    datetime.date(2021, 10, 1), date_end=datetime.date.today(), received=True
)
dir = os.path.dirname(
    'c:\\Users\\my-user\\Downloads\\"'
)
for invoice in invoices:
    print(sat.get_model(invoice))
```