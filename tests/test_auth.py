from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from sat_gt_fel_invoices_downloader import SatCredentials, SATDownloader
from sat_gt_fel_invoices_downloader.actions import SATDoLogin, SATGetMenu

from .conftest import response

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "filename, expected", [("valid_login.html", True), ("invalid_login.html", False)]
)
def test_login_from_existing_fixture(session, filename, expected):
    session.post.return_value = response((FIXTURES / filename).read_bytes())
    success, view_state = SATDoLogin(
        SatCredentials("test-user", "test-password"), session
    ).execute()
    assert success is expected
    assert bool(view_state) is expected


def test_menu_partial_response(session, capsys):
    session.post.return_value = response((FIXTURES / "valid_get_menu.xml").read_bytes())
    success, url = SATGetMenu(session, "test-view-state").execute()
    assert success is True
    assert "dte-consulta" in url
    assert capsys.readouterr().out == ""


def test_missing_menu_is_reported(session):
    session.post.return_value = response(b"<html><body>Maintenance</body></html>")
    assert SATGetMenu(session, "test-view-state").execute() == (False, None)


def test_lazy_full_download_and_logout(session, invoice, dates, tmp_path):
    """Compose login, JSF menu, token bootstrap, invoice query, download and logout."""
    session.cookies.clear()
    session.post.side_effect = [
        response((FIXTURES / "valid_login.html").read_bytes()),
        response((FIXTURES / "valid_get_menu.xml").read_bytes()),
        response(b"<invoice/>"),
        response(),
        response(),
    ]

    def get(url, **kwargs):
        if "dte-consulta" in url:
            session.cookies.set("ACCESS_TOKEN", "fresh-token")
            return response()
        return response(b'{"detalle":{"data":[{"numeroUuid":"test-invoice"}]}}')

    session.get.side_effect = get
    with SATDownloader(session) as client:
        client.set_credentials(SatCredentials("test-user", "test-password"))
        headers = client.get_invoices(*dates)
        assert headers == [{"numeroUuid": "test-invoice"}]
        filename = client.get_xml(invoice, tmp_path)
        assert Path(filename).read_bytes() == b"<invoice/>"
        assert client.its_initialized is True
    assert client.its_initialized is False
    assert client.view_state is None
    assert client.url_get_fel is None
    assert not session.cookies
    assert session.post.call_count == 5
    session.close.assert_not_called()


def test_logout_failure_still_resets_state(client, session):
    session.post.return_value = response(status=503)
    with pytest.raises(requests.HTTPError):
        client.logout()
    assert not client.its_initialized
    assert not session.cookies
    assert session.post.call_count == 2


def test_context_manager_preserves_original_error(client, session):
    session.post.return_value = response(status=503)
    with pytest.raises(RuntimeError, match="original failure"):
        with client:
            raise RuntimeError("original failure")


def test_owned_session_is_closed():
    with patch("sat_gt_fel_invoices_downloader.main.requests.Session") as session_class:
        with SATDownloader():
            pass
        session_class.return_value.close.assert_called_once()


def test_rejected_credentials_do_not_mark_client_initialized(session):
    session.post.return_value = response((FIXTURES / "invalid_login.html").read_bytes())
    client = SATDownloader(session).setCredentials(
        SatCredentials("test-user", "test-password")
    )
    with pytest.raises(ValueError, match="login failed"):
        client.initialize()
    assert not client.its_initialized
    assert session.post.call_count == 1


def test_credentials_cannot_change_during_active_session(client):
    with pytest.raises(ValueError, match="Log out"):
        client.set_credentials(SatCredentials("another-user", "another-password"))


def test_missing_bootstrap_token_logs_out_and_clears_state(session):
    session.cookies.clear()
    session.post.side_effect = [
        response((FIXTURES / "valid_login.html").read_bytes()),
        response((FIXTURES / "valid_get_menu.xml").read_bytes()),
        response(),
        response(),
    ]
    session.get.return_value = response()
    client = SATDownloader(session).set_credentials(
        SatCredentials("test-user", "test-password")
    )
    with pytest.raises(ValueError, match="ACCESS_TOKEN"):
        client.initialize()
    assert not client.its_initialized
    assert client.view_state is None
    assert client.url_get_fel is None
    assert session.post.call_count == 4


def test_repeated_logout_has_no_remote_request(client, session):
    session.post.return_value = response()
    client.logout()
    client.logout()
    assert session.post.call_count == 2
