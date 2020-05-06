from pathlib import Path

from yaml import safe_load
import pytest

from tests.test_fixtures import data_folder, root_path
from invproc.datastructures import Invoice
from invproc.parsing import parse_invoice_data


@pytest.fixture
def invoices(data_folder) -> Path:
    return data_folder / 'invoices'


def read_invoice(dn, n):
    with open(dn / f'{n}.data', 'r', encoding='utf-8') as fp:
        for line in fp:
            yield line


def read_expected(dn, n) -> Invoice:
    with open(dn / f'{n}.xpd.yml', 'r', encoding='utf-8') as fp:
        return Invoice(**safe_load(fp))


def test_valid_1(invoices):
    lines = read_invoice(invoices, 'valid_1')
    invoice = parse_invoice_data(lines)
    expected = read_expected(invoices, 'valid_1')

    assert expected.items[0].price == 2500  # represented as rappen
    assert expected == invoice


def test_valid_2(invoices):
    lines = read_invoice(invoices, 'valid_2')
    invoice = parse_invoice_data(lines)
    expected = read_expected(invoices, 'valid_2')

    assert expected == invoice


def test_missing_header(invoices):
    lines = read_invoice(invoices, 'missing_header')

    with pytest.raises(ValueError):
        parse_invoice_data(lines)


def test_missing_origin(invoices):
    lines = read_invoice(invoices, 'missing_origin')

    with pytest.raises(ValueError):
        parse_invoice_data(lines)


