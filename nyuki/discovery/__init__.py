from nyuki.services import Service


class Discovery(type):

    _REGISTRY = {}

    def __new__(mcs, name, bases, attrs):
        new_mcs = type.__new__(mcs, name, bases, attrs)
        mcs._REGISTRY[new_mcs.SCHEME] = new_mcs
        return new_mcs

    @classmethod
    def get(mcs, name):
        return mcs._REGISTRY[name]


class DiscoveryService(Service, metaclass=Discovery):

    SERVICE = 'discovery'
    SCHEME = None

    def register(self, callback):
        raise NotImplementedError()
