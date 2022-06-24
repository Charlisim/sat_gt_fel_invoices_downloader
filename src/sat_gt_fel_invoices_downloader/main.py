import re
import os.path
import base64
import codecs
import logging
import requests
from bs4 import BeautifulSoup, CData
from urllib.parse import urlencode
from datetime import datetime
from .models import (
    EstadoDTE,
    Invoice,
    InvoiceLine,
    InvoiceTotals,
    SATFELFilters,
    TotalTax,
    Address,
    ContactModel,
    InvoiceHeaders,
    IssuingModel,
    TypeFEL,
)
from .actions import SATDoLogin, SATDoLogout, SATGetMenu, SATGetStablisments
from contextlib import contextmanager

"""
Private class that makes all the action
"""

TIMEOUT = 20


class SatFelDownloader:
    def __init__(self, credentials, url_get_fel, request_session=requests.Session()):
        self._credentials = credentials
        self._session = request_session
        self._view_state = None
        self._url_get_fel = url_get_fel

    def _login(self):
        login_dict = {
            "login": self._credentials.username,
            "password": self._credentials.password,
            "operacion": "ACEPTAR",
        }
        r = self._session.post(
            "https://farm3.sat.gob.gt/menu/init.do", data=login_dict, timeout=TIMEOUT
        )
        r.raise_for_status()
        bs = BeautifulSoup(r.text, features="html.parser")
        logging.info("Did login")
        view_state = bs.find("input", {"name": "javax.faces.ViewState"})
        if view_state and "value" in view_state:
            self._view_state = view_state["value"]
            logging.info("Did get view state")
            return True
        return False

    def _get_invoices_headers(self, filter: SATFELFilters):
        logging.info("CALL URL GET FEL")
        self._session.get(self._url_get_fel, timeout=TIMEOUT)
        operation_param = filter.tipo
        cookie = self._session.cookies.get("ACCESS_TOKEN")
        dict_query = {
            "usuario": self._credentials.username,
            "tipoOperacion": operation_param.value,
            "nitIdReceptor": "",
            "estadoDte": filter.estadoDte.value,
            "fechaEmisionIni": filter.fechaInicio.strftime("%d-%m-%Y"),
            "fechaEmisionFinal": filter.fechaFin.strftime("%d-%m-%Y"),
        }
        logging.info("Querying invoices")
        logging.debug(dict_query)
        url = (
            "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte?"
            + urlencode(dict_query)
        )
        header = {"authtoken": "token " + cookie}
        r = self._session.get(url, headers=header, timeout=TIMEOUT)
        r.raise_for_status()
        json_response = r.json()["detalle"]["data"]
        return json_response

    def _process_contingency_pdf(self, invoice, filetype, received):
        url = "https://felav02.c.sat.gob.gt/verificador-rest/rest/publico/descargapdf"
        invoice = {
            "autorizacion": invoice["numeroUuid"],
            "emisor": invoice["nitEmisor"],
            "estado": "V",
            "monto": invoice["granTotal"],
            "receptor": invoice["nitReceptor"],
        }

        r = self._session.post(url, json=invoice, timeout=TIMEOUT)
        if r.status_code == 200:
            base64encoded = r.json()[0]
            bytes = base64.b64decode(base64encoded)
            if bytes[0:4] != b"%PDF":
                raise ValueError("Missing the PDF file signature")
            r.bytes = bytes
        return r, True

    def _get_response(self, invoice, filetype, received=True):
        url = None
        is_contingency = False
        print(invoice)
        if filetype.lower() == "xml":
            url = (
                "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte/xml?"
            )

        elif filetype.lower() == "pdf":
            url = (
                "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte/pdf?"
            )

        if url is None:
            return None
        operation_param = "R" if received else "E"

        dict_query = {
            "usuario": self._credentials.username,
            "tipoOperacion": operation_param,
            "nitIdReceptor": "",
        }
        url += urlencode(dict_query)
        cookie = self._session.cookies.get("ACCESS_TOKEN")
        header = {"authtoken": "token " + cookie}
        r = self._session.post(url, headers=header, json=[invoice], timeout=TIMEOUT)
        if r.status_code == 500:
            logging.warn("Did get 500 error trying pdf contingency")
            return self._process_contingency_pdf(invoice, "pdf-contingency", received)
        print(r)
        return r, is_contingency

    def get_pdf_content(self, invoice, received=True):
        r, is_contingency = self._get_response(
            invoice, filetype="pdf", received=received
        )
        
        if is_contingency:
            return r.bytes
        return r.content

    def get_pdf(self, invoice, save_in_dir=None, received=True):
        r, is_contingency = self._get_response(
            invoice, filetype="pdf", received=received
        )
        filename = self.get_filename_from_cd(r.headers.get("Content-Disposition"))
        if not filename:
            filename = invoice["numeroUuid"] + ".pdf"
        if save_in_dir:
            filename = os.path.join(save_in_dir, filename)
        if is_contingency:
            open(filename, "wb+").write(r.bytes)
        else:
            open(filename, "wb+").write(r.content)
        return filename

    def _process_invoice_lines(self, xml_lines):
        lines = xml_lines
        model_lines = []
        for item in lines:
            quantity = item.Cantidad.text
            good_or_service = item["BienOServicio"]
            line_number = item["NumeroLinea"]
            if "UnidadMedida" in item:
                uom = item.UnidadMedida.text
            description = item.Descripcion.text.strip()
            unit_price = item.PrecioUnitario.text
            total_before_discount = item.Precio.text
            discount = item.Descuento.text
            total = item.Total.text
            line = (
                InvoiceLine.builder()
                .set_quantity(float(quantity))
                .set_good_or_service(good_or_service)
                .set_line_number(int(line_number))
                .set_description(description)
                .set_unit_price(float(unit_price))
                .set_total_line(float(total_before_discount))
                .set_discount(float(discount))
                .set_total(float(total))
                .build()
            )
            model_lines.append(line)
        return model_lines

    def get_invoice_model(self, invoice, received=True):
        xml_content = self.get_xml_content(invoice, received)
        bs = BeautifulSoup(xml_content, "xml")
        emission_data = bs.find("DatosEmision")
        general_data = emission_data.select("DatosGenerales")[0]
        issuer = emission_data.select("Emisor")[0]
        receptor = emission_data.select("Receptor")[0]
        lines = emission_data.select("Item")
        currency = general_data["CodigoMoneda"]
        
        try:
             
            issue_date = datetime.strptime(
                general_data["FechaHoraEmision"], "%Y-%m-%dT%H:%M:%S%z"
            )
        except ValueError:
            try:
                issue_date = datetime.strptime(
                general_data["FechaHoraEmision"], "%Y-%m-%dT%H:%M:%S.%f%z"
                )
            except:
                try:
                    issue_date = datetime.strptime(
                    general_data["FechaHoraEmision"], "%Y-%m-%dT%H:%M:%S.%f"
                    )
                except:
                    issue_date = datetime.strptime(
                    general_data["FechaHoraEmision"], "%Y-%m-%dT%H:%M:%S"
                    )
            
        invoice_type = general_data["Tipo"]
        vat_affiliation = issuer["AfiliacionIVA"]
        stablisment_number = issuer["CodigoEstablecimiento"]
        
        issuer_email = issuer["CorreoEmisor"] if "CorreoEmisor" in issuer else None
        issuernit = issuer["NITEmisor"]
        commercial_name = issuer["NombreComercial"]
        issuer_name = issuer["NombreEmisor"]
        receptor_email = receptor.find("CorreoReceptor")
        emissor_address = issuer.find("Direccion").Text
        zip_code = issuer.find("CodigoPostal").text
        city = issuer.find("Municipio").text
        state = issuer.find("Departamento").text
        country = issuer.find("Pais").text
        nit_receptor = receptor["IDReceptor"]
        nombre_receptor = receptor["NombreReceptor"]
        model_lines = self._process_invoice_lines(lines)
        total = emission_data.Totales
        total_taxes = total.select("TotalImpuesto")
        grand_total = total.find("GranTotal").text

        total_taxes_model = []
        for tax in total_taxes:
            tax_model = (
                TotalTax.builder()
                .set_tax_name(tax["NombreCorto"])
                .set_tax_total(tax["TotalMontoImpuesto"])
                .build()
            )
            total_taxes_model.append(tax_model)
        address_model = (
            Address.builder()
            .set_street(emissor_address)
            .set_zip_code(zip_code)
            .set_city(city)
            .set_state(state)
            .set_country(country)
            .build()
        )
        issuer_model = (
            IssuingModel.builder()
            .set_nit(issuernit)
            .set_commercial_name(commercial_name)
            .set_issuing_name(issuer_name)
            .set_address(address_model)
            .set_vat_affiliation(vat_affiliation)
            .set_establishment(stablisment_number)
            .set_email(issuer_email)
            .build()
        )
        receiver = (
            ContactModel.builder()
            .set_nit(nit_receptor)
            .set_commercial_name(nombre_receptor)
            .set_address("CIUDAD")
            .set_email(receptor_email)
            .build()
        )
        invoice_header = (
            InvoiceHeaders.builder()
            .set_issue_date(issue_date)
            .set_invoice_type(invoice_type)
            .set_currency(currency)
            .set_issuer(issuer_model)
            .set_receiver(receiver)
            .build()
        )
        invoice_total = InvoiceTotals(total_taxes_model, grand_total=float(grand_total))
        fel_data = bs.find("Certificacion").find("NumeroAutorizacion")
        fel_invoice_number = fel_data["Numero"]
        fel_invoice_serie = fel_data["Serie"]
        fel_signature = fel_data.text
        invoice = (
            Invoice.builder()
            .with_headers(invoice_header)
            .with_lines(model_lines)
            .with_totals(invoice_total)
            .set_fel_signature(fel_signature)
            .set_fel_invoice_number(fel_invoice_number)
            .set_fel_invoice_serie(fel_invoice_serie)
            .build()
        )
        return invoice

    def get_xml_content(self, invoice, received=True):
        return self._get_response(
            invoice=invoice, filetype="xml", received=received
        )[0].content

    def get_xml(self, invoice, save_in_dir=None, received=True):
        r, _ = self._get_response(invoice=invoice, filetype="xml", received=received)
        filename = self.get_filename_from_cd(r.headers.get("Content-Disposition"))
        if not filename:
            filename = invoice["numeroUuid"] + ".xml"
        if save_in_dir:
            filename = os.path.join(save_in_dir, filename)
            open(filename, "wb").write(r.content)
            return filename
        else:
            return r.content

    def get_filename_from_cd(self, cd):
        """
        Get filename from content-disposition
        """

        if not cd:
            return None
        fname = re.findall("filename=(.+)", cd)
        if len(fname) == 0:
            return None
        return fname[0].replace('"', "")


