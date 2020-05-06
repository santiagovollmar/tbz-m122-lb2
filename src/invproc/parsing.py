from typing import Iterable, List, Dict, Any, Optional
from datetime import datetime, timedelta
import re

from loguru import logger

from .datastructures import Invoice, InvoiceItem, ContactDetails


def parse_invoice_data(lines: Iterable[str]) -> Invoice:
    def next_parts(*, required=False) -> Optional[List[str]]:
        try:
            line = next(lines)
            parts = line.strip().split(';')
            return parts
        except StopIteration as e:
            if required:
                raise ValueError()  # TODO
            else:
                return None

    attributes = {'items': []}

    # parse header
    attributes.update(_parse_invoice_header(next_parts(required=True)))

    # parse lines based on leading token
    while True:
        parts = next_parts()
        if parts is None:  # EOF
            break

        identifier = parts[0].lower()

        if identifier == 'herkunft':
            o = _parse_origin_header(parts)
            if 'recipient' in attributes:
                logger.warning('OVERWRITE')  # TODO warn about overwrite; ask if exit
            attributes['recipient'] = o
        elif identifier == 'endkunde':
            o = _parse_destination_header(parts)
            if 'sender' in attributes:
                logger.warning('OVERWRITE')  # TODO warn about overwrite; ask if exit
            attributes['sender'] = o
        elif identifier == 'rechnpos':
            attributes['items'].append(_parse_invoice_item(parts))
        else:
            logger.warning('INVALID ID')  # TODO warn; ask if exit

    # create invoice from gathered attributes
    invoice = Invoice(**attributes)

    if len(invoice.items) == 0:
        pass  # TODO warn; ask if exit

    return invoice


def _parse_invoice_header(parts: List[str]) -> Dict[str, Any]:
    attributes = _map_to_attributes(parts, ['id', 'account', 'city', 'date', 'time', 'target_deadline'])

    id = attributes['id']
    if re.fullmatch(r'Rechnung_[^_]+', id, re.IGNORECASE):
        attributes['id'] = id[9:]
    else:
        raise ValueError('Invalid invoice id in header')

    account = attributes['account']
    if re.fullmatch(r'Auftrag_A[^_]+', account, re.IGNORECASE):
        attributes['account'] = account[8:]
    else:
        raise ValueError('Invalid account id in header')

    try:
        date_str = f'{attributes["date"]} {attributes["time"]}'
        attributes['timestamp'] = datetime.strptime(date_str, '%d.%m.%Y %H:%M:%S')
        del attributes['date'], attributes['time']
    except ValueError:
        raise ValueError('Time malformed in header')

    target_deadline = attributes['target_deadline']
    if re.fullmatch(r'ZahlungszielInTagen_[0-9]+', target_deadline, re.IGNORECASE):
        attributes['target_deadline'] = timedelta(days=int(target_deadline[20:]))
    else:
        raise ValueError('Invalid format of target deadline')

    return attributes


def _parse_origin_header(parts: List[str]) -> ContactDetails:
    attributes = _map_to_attributes(parts, [None, 'id', 'company', 'human', 'street', 'city', 'vat_id', 'email'])

    m = re.fullmatch(r'([0-9]{3,5}) (.+)', attributes['city'])
    if m:
        attributes['zip'] = m.group(1)
        attributes['city'] = m.group(2)
    else:
        raise ValueError('Missing or malformed zip code/city in origin')

    m = re.fullmatch(r'(CHE-\d{3}\.\d{3}\.\d{3}) MWST', attributes['vat_id'])
    if m:
        attributes['vat_id'] = m.group(1)
    else:
        raise ValueError('Missing or malformed VATIN')

    return ContactDetails(**attributes)


def _parse_destination_header(parts: List[str]) -> ContactDetails:
    attributes = _map_to_attributes(parts, [None, 'id', 'company', 'street', 'city'])

    m = re.fullmatch(r'([0-9]{3,5}) (.+)', attributes['city'])
    if m:
        attributes['zip'] = m.group(1)
        attributes['city'] = m.group(2)
    else:
        raise ValueError('Missing or malformed zip code/city in destination')

    return ContactDetails(**attributes)


def _parse_invoice_item(parts: List[str]) -> InvoiceItem:
    attributes = _map_to_attributes(parts, [None, None, 'description', 'count', 'price', 'total', 'vat_multiplier'])

    m = re.fullmatch(r'MWST_([0-9]{1,5}\.[0-9]{1,5})%', attributes['vat_multiplier'])
    if m:
        percentage = m.group(1)

        try:
            attributes['vat_multiplier'] = float(percentage) / 100
        except ValueError as e:
            raise ValueError('vat multiplier is not a valid float')
    else:
        raise ValueError('Malformed vat multiplier field')

    return InvoiceItem(**attributes)


def _map_to_attributes(parts: List[str], map: List[str]) -> Dict[str, str]:
    if len(map) > len(parts):
        raise ValueError('Not enough parts in line')

    attributes = dict()
    for part, attr in zip(parts, map):
        if attr is not None:
            attributes[attr] = part

    return attributes

