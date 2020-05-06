import re
from io import BytesIO
from ftplib import FTP, FTP_TLS

from loguru import logger

from .config import config, LocationSpecConfig

_connection_cache = {}


def scan(location: LocationSpecConfig):
    ftp = _connect(location.server)
    ftp.cwd(location.path)
    fns = ftp.nlst()

    logger.debug(f'Scanning "{location.path}" [{location.server}] for files matching regex "{location.pattern}"')
    files = []
    for fn in fns:
        if re.fullmatch(location.pattern, fn):
            logger.debug(f'Reading contents of matching file "{fn}"')
            try:
                with BytesIO() as fp:
                    ftp.retrbinary(f'RETR {fn}', fp.write)
                    fp.seek(0)
                    fc = fp.read()
                    files.append((fn, fc))
            except Exception as e:
                logger.error(f'Exception occurred while reading "{fn}" [{location.server}]. File will be ignored', e)

    return files


def push(location: LocationSpecConfig, fn, fc):
    ftp = _connect(location.server)
    ftp.cwd(location.path)

    with BytesIO(fc) as fp:
        logger.debug(f'Uploading "{fn}" to "{location.path}" [{location.server}]')
        ftp.storbinary(f'STOR {fn}', fp)


def delete(location: LocationSpecConfig, fn):
    ftp = _connect(location.server)
    ftp.cwd(location.path)

    logger.debug(f'Deleting "{fn}" from "{location.path}" [{location.server}]')
    ftp.delete(fn)


def close_connections():
    for s, c in _connection_cache.items():
        try:
            c.quit()
        except Exception as e:
            logger.warning(f'Error occured during closing of connection to "{s}". Ignoring', e)


def _connect(server: str):
    global _connection_cache

    if server not in _connection_cache:
        if server == 'in_server':
            logger.debug(f'Connection to "in_server" requested')
            conn_specs = config().ftp.in_server
        elif server == 'out_server':
            logger.debug(f'Connection to "out_server" requested')
            conn_specs = config().ftp.out_server
        else:
            raise ValueError(f'Unknown server "{server}"')

        logger.debug(f'conn specs = {conn_specs}')

        if conn_specs.secure:
            ftp = FTP_TLS(conn_specs.host)
            ftp.auth()
        else:
            ftp = FTP(conn_specs.host)

        # ftp.connect(conn_specs.host, conn_specs.port)
        logger.debug(f'Connected to "{server}". Logging in...')
        ftp.login(conn_specs.username, conn_specs.password)
        logger.debug(f'Established connection to "{server}". Saving to cache')
        _connection_cache[server] = ftp
        return ftp
    else:
        ftp = _connection_cache[server]
        ftp.cwd('/')
        logger.debug(f'Recycling connection to "{server}"')
        return ftp

