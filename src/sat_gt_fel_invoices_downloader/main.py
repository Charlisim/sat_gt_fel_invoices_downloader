import base64
import logging
from datetime import datetime
from email.message import Message
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from .actions import (
    SATDoLogin,
    SATDoLogout,
    SATGetMenu,
    SATGetStablisments,
    auth_headers,
)
from .models import (
    Address,
    ContactModel,
    EstadoDTE,
    Invoice,
    InvoiceHeaders,
    InvoiceLine,
    InvoiceTotals,
    IssuingModel,
    SATFELFilters,
    TotalTax,
    TypeFEL,
)

"""
Private class that makes all the action
"""

TIMEOUT = 20
logger = logging.getLogger(__name__)


class SatFelDownloader:
    def __init__(self, credentials, url_get_fel, request_session=None):
        self._credentials = credentials
        self._session = (
            request_session if request_session is not None else requests.Session()
        )
        self._view_state = None
        self._url_get_fel = url_get_fel

    def _get_invoices_headers(self, filter: SATFELFilters):
        operation_param = filter.tipo
        dict_query = {
            "usuario": self._credentials.username,
            "tipoOperacion": operation_param.value,
            "nitIdReceptor": "",
            "estadoDte": filter.estadoDte.value,
            "fechaEmisionIni": filter.fechaInicio.strftime("%d-%m-%Y"),
            "fechaEmisionFinal": filter.fechaFin.strftime("%d-%m-%Y"),
        }
        logging.info("Querying invoices")
        url = (
            "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte?"
            + urlencode(dict_query)
        )
        header = auth_headers(self._session)
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
        r.raise_for_status()
        base64encoded = r.json()[0]
        content = base64.b64decode(base64encoded, validate=True)
        if not content.startswith(b"%PDF"):
            raise ValueError("Missing the PDF file signature")
        r.bytes = content
        return r, True

    def _get_response(self, invoice, filetype, received=True):
        url = None
        is_contingency = False
        if filetype.lower() == "xml":
            url = (
                "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte/xml?"
            )

        elif filetype.lower() == "pdf":
            url = (
                "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte/pdf?"
            )

        if url is None:
            raise ValueError("File type must be pdf or xml")
        operation_param = "R" if received else "E"

        dict_query = {
            "usuario": self._credentials.username,
            "tipoOperacion": operation_param,
            "nitIdReceptor": "",
        }
        url += urlencode(dict_query)
        header = auth_headers(self._session)
        r = self._session.post(url, headers=header, json=[invoice], timeout=TIMEOUT)
        if r.status_code == 500 and filetype.lower() == "pdf":
            logger.warning("PDF request failed; trying the contingency endpoint")
            return self._process_contingency_pdf(invoice, "pdf-contingency", received)
        r.raise_for_status()
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
        content = r.bytes if is_contingency else r.content
        return self._save_file(r, invoice, "pdf", content, save_in_dir)

    def _save_file(self, response, invoice, extension, content, directory):
        filename = self.get_filename_from_cd(
            response.headers.get("Content-Disposition")
        )
        if not filename:
            filename = self._safe_filename(str(invoice["numeroUuid"]) + "." + extension)
        destination = Path(directory) if directory is not None else Path.cwd()
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / filename
        path.write_bytes(content)
        return str(path) if directory is not None else filename

    @staticmethod
    def _safe_filename(filename):
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if filename in {"", ".", ".."} or "\x00" in filename or ":" in filename:
            raise ValueError("Invalid invoice filename")
        return filename

    def _process_invoice_lines(self, xml_lines):
        lines = xml_lines
        model_lines = []
        for item in lines:
            quantity = item.Cantidad.text
            good_or_service = item["BienOServicio"]
            line_number = item["NumeroLinea"]
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
        if emission_data is None:
            raise ValueError("The XML does not contain FEL DatosEmision")
        general_data = emission_data.select("DatosGenerales")[0]
        issuer = emission_data.select("Emisor")[0]
        receptor = emission_data.select("Receptor")[0]
        lines = emission_data.select("Item")
        currency = general_data["CodigoMoneda"]

        issue_date = datetime.fromisoformat(general_data["FechaHoraEmision"])

        invoice_type = general_data["Tipo"]
        vat_affiliation = issuer["AfiliacionIVA"]
        stablisment_number = issuer["CodigoEstablecimiento"]

        issuer_email = issuer.get("CorreoEmisor")
        issuernit = issuer["NITEmisor"]
        commercial_name = issuer["NombreComercial"]
        issuer_name = issuer["NombreEmisor"]
        receptor_email = receptor.get("CorreoReceptor")
        emissor_address = issuer.find("Direccion").text.strip()
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
                .set_tax_total(float(tax["TotalMontoImpuesto"]))
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
        return self._get_response(invoice=invoice, filetype="xml", received=received)[
            0
        ].content

    def get_xml(self, invoice, save_in_dir=None, received=True):
        r, _ = self._get_response(invoice=invoice, filetype="xml", received=received)
        if save_in_dir is not None:
            return self._save_file(r, invoice, "xml", r.content, save_in_dir)
        return r.content

    def get_filename_from_cd(self, cd):
        """
        Get filename from content-disposition
        """

        if not cd:
            return None
        message = Message()
        message["Content-Disposition"] = cd
        filename = message.get_filename()
        return self._safe_filename(filename) if filename else None


