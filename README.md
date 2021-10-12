# FEL Invoices Downloader for SAT of Guatemala

Downloads received and emited invoices in FEL (Factura En Linea) of Guatemala SAT

## How to use it

### Installation

`pip install sat_gt_fel_invoices_downloader`


### Example

```python

sat_credentials = SatCredentials("YOUR AGENCIA DIGITAL USER", "YOUR AGENCIA DIGITAL PASSWORD")
sat = SatFelDownloader(sat_credentials)
sat._login()
sat._get_queries_menu()
invoices = sat.get_invocies(
    datetime.date(2021, 10, 1), date_end=datetime.date(2021, 10, 30)
)
dir = os.path.dirname(
    'c:\\Users\\my-user\\Downloads\\"'
)
for invoice in invoices:
    sat.get_pdf(invoice, save_in_dir=dir, received=True)

```