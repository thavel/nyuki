from nyuki.services import Service


class Discovery(type):

    _REGISTRY = {}

    def __new__(mcs, name, bases, attrs):
        new_mcs = type.__new__(mcs, name, bases, attrs)
        if new_mcs.SCHEME:
            mcs._REGISTRY[new_mcs.SCHEME] = new_mcs
        return new_mcs

    @classmethod
    def get(mcs, name):
        method = mcs._REGISTRY.get(name)
        if not method:
            raise ValueError("Unknown discovery method '{}'".format(name))
        return mcs._REGISTRY[name]


class DiscoveryService(Service, metaclass=Discovery):

    SERVICE = 'discovery'
    SCHEME = None

    def register(self, callback):
        raise NotImplementedError()


from .dns import DnsDiscovery