"""
Main entrance of the SAT Downloader.
"""


class SATDownloader:
    """Download FEL invoices using an independent SAT session.

    Authentication is lazy. Use a context manager or call close() after use.
    A supplied requests.Session remains owned by its caller.
    """

    def __init__(self, request_session=None):
        self.credentials = None
        self._owns_session = request_session is None
        self.session = (
            request_session if request_session is not None else requests.Session()
        )
        self.url_get_fel = None
        self.its_initialized = False
        self.view_state = None

    def set_credentials(self, credentials):
        """Set credentials before authentication and return this client."""
        if self.its_initialized:
            raise ValueError("Log out before changing credentials")
        self.credentials = credentials
        return self

    def setCredentials(self, credentials):
        """Compatibility alias for set_credentials()."""
        return self.set_credentials(credentials)

    def initialize(self):
        if self.its_initialized:
            return
        if self.credentials is None:
            raise ValueError("Credentials are required; call set_credentials() first")
        did_login, view_state = SATDoLogin(self.credentials, self.session).execute()
        if not did_login or not view_state:
            raise ValueError(
                "SAT login failed: credentials rejected or login page changed"
            )
        self.view_state = view_state
        try:
            did_get_menu, url = SATGetMenu(self.session, view_state).execute()
            if not did_get_menu or not url:
                raise ValueError("The SAT response does not contain the FEL menu link")
            bootstrap = self.session.get(url, timeout=TIMEOUT)
            bootstrap.raise_for_status()
            auth_headers(self.session)
            self.url_get_fel = url
            self.its_initialized = True
        except Exception:
            try:
                self.logout()
            except requests.RequestException:
                logger.warning("Could not log out after initialization failed")
            raise
        logger.info("SAT session initialized")

    def logout(self):
        """End the remote session and clear local authentication state."""
        try:
            if self.its_initialized or self.view_state is not None:
                SATDoLogout(self.session, self.view_state).execute()
        finally:
            self.its_initialized = False
            self.view_state = None
            self.url_get_fel = None
            self.session.cookies.clear()

    def close(self):
        try:
            self.logout()
        finally:
            if self._owns_session:
                self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.close()
        except requests.RequestException:
            if exc_type is None:
                raise
            logger.warning("Could not log out while handling another error")
        return False

    def _downloader(self):
        if not self.its_initialized:
            self.initialize()
        return SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )

    def get_establishments(self):
        self._downloader()
        return SATGetStablisments(self.session).execute()

    def get_stablisments(self):
        """Compatibility alias for get_establishments()."""
        return self.get_establishments()

    def get_invoices_with_filters(self, filters: SATFELFilters):
        if filters.fechaInicio > filters.fechaFin:
            raise ValueError("The start date must be on or before the end date")
        return self._downloader()._get_invoices_headers(filters)

    def get_invoices(self, date_start, date_end, received=True):
        type_fel = TypeFEL.RECIBIDA if received else TypeFEL.EMITIDA
        filters = SATFELFilters(0, EstadoDTE.TODOS, date_start, date_end, type_fel)
        return self.get_invoices_with_filters(filters)

    def get_invoices_models(self, date_start, date_end, received=True):
        invoices = self.get_invoices(date_start, date_end, received=received)
        downloader = self._downloader()
        return [
            downloader.get_invoice_model(invoice, received=received)
            for invoice in invoices
        ]

    def get_model(self, invoice, received=True):
        return self._downloader().get_invoice_model(invoice, received=received)

    def get_pdf_content(self, invoice, save_in_dir=None, received=True):
        """Return PDF bytes; save_in_dir is an unused compatibility argument."""
        return self._downloader().get_pdf_content(invoice, received=received)

    def get_pdf(self, invoice, save_in_dir=None, received=True):
        return self._downloader().get_pdf(invoice, save_in_dir, received=received)

    def get_xml_content(self, invoice, received=True):
        return self._downloader().get_xml_content(invoice, received=received)

    def get_xml(self, invoice, save_in_dir=None, received=True):
        return self._downloader().get_xml(invoice, save_in_dir, received=received)
