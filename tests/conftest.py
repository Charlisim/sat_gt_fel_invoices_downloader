from datetime import date
from unittest.mock import Mock

import pytest
import requests

from sat_gt_fel_invoices_downloader.main import SATDownloader, SatFelDownloader
from sat_gt_fel_invoices_downloader.models import SatCredentials


@pytest.fixture(autouse=True)
def prevent_live_requests(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not contact live services")

    monkeypatch.setattr(requests.Session, "request", blocked)


@pytest.fixture
def session():
    session = Mock(spec=requests.Session)
    session.cookies = requests.cookies.RequestsCookieJar()
    session.cookies.set("ACCESS_TOKEN", "test-token")
    return session


@pytest.fixture
def invoice():
    return {
        "numeroUuid": "11111111-1111-1111-1111-111111111111",
        "nitEmisor": "11111111",
        "nitReceptor": "22222222",
        "granTotal": 112,
    }


@pytest.fixture
def downloader(session):
    return SatFelDownloader(
        SatCredentials("test-user", "test-password"),
        "https://example.test/fel",
        session,
    )


@pytest.fixture
def client(session):
    client = SATDownloader(session)
    client.setCredentials(SatCredentials("test-user", "test-password"))
    client.its_initialized = True
    client.url_get_fel = "https://example.test/fel"
    return client


@pytest.fixture
def dates():
    return date(2026, 1, 1), date(2026, 1, 31)


def response(content=b"", status=200, headers=None):
    result = requests.Response()
    result.status_code = status
    result._content = content
    result.headers.update(headers or {})
    result.url = "https://example.test/response"
    return result
