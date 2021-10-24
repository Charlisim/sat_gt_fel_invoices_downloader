import re
import os.path
import xml.etree.ElementTree as ET
import datetime
import logging
import requests
from bs4 import BeautifulSoup, CData
from urllib.parse import urlencode
from .actions import SATDoLogin, SATGetMenu
from .main import SatFelDownloader


class SATDownloader:
    def __init__(self, request_session=requests.Session()):
        self.credentials = None
        self.session = request_session
        self.url_get_fel = None
        self.its_initialized = False

    def setCredentials(self, credentials):
        self.credentials = credentials
        return self

    def initialize(self):
        did_login, view_state = SATDoLogin(self.credentials, self.session).execute()
        if not did_login or not view_state:
            raise ValueError("The credentials you provided are not valid")
        menu = SATGetMenu(self.session, view_state)
        (did_get_menu, url) = menu.execute()
        self.url_get_fel = url
        if not did_get_menu:
            raise ValueError("Could not get the menu")
        self.its_initialized = True

    def get_invoices(self, date_start, date_end):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        return downloader.get_invoices_headers(date_start, date_end)

    def get_invoices_models(self, date_start, date_end):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        invoices = self.get_invoices(date_start, date_end)
        invoices_model = list(map(downloader.get_invoice_model, invoices))
        return invoices_model

    def get_pdf(self, invoice, save_in_dir=None):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        downloader.get_pdf(invoice, save_in_dir)

    def get_xml(self, invoice):
        if not self.its_initialized:
            self.initialize()
        downloader = SatFelDownloader(
            self.credentials, url_get_fel=self.url_get_fel, request_session=self.session
        )
        downloader.get_xml(invoice)
