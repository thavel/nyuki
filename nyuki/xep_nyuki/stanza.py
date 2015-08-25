import json

from slixmpp.xmlstream import ElementBase


class NyukiRequest(ElementBase):

    name = 'request'
    namespace = 'nyuki'
    interfaces = set(['capability', 'json'])
    sub_interfaces = set(['json'])
    plugin_attrib = 'request'

    def getJson(self):
        return json.loads(self._get_sub_text('json', '{}'))

    def setJson(self, body):
        if body:
            self._set_sub_text('json', json.dumps(body))


class NyukiResponse(ElementBase):

    name = 'response'
    namespace = 'nyuki'
    interfaces = set(['status', 'json'])
    sub_interfaces = set(['json'])
    plugin_attrib = 'response'

    def getJson(self):
        return json.loads(self._get_sub_text('json', '{}'))

    def setJson(self, body):
        if body:
            self._set_sub_text('json', json.dumps(body))

    def getStatus(self):
        try:
            return int(self._get_sub_text('status', ''))
        except ValueError:
            return None

    def setStatus(self, status):
        self._set_sub_text('status', str(status))


class NyukiEvent(ElementBase):

    name = 'event'
    namespace = 'nyuki'
    interfaces = set(['json'])
    sub_interfaces = interfaces
    plugin_attrib = 'event'

    def getJson(self):
        return json.loads(self._get_sub_text('json', '{}'))

    def setJson(self, body):
        if body:
            self._set_sub_text('json', json.dumps(body))
