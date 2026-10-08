import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from sat_gt_fel_invoices_downloader import SATDownloader

from .conftest import response


@pytest.mark.parametrize(
    "method", ["get_pdf", "get_pdf_content", "get_xml", "get_xml_content", "get_model"]
)
def test_issued_invoice_operation_is_preserved(
    client, session, invoice, method, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    xml = (Path(__file__).parent / "fixtures" / "invoice.xml").read_bytes()
    session.post.return_value = response(xml if method == "get_model" else b"%PDF-test")
    getattr(client, method)(invoice, received=False)
    query = parse_qs(urlparse(session.post.call_args.args[0]).query)
    assert query["tipoOperacion"] == ["E"]


def test_bulk_models_preserve_issued_operation(client, session, invoice, dates):
    session.get.return_value = response(
        json.dumps({"detalle": {"data": [invoice]}}).encode()
    )
    session.post.return_value = response(
        (Path(__file__).parent / "fixtures" / "invoice.xml").read_bytes()
    )
    assert len(client.get_invoices_models(*dates, received=False)) == 1
    assert parse_qs(urlparse(session.post.call_args.args[0]).query)[
        "tipoOperacion"
    ] == ["E"]


def test_pdf_contingency_returns_decoded_content(downloader, session, invoice):
    session.post.side_effect = [
        response(status=500),
        response(json.dumps([base64.b64encode(b"%PDF-fallback").decode()]).encode()),
    ]
    assert downloader.get_pdf_content(invoice) == b"%PDF-fallback"
    assert session.post.call_count == 2


@pytest.mark.parametrize(
    "fallback", [response(status=503), response(b'["bm90IGEgcGRm"]')]
)
def test_pdf_contingency_failures_are_raised(downloader, session, invoice, fallback):
    session.post.side_effect = [response(status=500), fallback]
    with pytest.raises((requests.HTTPError, ValueError)):
        downloader.get_pdf_content(invoice)


@pytest.mark.parametrize(
    "header, expected",
    [
        ('attachment; filename="invoice.pdf"; size=42', "invoice.pdf"),
        ("attachment; filename*=UTF-8''invoice%20copy.pdf", "invoice copy.pdf"),
        ('attachment; filename="../../invoice.pdf"', "invoice.pdf"),
        ('attachment; filename="C:\\temp\\invoice.pdf"', "invoice.pdf"),
        (None, None),
        ("attachment", None),
    ],
)
def test_download_filename(downloader, header, expected):
    assert downloader.get_filename_from_cd(header) == expected


def test_nested_output_directory_is_created(downloader, session, invoice, tmp_path):
    directory = tmp_path / "invoices" / "2026"
    session.post.return_value = response(
        b"%PDF-test",
        headers={"Content-Disposition": 'attachment; filename="../../invoice.pdf"'},
    )
    filename = downloader.get_pdf(invoice, directory)
    assert filename == str(directory / "invoice.pdf")
    assert (directory / "invoice.pdf").read_bytes() == b"%PDF-test"
    assert not (tmp_path / "invoice.pdf").exists()


def test_invalid_date_range_does_not_authenticate(session, dates):
    client = SATDownloader(session)
    with pytest.raises(ValueError, match="start date"):
        client.get_invoices(dates[1], dates[0])
    session.post.assert_not_called()


def test_missing_access_token_has_clear_error(downloader, session, invoice):
    session.cookies.clear()
    with pytest.raises(ValueError, match="ACCESS_TOKEN"):
        downloader.get_xml_content(invoice)
    session.post.assert_not_called()


def test_invoice_data_is_not_printed(client, session, invoice, capsys):
    session.post.return_value = response(b"<invoice/>")
    client.get_xml_content(invoice)
    assert capsys.readouterr().out == ""
