from datetime import datetime


def from_isoformat(iso):
    return datetime.strptime(iso, '%Y-%m-%dT%H:%M:%S.%f')
