from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .datastructures import Invoice, InvoiceItem, ContactDetails
from .config import config

_jinja_env: Optional[Environment] = None


def render_xml(invoice: Invoice) -> str:
    _ensure_env_loaded()

    template = _jinja_env.get_template(config().templates.xml_template.file)
    return template.render(invoice)


def render_txt(invoice: Invoice) -> str:
    _ensure_env_loaded()
    template = _jinja_env.get_template(config().templates.txt_template.file)
    return template.render(invoice)


def render_mail(invoice: Invoice) -> str:
    _ensure_env_loaded()
    template = _jinja_env.get_template('mail.txt')
    return template.render(invoice)


def _ensure_env_loaded():
    global _jinja_env

    if _jinja_env is None:
        c = config().templates

        _jinja_env = Environment(
            loader=FileSystemLoader(c.search_in),
            autoescape=select_autoescape(['xml']),
            lstrip_blocks=True,
            trim_blocks=True
        )

        _jinja_env.filters.update(_build_custom_filters())



def _build_custom_filters():
    return {
        'lmap': lambda value, transformer = 'e': map(eval('lambda e: ' + transformer), value),
        'enumerate': lambda value: enumerate(value),
        'fill': lambda value, length, c = ' ': str(value) + (c * (length - len(str(value)))),
        'lfill':  lambda value, length, c = ' ': (c * (length - len(str(value)))) + str(value),
        'chf': lambda value, length: ('   CHF{:' + str(length-6) + '.2f}').format(value/100)
    }

