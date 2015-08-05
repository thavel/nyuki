import logging
import functools
import sys
import inspect


log = logging.getLogger(__name__)


class EventError(Exception):
    """
    Base class for event exception
    """


class InvalidEventError(EventError):
    def __init__(self, event, *args, **kwargs):
        msg = "Invalid event: %s" % event
        super(InvalidEventError, self).__init__(msg, *args, **kwargs)


class RegisterEvent(type):
    def __init__(cls, name, bases, attrs):
        cls._event_handlers = {}
        for key, val in attrs.items():
            names = getattr(val, '_events', [])
            for n in names:
                try:
                    cls._event_handlers[n].append(val)
                except KeyError:
                    cls._event_handlers[n] = [val]


class EventMetaBase(type):
    """
    Metaclass that stores the method that will be called on event.
    """

    def __init__(cls, *args, **kwargs):
        super(EventMetaBase, cls).__init__(*args, **kwargs)
        cls.event_handlers = [{
            'attr': 'my_event_name',
            'add': 'add_event_handler'
        }]

    def __call__(cls, *args, **kwargs):
        instance = super(EventMetaBase, cls).__call__(*args, **kwargs)
        methods = [getattr(instance, m) for m in dir(cls)if not m.startswith("__")]
        for method in methods:
            for event_handler in cls.event_handlers:
                if hasattr(method, event_handler['attr']):
                    _add_method = getattr(instance, event_handler['add'])
                    _event_name = getattr(method, event_handler['attr'])
                    _pointer = getattr(instance, method.__name__)
                    _add_method(_event_name, _pointer)
        return instance


def list_events(name):
    """
    A utility method to list all the events (inheriting from `Event`) defined
    in a module.
    """
    module = sys.modules[name]
    members = inspect.getmembers(module)
    events = set()
    for name, obj in members:
        if inspect.isclass(obj) \
            and issubclass(obj, Event) \
                and obj is not Event:
            events.add(obj)
    return events


def on_event(*names):
    """
    A decorator that adds a `_register` attribute to each method/function that
    should be called upon firing an event.
    Several event names can be registered at once.
    """
    def decorator(func):
        func._events = set(names)

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


class Event(object):
    """
    Base event class.
    """
    @property
    def name(self):
        """Return the name of this Event class"""
        return self.__class__.__name__


class EventManager(object):
    """
    Event stack.
    """
    def __init__(self, instance=None):
        self._handlers = {}
        if instance is not None:
            self.register(instance)

    @property
    def handlers(self):
        return self._handlers

    def register(self, instance):
        """
        Registering an object `instance` here means to find methods decorated
        with `@on_event` in that object and populate the `handlers` dict.
        This also to automatically adds to `instance` a helper to the `fire()`
        method.
        """
        for attr in dir(instance):
            try:
                method = getattr(instance, attr)
            except AttributeError as e:
                log.warning('method %s not registered, make sure there is no on_event in %s' % (attr, instance))
                log.exception(e)
            if not inspect.ismethod(method):
                continue
            if hasattr(method, '_events'):
                self.add_handler(method)
        instance.fire = self.fire

    def add_handler(self, method, event_cls=None):
        # if not isfunction(method):
        #     errmsg = "'{func}' is not a method or a function"
        #     raise TypeError(errmsg.format(func=repr(method)))
        if event_cls is not None:
            if not issubclass(event_cls, Event):
                errmsg = "'{evt}' is not a subclass of 'event.Event'"
                raise TypeError(errmsg.format(evt=repr(event_cls)))
            self._handlers.setdefault(event_cls, set()).add(method)
        else:
            for cls in method._events:
                self._handlers.setdefault(cls, set()).add(method)

    def fire(self, event):
        if not isinstance(event, Event):
            errmsg = "'{evt}' is not an instance of 'event.Event'"
            raise TypeError(errmsg.format(evt=repr(event)))
        try:
            handlers = self._handlers[event.__class__]
        except KeyError:
            handlers = set()
        # XXX: need to  make the code below asynchronous (e.g. using aynscio)
        for method in handlers:
            method(event)
