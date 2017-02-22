from datetime import datetime
from functools import singledispatch


@singledispatch
def serialize_object(obj):
    """
    Default serializer for python objects.
    """
    return 'Internal server data: {}'.format(type(obj))


@serialize_object.register(datetime)
def _serialize_datetime(dt):
    """
    Datetime serializer.
    """
    return dt.isoformat()
