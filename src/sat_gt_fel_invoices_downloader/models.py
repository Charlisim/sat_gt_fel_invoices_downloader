from datetime import date, datetime
from enum import Enum
from re import S
from dataclasses import dataclass
from typing import List


class EstadoDTE(Enum):
    TODOS = ""
    VIGENTES = "V"
    ANULADAS = "I"


class TypeFEL(Enum):
    RECIBIDA = "R"
    EMITIDA = "E"


@dataclass
class SatCredentials:
    username: str
    password: str


@dataclass
class SATFELFilters:
    establecimiento: int
    estadoDte: EstadoDTE
    fechaInicio: date
    fechaFin: date
    tipo: TypeFEL


@dataclass
class Address:
    street: str
    zip_code: int
    city: str
    state: str
    country: str = "GT"

    @classmethod
    def builder(cls):
        return Builder(cls)


@dataclass
class ContactModel:
    nit: str
    commercial_name: str
    address: Address
    email: str

    @classmethod
    def builder(cls):
        return Builder(cls)


@dataclass
class IssuingModel(ContactModel):
    nit: str
    commercial_name: str
    issuing_name: str
    address: str
    vat_affiliation: str
    establishment: str

    @classmethod
    def builder(cls):
        return Builder(cls)


@dataclass
class Tax:
    short_name: str
    tax_code: str
    taxable_ammount: float
    tax_ammount: float


@dataclass
class InvoiceLine(object):
    good_or_service: str
    description: str
    quantity: float
    unit_price: float
    total_line: float
    total: float
    line_number: int
    discount: float

    @classmethod
    def builder(cls):
        return Builder(cls)


@dataclass
class InvoiceHeaders:
    issue_date: datetime.date
    invoice_type: str
    issuer: IssuingModel
    receiver: ContactModel
    currency: str

    @classmethod
    def builder(cls):
        return Builder(cls)


@dataclass
class TotalTax:
    tax_name: str
    tax_total: float

    @classmethod
    def builder(cls):
        return Builder(cls)


@dataclass
class InvoiceTotals:
    total_taxes: List[TotalTax]
    grand_total: float

    @classmethod
    def builder(cls):
        return Builder(cls)


@dataclass
class Invoice:
    headers: InvoiceHeaders
    lines: List[InvoiceLine]
    totals: InvoiceTotals
    fel_signature: str
    fel_invoice_serie: str
    fel_invoice_number: str

    def __str__(self):
        lines_format = "INVOICE LINES\n"
        for line in self.lines:
            lines_format += str(line)
            lines_format += "\n"

        return "{3} - {4} - {5}\n{0}\n{1}\n{2}".format(
            self.headers,
            lines_format,
            self.totals,
            self.fel_signature,
            self.fel_invoice_serie,
            self.fel_invoice_number,
        )

    @classmethod
    def builder(cls):
        return InvoiceBuilder(cls)


class Builder:
    def __init__(self, cls):
        self.attrs = {}
        self.cls = cls

    def __getattr__(self, name):
        if name[0:3] == "set":

            def setter(x):
                field_name = name[4:]
                self.attrs[field_name] = x
                return self

            return setter
        else:
            return None

    def build(self):
        return self.cls(**self.attrs)


class InvoiceBuilder(Builder):
    def __init__(self, cls):
        self.attrs = {}
        self.cls = cls

    def with_headers(self, headers):
        self.attrs["headers"] = headers
        return self

    def with_lines(self, lines):
        self.attrs["lines"] = lines
        return self

    def with_totals(self, totals):
        self.attrs["totals"] = totals
        return self
