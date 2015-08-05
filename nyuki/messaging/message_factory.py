from enum import Enum
import json
import uuid


class Codes(Enum):
    # Request received and accepted by the bus.
    TRYING = '100_TRYING'
    # Delivery attempted to target system.
    RINGING = '180_RINGING'
    CALL_IS_BEING_FORWARDED = '181_CALL_IS_BEING_FORWARDED'
    QUEUED = '182_QUEUED'
    # Operation is still in progress (may be repeated any number of times).
    SESSION_PROGRESS = '183_SESSION_PROGRESS'
    # Request successful.
    OK = '200_OK'
    ACCEPTED = '202_ACCEPTED'
    REJECTED = '203_REJECTED'
    # Request assumed to be successful, but the target system can't give
    # any completion information.
    NO_NOTIFICATION = '204_NO_NOTIFICATION'
    # Generic response for syntactically or semantically invalid requests
    # (either at the bus level, or at a higher level).
    BAD_REQUEST = '400_BAD_REQUEST'
    # Invalid GET target, or recipient is known not to exist.
    NOT_FOUND = '404_NOT_FOUND'
    # Given bus method ('PROCESS', 'INVOKE', etc.) not supported by agent.
    METHOD_NOT_ALLOWED = '405_METHOD_NOT_ALLOWED'
    NOT_ACCEPTABLE = '406_NOT_ACCEPTABLE'
    # Event deadline reached without a conclusive response
    REQUEST_TIMEOUT = '408_REQUEST_TIMEOUT'
    # Address scheme or other not supported by agent.
    UNSUPPORTED_MEDIA_TYPE = '415_UNSUPPORTED_MEDIA_TYPE'
    TOO_MANY_REQUESTS = '429_TOO_MANY_REQUESTS'
    # Request could not be processed at the moment because the
    # corresponding feature is disabled by the current configuration
    FEATURE_DISABLED = '461_FEATURE_DISABLED'
    # Recipient may exist, but delivering a message to it failed
    # (e.g. the recipient isn't connected, its mailbox is full, etc.)
    TEMPORARILY_UNAVAILABLE = '480_TEMPORARILY_UNAVAILABLE'
    # Unknown request id in response.
    UNKNOWN_TRANSACTION = '481_UNKNOWN_TRANSACTION'
    # Recipient received a message but rejected it
    # (e.g. confirmation failure)
    USER_BUSY = '486_USER_BUSY'
    # A similar request was received earlier and is still being processed.
    REQUEST_PENDING = '491_REQUEST_PENDING'
    # Unexpected internal error when processing the request.
    INTERNAL_SERVER_ERROR = '500_INTERNAL_SERVER_ERROR'
    # Unsupported INVOKE action.
    NOT_IMPLEMENTED = '501_NOT_IMPLEMENTED'
    # Erroneous response from a downstream server / equipment.
    BAD_GATEWAY = '502_BAD_GATEWAY'
    # Agent not running / does not exist
    SERVICE_UNAVAILABLE = '503_SERVICE_UNAVAILABLE'
    # Protocol-specific timeout with a downstream equipment.
    SERVER_TIMEOUT = '504_SERVER_TIMEOUT'

    @staticmethod
    def in_values(value):
        return value in [c.value for c in Codes.__members__.values()]


class MessageFactory(object):

    def __init__(self, xmpp_client):
        self.xmpp_client = xmpp_client
        self.requests = dict()

    def generate_uid(self):
        return str(uuid.uuid4())

    def build_message_for_unicast(self, msg, to, subject="PROCESS",
                                  is_json=False):
        if is_json:
            return self.xmpp_client.make_message(mto=to, mbody=json.dumps(msg),
                                                 mtype='normal',
                                                 msubject=subject)
        else:
            return self.xmpp_client.make_message(mto=to, mbody=msg,
                                                 mtype='normal',
                                                 msubject=subject)

    def build_request_unicast_message(self, msg, to, subject="PROCESS",
                                      session=None, is_json=False, msg_id=None):

        session = session or {}
        subject = subject.lower()
        xmpp_message = self.build_message_for_unicast(msg, to, subject,
                                                      is_json)
        xmpp_message['id'] = msg_id or self.generate_uid()
        self.requests[xmpp_message['id']] = session
        return xmpp_message

    def build_response_unicast_message(self, msg, to, subject, msg_id,
                                       is_json=False):
        if isinstance(subject, Codes):
            subject = subject.value
        elif not Codes.in_values(subject):
            raise ValueError("subject must be a response type")

        xmpp_message = self.build_message_for_unicast(
            msg, to, subject, is_json)
        xmpp_message['id'] = msg_id
        return xmpp_message
