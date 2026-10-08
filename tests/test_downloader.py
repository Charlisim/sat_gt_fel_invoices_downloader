import json
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from sat_gt_fel_invoices_downloader.actions import SATGetStablisments
from sat_gt_fel_invoices_downloader.main import SATDownloader

from .conftest import response


def test_clients_do_not_share_sessions():
    first, second = SATDownloader(), SATDownloader()
    assert first.session is not second.session
    first.session.cookies.set("ACCESS_TOKEN", "first-client")
    assert second.session.cookies.get("ACCESS_TOKEN") is None


def test_public_xml_content_returns_bytes(client, session, invoice):
    session.post.return_value = response(b"<invoice/>")
    assert client.get_xml_content(invoice) == b"<invoice/>"


def test_public_xml_returns_saved_filename(client, session, invoice, tmp_path):
    session.post.return_value = response(b"<invoice/>")
    filename = client.get_xml(invoice, tmp_path)
    assert filename == str(tmp_path / (invoice["numeroUuid"] + ".xml"))
    assert (tmp_path / (invoice["numeroUuid"] + ".xml")).read_bytes() == b"<invoice/>"


def test_pdf_content_defaults_to_received(client, session, invoice):
    session.post.return_value = response(b"%PDF-test")
    assert client.get_pdf_content(invoice) == b"%PDF-test"
    query = parse_qs(urlparse(session.post.call_args.args[0]).query)
    assert query["tipoOperacion"] == ["R"]


def test_establishments_returns_decoded_json(session):
    session.get.return_value = response(json.dumps([{"codigo": 1}]).encode())
    assert SATGetStablisments(session).execute() == [{"codigo": 1}]


def test_xml_server_error_is_not_replaced_by_pdf(downloader, session, invoice):
    session.post.return_value = response(b"server error", status=500)
    with pytest.raises(requests.HTTPError):
        downloader.get_xml_content(invoice)
    assert session.post.call_count == 1


def test_download_http_error_does_not_write_file(
    downloader, session, invoice, tmp_path
):
    session.post.return_value = response(b"not found", status=404)
    with pytest.raises(requests.HTTPError):
        downloader.get_pdf(invoice, tmp_path)
    assert list(tmp_path.iterdir()) == []
