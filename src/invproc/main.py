import os
import os.path
import re
import pickle
from io import BytesIO
from zipfile import ZipFile
from typing import List, Tuple, Optional
import uuid

from loguru import logger

from .config import config
from .datastructures import Invoice, InvoiceItem, ContactDetails
from .ftp_utils import scan, push, delete, close_connections
from .parsing import parse_invoice_data
from .templating import render_txt, render_xml
from .mailer import send_mail

_run_id = None


def _get_uid():
    global _run_id

    if _run_id is None:
        _run_id = str(uuid.uuid4())
        return _run_id
    else:
        return _run_id


def main():
    logger.add('app.log')
    c = config()
    uid = _get_uid()
    logger.info(f'Started run {uid}')

    # scan for new invoices
    new_invoices = pull_invoices()

    if len(new_invoices) > 0:
        logger.info(f'Received {len(new_invoices)} new invoices. Processing...')

        for invoice in new_invoices:
            try:
                archive(f'{invoice.recipient.id}_{invoice.id}_invoice.pickle', pickle.dumps(invoice))
                files = build_invoice_files(invoice)
                for fn, fc in files:
                    push(c.locations.invoice_push, fn, fc)
                    logger.info(f'#{invoice.id} Successfully pushed invoices to next stage')
            except Exception as e:
                logger.opt(exception=e)\
                    .error(f'#{invoice.id} Error occurred during processing of invoice. Invoice will be skipped')

    # scan for new receipts
    new_receipts = pull_receipts()

    if len(new_receipts) > 0:
        logger.info(f'Received {len(new_receipts)} new receipts. Processing...')

        for fn, fc in new_receipts:
            try:
                invoice, zip_fn, zip_fc = process_receipt(fn, fc)
            except Exception as e:
                logger.opt(exception=e).error(f'Error occurred during processing of receipt "{fn}". Ignoring')
                continue

            logger.info(f'Sending email')
            try:
                send_mail(invoice, (zip_fn, zip_fc))
            except Exception as e:
                logger.opt(exception=e).error('Error occurred during sending of mail')

    # clean up
    logger.info('Closing connections...')
    close_connections()

    logger.info(f'Finished run {uid}')


def pull_invoices() -> List[Invoice]:
    def yield_lines(fc: bytes):
        for line in fc.decode('utf-8').splitlines():
            yield line

    c = config()
    invoices = []

    files = scan(c.locations.data_scan)
    if len(files) == 0:
        logger.info(f'No new invoices to parse')
        return []

    for fn, fc in files:
        logger.info(f'Parsing pulled invoice "{fn}"')

        try:
            invoice = parse_invoice_data(yield_lines(fc))
            invoices.append(invoice)
            logger.info(f'Successfully parsed invoice #{invoice.id}: ' + str(invoice))
            delete(c.locations.data_scan, fn)
        except ValueError as e:
            logger.opt(exception=e).warning(f'Invoice data is malformed. Ignoring invoice')

    return invoices


def build_invoice_files(invoice) -> List[Tuple[str, bytes]]:
    logger.info(f'#{invoice.id} Rendering txt and xml files')
    files = []

    xml_content = render_xml(invoice).encode('utf-8')
    xml_fn = f'{invoice.recipient.id}_{invoice.id}_invoice.xml'
    files.append((xml_fn, xml_content))
    logger.debug(f'#{invoice.id} Rendered "{xml_fn}"')

    txt_content = render_txt(invoice).encode('utf-8')
    txt_fn = f'{invoice.recipient.id}_{invoice.id}_invoice.txt'
    files.append((txt_fn, txt_content))
    logger.debug(f'#{invoice.id} Rendered "{txt_fn}"')

    for fn, fc in files:
        archive(fn, fc)

    return files


def pull_receipts() -> List[Tuple[str, bytes]]:
    c = config()
    files = scan(c.locations.receipt_scan)

    if len(files) == 0:
        logger.info(f'No new receipts to process')
        return []

    return files


def process_receipt(fn, fc) -> Tuple[Invoice, str, bytes]:
    c = config()
    logger.info(f'Processing receipt "{fn}"')

    archive(fn, fc)
    prefix = extract_receipt_prefix(fn, fc)
    inv = find_invoice(prefix) if prefix is not None else None
    if prefix is None:
        logger.warning('Could not extract prefix from receipt {fn}. Using receipt\'s fn instead')
        prefix = fn

    files = [(fn, fc)]
    if inv is not None:
        files.append(inv)

    zip_fn = prefix + '.zip'
    logger.info(f'Creating zip archive "{zip_fn}" containing files [{", ".join([fn for fn, _ in files])}]')
    zip_archive = create_zip_archive(files)
    archive(zip_fn, zip_archive)

    logger.info(f'Uploading zip archive')
    push(c.locations.archive_push, zip_fn, zip_archive)
    delete(c.locations.receipt_scan, fn)

    return find_invoice_pickle(prefix), zip_fn, zip_archive


def find_invoice(prefix) -> Optional[Tuple[str, bytes]]:
    c = config()

    for dir, dirs, files in os.walk(c.archive):
        if 'failure' in dir:
            continue

        for fn in files:
            if fn.lower().startswith(prefix.lower() + '_invoice') and fn.endswith('.txt'):
                with open(os.path.join(dir, fn), 'rb') as fp:
                    return fn, fp.read()

    return None


def find_invoice_pickle(prefix) -> Optional[Invoice]:
    c = config()

    for dir, dirs, files in os.walk(c.archive):
        if 'failure' in dir:
            continue

        for fn in files:
            if fn.lower().startswith(prefix.lower() + '_invoice') and fn.endswith('.pickle'):
                with open(os.path.join(dir, fn), 'rb') as fp:
                    return pickle.load(fp)

    return None


def extract_receipt_prefix(fn, fc):
    prefix = None

    m = re.search(r'(K?[0-9]{2,5}_[0-9]{3,6})_invoice', fc.decode('utf-8'), re.IGNORECASE)
    if m:
        prefix = m.group(1)
        return prefix

    if fn.startswith('quittungsfile'):
        prefix = fn.split('.')[0].replace('quittungsfile', '')
        logger.warning(f'Could not deduce expected prefix name from receipt "{fn}". '
                       f'Taking prefix from filename ({prefix})')
        return prefix

    if prefix is None:
        logger.warning(f'Could not deduce appropriate prefix name from receipt "{fn}"')
        return None


def create_zip_archive(files: List[Tuple[str, bytes]]) -> bytes:
    with BytesIO() as dest:
        with ZipFile(dest, 'w') as zipfile:
            for fn, fc in files:
                zipfile.writestr(fn, fc)

        dest.seek(0)
        return dest.read()


def archive(fn, fc, failure=False):
    c = config()
    uid = _get_uid()

    if failure:
        dir = os.path.join(c.archive, 'failures', uid)
        os.makedirs(dir, exist_ok=True)
    else:
        dir = os.path.join(c.archive, uid)
        os.makedirs(dir, exist_ok=True)

    with open(os.path.join(dir, fn), 'wb') as fp:
        fp.write(fc)

    logger.debug(f'Archived {fn} [failure={failure}]')
