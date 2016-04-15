from enum import Enum


class EventStatus(Enum):

    FAILED = 'FAILED'
    NOT_CONNECTED = 'NOT_CONNECTED'
    SENT = 'SENT'

    @classmethod
    def failed(cls):
        return [cls.FAILED, cls.NOT_CONNECTED]
