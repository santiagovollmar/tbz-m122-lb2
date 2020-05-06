from typing import List
from math import floor
from pydantic import BaseModel, validator
from datetime import datetime, timedelta


class DictWrapper:  # TODO probably
    pass


class Invoice(BaseModel):
    id: str
    account: str
    city: str
    timestamp: datetime
    target_deadline: timedelta
    recipient: 'ContactDetails'
    sender: 'ContactDetails'
    items: List['InvoiceItem']


class ContactDetails(BaseModel):
    id: str
    company: str = None
    human: str = None
    street: str
    city: str
    zip: int
    vat_id: str = None
    email: str = None

    def yield_address_lines(self):
        line_order = ['company', 'human', 'street', 'city', 'vat_id']

        for line in line_order:
            content = getattr(self, line, None)

            if content is not None:
                if line == 'city':
                    content = f'{self.zip} {content}'

                yield content


class InvoiceItem(BaseModel):
    description: str
    price: int  # rappen
    count: int
    total: int  # rappen
    vat_multiplier: float

    @validator('price', 'total', pre=True)
    def parse_chf(cls, v):
        print('IN', type(v), v)
        if isinstance(v, str):
            v = float(v)

        if isinstance(v, float) or isinstance(v, int):
            v *= 100
        else:
            ValueError(f'{v} is not a valid int or float')

        if isinstance(v, float):
            if floor(v) != v:
                ValueError(f'Precision too high')

            v = int(v)

        print('OUT', type(v), v)
        return v

    @validator('total')
    def adds_up(cls, v, values):
        if {'price', 'count'} < values.keys():
            total, price, count = v, values['price'], values['count']

            if price * count != total:
                raise ValueError('total does not reflect item count * item price')

        return v


Invoice.update_forward_refs()
