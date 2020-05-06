import os
import os.path

from typing import List, Union, Dict, Any, Optional

from loguru import logger
from pydantic import BaseModel, validator
from yaml import load, add_constructor

try:
    from yaml import CLoader as Loader
except:
    from yaml import Loader


_config: Optional['Config'] = None


def config() -> 'Config':
    global _config

    if _config:
        return _config
    else:
        # read config
        add_constructor('!env', _env_tag_handler, Loader)
        yaml_dict = read_config(path=_select_config_file())
        _config = Config(**yaml_dict)
        return _config


def read_config(*, path: str = None, data: Union[str, bytes] = None) -> Dict[str, Any]:
    if path is not None:
        with open(path, 'rb') as f:
            logger.info(f'Reading configuration from {path}')
            data = f.read()

    return load(data, Loader=Loader)


def _select_config_file():
    # locate file
    extensions = ['.yml', '.yaml', '.json']
    names = ['config', 'configuration']
    file_list = [n+e for n in names for e in extensions]

    for path in file_list:
        if os.path.isfile(path):
            return path


def _env_tag_handler(loader, node):
    return os.getenv(node.value)


class TemplateConfig(BaseModel):
    file: str
    name_template: str


class TemplatesConfig(BaseModel):
    search_in: str = './templates'
    xml_template: 'TemplateConfig' = TemplateConfig(file='invoice.xml', name_template='{account}_{id}_invoice.xml')
    txt_template: 'TemplateConfig' = TemplateConfig(file='invoice.txt', name_template='{account}_{id}_invoice.txt')


class Config(BaseModel):
    templates: 'TemplatesConfig' = TemplatesConfig()
    ftp: 'FtpConfig'
    locations: 'LocationsConfig'
    email: 'EmailConfig'
    archive: str = './archive'


class FtpConfig(BaseModel):
    in_server: 'FtpServerConfig'
    out_server: 'FtpServerConfig'


class FtpServerConfig(BaseModel):
    host: str
    secure: bool
    port: int = None
    username: str
    password: str

    @validator('port', always=True)
    def default_port(cls, v, values):
        if v is not None:
            return v

        try:
            if values['secure']:
                return 22
            else:
                return 21
        except KeyError:
            raise ValueError('Field "secure" not provided')


class LocationsConfig(BaseModel):
    data_scan: 'LocationSpecConfig'
    receipt_scan: 'LocationSpecConfig'
    invoice_push: 'LocationSpecConfig'
    archive_push: 'LocationSpecConfig'


class LocationSpecConfig(BaseModel):
    server: str
    path: str
    pattern: str = None


class EmailConfig(BaseModel):
    hostname: str
    port: int
    username: str
    password: str


Config.update_forward_refs()
FtpConfig.update_forward_refs()
FtpServerConfig.update_forward_refs()
LocationsConfig.update_forward_refs()
