import re
import os.path
import xml.etree.ElementTree as ET
import logging
import requests
from bs4 import BeautifulSoup, CData
from urllib.parse import urlencode
from .models import *
from datetime import datetime


class SatCredentials:
    def __init__(self, username, password):
        self.username = username
        self.password = password


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
        r = self._session.post("https://farm3.sat.gob.gt/menu/init.do", data=login_dict)
        r.raise_for_status()
        bs = BeautifulSoup(r.text, features="html.parser")
        view_state = bs.find("input", {"name": "javax.faces.ViewState"})
        if view_state and "value" in view_state:
            self._view_state = view_state["value"]
            return True
        return False

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
            return True
        return False

    def get_invoices_headers(self, date_start, date_end, received=True):
        self._session.get(self._url_get_fel)
        operation_param = "R" if received else "E"
        cookie = self._session.cookies.get("ACCESS_TOKEN")
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
        filename = self.get_filename_from_cd(r.headers.get("Content-Disposition"))
        if save_in_dir:
            filename = os.path.join(save_in_dir, filename)
        open(filename, "wb").write(r.content)

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
        xml_content = self._get_xml_content(invoice, received)
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
            issue_date = datetime.strptime(
                general_data["FechaHoraEmision"], "%Y-%m-%dT%H:%M:%S.%f%z"
            )
        invoice_type = general_data["Tipo"]
        vat_affiliation = issuer["AfiliacionIVA"]
        stablisment_number = issuer["CodigoEstablecimiento"]
        issuer_email = issuer["CorreoEmisor"]
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
        logging.info(invoice)
        return invoice

    def _get_xml_response(self, invoice, received=True):
        operation_param = "R" if received else "E"

        dict_query = {
            "usuario": self._credentials.username,
            "tipoOperacion": operation_param,
            "nitIdReceptor": "",
        }
        url = (
            "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte/xml?"
            + urlencode(dict_query)
        )

        cookie = self._session.cookies.get("ACCESS_TOKEN")
        header = {"authtoken": "token " + cookie}
        r = self._session.post(url, headers=header, json=[invoice])
        return r

    def _get_xml_content(self, invoice, received=True):
        return self._get_xml_response(invoice=invoice, received=received).content

    def get_xml(self, invoice, save_in_dir=None, received=True):
        r = self._get_xml_response(invoice, received)
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
