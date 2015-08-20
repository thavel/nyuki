import json
from slixmpp.xmlstream import ElementBase


class Request(ElementBase):

    namespace = 'nyuki:request'
    name = 'request'
    plugin_attrib = 'request'
    interfaces = set(['capability', 'body'])
    sub_interfaces = interfaces

    def getBody(self):
        return json.loads(self._get_sub_text('body', '{}'))

    def setBody(self, body):
        self._set_sub_text('body', json.dumps(body))


class Response(ElementBase):

    namespace = 'nyuki:request'
    name = 'response'
    plugin_attrib = 'response'
    interfaces = set(['status', 'body'])
    sub_interfaces = interfaces

    def getBody(self):
        return json.loads(self._get_sub_text('body', '{}'))

    def setBody(self, body):
        self._set_sub_text('body', json.dumps(body))

    def getStatus(self):
        status = self._get_sub_text('status', '')
        return int(status) if status else None

    def setStatus(self, status):
        self._set_sub_text('status', str(status))
