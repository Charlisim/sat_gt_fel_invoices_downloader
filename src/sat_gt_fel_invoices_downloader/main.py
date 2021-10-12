from http import cookiejar
import json
from posixpath import dirname
import requests
from bs4 import BeautifulSoup, CData
from urllib.parse import urlencode
import re
import os.path


class SatCredentials:
    def __init__(self, username, password):
        self.username = username
        self.password = password


class SatFelDownloader:
    def __init__(self, credentials):
        print("Test")
        self._credentials = credentials
        self._session = requests.session()
        self._view_state = None
        self._url_get_fel = None

    def _login(self):
        login_dict = {
            "login": self._credentials.username,
            "password": self._credentials.password,
            "operacion": "ACEPTAR",
        }
        r = self._session.post("https://farm3.sat.gob.gt/menu/init.do", data=login_dict)
        r.raise_for_status()
        bs = BeautifulSoup(r.text, features="html.parser")
        view_state = bs.find("input", {"name": "javax.faces.ViewState"})
        print(view_state["value"])
        self._view_state = view_state["value"]

    def _get_queries_menu(self):
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

    def get_invocies(self, date_start, date_end, received=True):
        self._session.get(self._url_get_fel)
        operation_param = "R" if received else "E"
        cookie = self._session.cookies.get("ACCESS_TOKEN")
        print(cookie)
        dict_query = {
            "usuario": self._credentials.username,
            "tipoOperacion": operation_param,
            "nitIdReceptor": "",
            "fechaEmisionIni": date_start.strftime("%d-%m-%Y"),
            "fechaEmisionFinal": date_end.strftime("%d-%m-%Y"),
        }
        url = (
            "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte?"
            + urlencode(dict_query)
        )
        header = {"authtoken": "token " + cookie}
        r = self._session.get(url, headers=header)
        json_response = r.json()["detalle"]["data"]
        print(json_response)
        return json_response

    def get_pdf(self, invoice, save_in_dir=None, received=True):
        operation_param = "R" if received else "E"

        dict_query = {
            "usuario": self._credentials.username,
            "tipoOperacion": operation_param,
            "nitIdReceptor": "",
        }
        url = (
            "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte/pdf?"
            + urlencode(dict_query)
        )

        cookie = self._session.cookies.get("ACCESS_TOKEN")
        header = {"authtoken": "token " + cookie}
        r = self._session.post(url, headers=header, json=[invoice])
        print(r.headers)
        print(r.status_code)
        filename = self.get_filename_from_cd(r.headers.get("Content-Disposition"))
        if save_in_dir:
            filename = os.path.join(save_in_dir, filename)
            print(filename)
        open(filename, "wb").write(r.content)

    def get_filename_from_cd(self, cd):
        """
        Get filename from content-disposition
        """

        if not cd:
            return None
        fname = re.findall("filename=(.+)", cd)
        print(fname)
        if len(fname) == 0:
            return None
        return fname[0].replace('"', "")
