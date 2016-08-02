from datetime import datetime


def serialize_bus_event(obj):
    """
    JSON default serializer for python objects
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    return repr(obj)
