from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import get_type_hints

import pytest

from sat_gt_fel_invoices_downloader.models import InvoiceHeaders, SatCredentials

from .conftest import response

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-01-15T10:30:00-06:00",
        "2026-01-15T10:30:00.123-06:00",
        "2026-01-15T10:30:00",
        "2026-01-15T10:30:00.123",
        "2026-01-15T16:30:00Z",
    ],
)
def test_parse_fel_invoice(downloader, session, invoice, timestamp):
    xml = (
        (FIXTURES / "invoice.xml")
        .read_text()
        .replace("2026-01-15T10:30:00-06:00", timestamp)
    )
    session.post.return_value = response(xml.encode())
    model = downloader.get_invoice_model(invoice)
    assert model.headers.issue_date == datetime.fromisoformat(timestamp)
    assert model.headers.issuer.address.street == "Example Street 1"
    assert model.headers.issuer.address.zip_code == "01001"
    assert model.headers.issuer.email == "issuer@example.test"
    assert model.headers.receiver.email == "receiver@example.test"
    assert model.lines[0].quantity == 2
    assert model.lines[0].total == 112
    assert model.totals.total_taxes[0].tax_total == 12.0
    assert model.totals.grand_total == 112.0
    assert model.fel_signature == invoice["numeroUuid"]
    assert asdict(model)["headers"]["issuer"]["address"]["street"] == "Example Street 1"


def test_optional_email_attributes(downloader, session, invoice):
    xml = (FIXTURES / "invoice.xml").read_text()
    xml = xml.replace(' CorreoEmisor="issuer@example.test"', "").replace(
        ' CorreoReceptor="receiver@example.test"', ""
    )
    session.post.return_value = response(xml.encode())
    model = downloader.get_invoice_model(invoice)
    assert model.headers.issuer.email is None
    assert model.headers.receiver.email is None


def test_issue_date_type_can_be_resolved():
    assert get_type_hints(InvoiceHeaders)["issue_date"] is datetime


def test_credentials_repr_hides_password():
    assert "private-password" not in repr(
        SatCredentials("test-user", "private-password")
    )


def test_invalid_xml_has_clear_error(downloader, session, invoice):
    session.post.return_value = response(b"<error/>")
    with pytest.raises(ValueError, match="DatosEmision"):
        downloader.get_invoice_model(invoice)
