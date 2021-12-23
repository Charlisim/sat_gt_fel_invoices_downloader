import re
import datetime
import logging
import requests
from bs4 import BeautifulSoup, CData
from urllib.parse import urlencode

TIMEOUT = 5


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
        logging.info("Did make loging")
        bs = BeautifulSoup(r.text, features="html.parser")
        view_state = bs.find("input", {"name": "javax.faces.ViewState"})
        if view_state and "value" in view_state.attrs.keys():
            self._view_state = view_state["value"]
            logging.info("Did get view state")
            return (True, self._view_state)
        logging.warning("Didn't get view state")
        return (True, self._view_state)


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
        r = self._session.post(
            "https://farm3.sat.gob.gt/menu-agenciaVirtual/private/home.jsf",
            data=form_data,
            timeout=3,
        )
        r2 = self._session.post(
            "https://farm3.sat.gob.gt/menu/init.do",
            data={"operacion": "CANCELAR"},
            timeout=3,
        )


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
        parser = BeautifulSoup(r.text, "html.parser")
        data = []
        for cd in parser.findAll(text=True):
            if isinstance(cd, CData):
                data.append(cd)

        if len(data) > 0:
            parserdata = BeautifulSoup(data[0], "html.parser")
            dtelink = parserdata.find("a", href=re.compile("dte-consulta"))
            dte_link = dtelink["href"]
            self._url_get_fel = dte_link
            return (True, self._url_get_fel)
        return (False, self._url_get_fel)


class SATGetStablisments:
    def __init__(self, request_session):
        self._session = request_session

    def execute(self):
        url = "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/catalogo/establecimientos"
        cookie = self._session.cookies.get("ACCESS_TOKEN")
        header = {"authtoken": "token " + cookie}
        r = self._session.get(url, headers=header, timeout=TIMEOUT)
        return r.json
