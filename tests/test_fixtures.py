from pathlib import Path
from typing import Dict
import pytest


@pytest.fixture
def root_path() -> Path:
    return Path('./tests')


@pytest.fixture
def data_folder(root_path) -> Path:
    return root_path / 'data'