"""
Main entrance of the SAT Downloader.
"""


class SATDownloader:
    def __init__(self, request_session=requests.Session()):
        self.credentials = None
        self.session = request_session
        self.url_get_fel = None
        self.its_initialized = False
        self.view_state = None

    "Need to set credentials before use any of the methods"

    def setCredentials(self, credentials):
        self.credentials = credentials
        return self

    def initialize(self):
        if self.credentials is None:
            raise ValueError(
                "You didn't provided credentials. Please use setCredentials method"
            )
        did_login, view_state = SATDoLogin(self.credentials, self.session).execute()
        if not did_login or not view_state:
            raise ValueError("The credentials you provided are not valid")
        logging.info("Did authenticate")
        menu = SATGetMenu(self.session, view_state)
        (did_get_menu, url) = menu.execute()
        logging.info("Did get menu URL")
        self.url_get_fel = url
        if not did_get_menu:
            raise ValueError("Could not get the menu")
        self.its_initialized = True
        self.view_state = view_state
        logging.info("Initialization process finished")

    """
        Remember to logout after you have finished your operations to make sure you don't interfere with web login.
    """

    def logout(self):
        SATDoLogout(self.session, self.view_state).execute()
        self.its_initialized = False
        self.view_state = None
        self.url_get_fel = None

    def get_stablisments(self):

        if not self.its_initialized:
            self.initialize()
        stablisments = SATGetStablisments(self.session).execute()
        return stablisments

    def get_invoices_with_filters(self, filters: SATFELFilters):
        logging.info("GET INVOICES WITH FILTERS")
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        return downloader._get_invoices_headers(filters)

    def get_invoices(self, date_start, date_end, received=True):
        logging.info("GET INVOICES WITH OLD FORMAT")

        type_fel = TypeFEL.RECIBIDA if received else TypeFEL.EMITIDA
        filter = SATFELFilters(0, EstadoDTE.TODOS, date_start, date_end, type_fel)
        return self.get_invoices_with_filters(filter)

    def get_invoices_models(self, date_start, date_end, received=True):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        invoices = self.get_invoices(date_start, date_end, received)
        invoices_model = list(map(downloader.get_invoice_model, invoices))
        return invoices_model

    def get_model(self, invoice):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        return downloader.get_invoice_model(invoice)

    def get_pdf_content(self, invoice, save_in_dir=None):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        return downloader.get_pdf_content(invoice, save_in_dir)

    def get_pdf(self, invoice, save_in_dir=None):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        return downloader.get_pdf(invoice, save_in_dir)

    def get_xml_content(self, invoice):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        downloader.get_xml_content(invoice)

    def get_xml(self, invoice, save_in_dir=None):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        downloader.get_xml(invoice, save_in_dir)
