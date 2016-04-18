from enum import Enum


class EventStatus(Enum):

    FAILED = 'FAILED'
    PENDING = 'PENDING'
    SENT = 'SENT'

    @classmethod
    def not_sent(cls):
        return [cls.FAILED, cls.PENDING]
