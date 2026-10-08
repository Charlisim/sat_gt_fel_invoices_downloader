import logging
import re

from bs4 import BeautifulSoup

TIMEOUT = 20
logger = logging.getLogger(__name__)


def auth_headers(session):
    token = session.cookies.get("ACCESS_TOKEN")
    if not token:
        raise ValueError("SAT did not provide an ACCESS_TOKEN; authenticate again")
    return {"authtoken": "token " + token}


class SATDoLogin:
    def __init__(self, credentials, request_session):
        self._credentials = credentials
        self._session = request_session
        self._view_state = None

    def execute(self):
        login_dict = {
            "login": self._credentials.username,
            "password": self._credentials.password,
            "operacion": "ACEPTAR",
        }
        r = self._session.post(
            "https://farm3.sat.gob.gt/menu/init.do", data=login_dict, timeout=TIMEOUT
        )
        r.raise_for_status()
        logger.info("Login response received")
        bs = BeautifulSoup(r.text, features="html.parser")
        view_state = bs.find("input", {"name": "javax.faces.ViewState"})
        if view_state and "value" in view_state.attrs.keys():
            self._view_state = view_state["value"]
            logger.info("Login view state received")
            return (True, self._view_state)
        logger.warning("Login response did not contain a view state")
        return (False, None)


class SATDoLogout:
    def __init__(self, request_session, view_state):
        self._session = request_session
        self.view_state = view_state

    def execute(self):

        form_data = {
            "javax.faces.partial.ajax": True,
            "javax.faces.source: formContent": "j_idt46",
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": "formContent:contentAgenciaVirtual",
            "formContent:j_idt46": "formContent:j_idt46",
            "formContent": "formContent",
            "javax.faces.ViewState": self.view_state,
        }
        try:
            r = self._session.post(
                "https://farm3.sat.gob.gt/menu-agenciaVirtual/private/home.jsf",
                data=form_data,
                timeout=TIMEOUT,
            )
            r.raise_for_status()
        finally:
            r = self._session.post(
                "https://farm3.sat.gob.gt/menu/init.do",
                data={"operacion": "CANCELAR"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()


class SATGetMenu:
    def __init__(self, request_session, view_state):
        self._session = request_session
        self._view_state = view_state
        self._url_get_fel = None

    def execute(self):
        form_data = {
            "javax.faces.partial.ajax": True,
            "javax.faces.source: formContent": "j_idt34",
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": "formContent:contentAgenciaVirtual",
            "formContent:j_idt34": "formContent:j_idt34",
            "formContent": "formContent",
            "javax.faces.ViewState": self._view_state,
        }
        r = self._session.post(
            "https://farm3.sat.gob.gt/menu-agenciaVirtual/private/home.jsf",
            data=form_data,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        if r.text.lstrip().startswith("<?xml") or "<partial-response" in r.text:
            partial_response = BeautifulSoup(r.text, "xml")
            html = "\n".join(
                update.get_text() for update in partial_response.find_all("update")
            )
        else:
            html = r.text
        parser = BeautifulSoup(html, "html.parser")
        dtelink = parser.find("a", href=re.compile("dte-consulta"))
        if dtelink is None:
            return (False, None)
        dte_link = dtelink["href"]
        self._url_get_fel = dte_link
        return (True, self._url_get_fel)


class SATGetStablisments:
    def __init__(self, request_session):
        self._session = request_session

    def execute(self):
        url = "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/catalogo/establecimientos"
        r = self._session.get(url, headers=auth_headers(self._session), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
