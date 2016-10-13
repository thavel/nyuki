import logging
import re
from copy import deepcopy

from .evaluate import ConditionBlock


log = logging.getLogger(__name__)


class TraceableDict(dict):
    """
    Python dict-based class that tracks any changes.
    Format:
        {"action": "add", "key": <key>, "value": <new-value>},
        {"action": "remove", "key": <key>, "value": <old-value>},
        {"action": "update", "key": <key>, "old_value": <old-value>,
                                           "new_value": <new-value>},
    """
    def __init__(self, dict2):
        self._changes = []
        super().__init__(deepcopy(dict2))

    def __setitem__(self, key, value):
        if key not in self:
            self._changes.append({
                'action': 'add',
                'key': key,
                'value': deepcopy(value)
            })
        else:
            self._changes.append({
                'action': 'update',
                'key': key,
                'old_value': deepcopy(self[key]),
                'new_value': deepcopy(value)
            })
        super().__setitem__(key, value)

    def __delitem__(self, key):
        self._changes.append({
            'action': 'remove',
            'key': key,
            'value': deepcopy(self[key])
        })
        super().__delitem__(key)

    def update(self, dict2=None, **kwargs):
        for key in dict2:
            if key not in self:
                self._changes.append({
                    'action': 'add',
                    'key': key,
                    'value': deepcopy(dict2[key])
                })
            else:
                self._changes.append({
                    'action': 'update',
                    'key': key,
                    'old_value': deepcopy(self[key]),
                    'new_value': deepcopy(dict2[key])
                })
        super().update(dict2, **kwargs)

    @property
    def changes(self):
        return self._changes


# Inspired from https://github.com/faif/python-patterns/blob/master/registry.py
class _RegisteredRule(type):
    """
    This metaclass is designed to register automatically public rule classes
    that inherit from `_Rules()`.
    """
    _registry = {}

    def __new__(mcs, name, bases, attrs):
        cls = type.__new__(mcs, name, bases, attrs)
        name = cls.TYPENAME or cls.__name__.lower()
        if not name.startswith('_'):
            cls.TYPENAME = name
            mcs._registry[name] = cls
        return cls

    @classmethod
    def get(mcs, rtype):
        return mcs._registry[rtype]


class Converter(object):

    """
    A sequence of `_Rule` objects intended to be applied on a dict.
    """

    def __init__(self, rules=None):
        self._rules = rules or []

    @property
    def rules(self):
        return self._rules

    @classmethod
    def from_dict(cls, config):
        """
        Create a `Converter` object from dict 'config'. The dict must look like
        the following:
        {
            "rules": [
                {"type": <rule-type-name>, "fieldname": <name>, ...},
                {"type": <rule-type-name>, "fieldname": <name>, ...},
                {"type": "condition-block", "conditions": [...]},
                {"type": <rule-type-name>, "fieldname": <name>, ...},
            ]
        }
        """
        rules = []
        for rule in config['rules']:
            params = rule.copy()
            rtype = params.pop('type')
            rule_cls = _RegisteredRule.get(rtype)
            rules.append(rule_cls(**params))
        return cls(rules=rules)

    def apply(self, data):
        rules = []
        for rule in self.rules:
            diff = rule.apply(data)
            rules.append(diff)
        return {'rules': rules}


class FactoryConditionBlock(ConditionBlock, metaclass=_RegisteredRule):

    TYPENAME = 'condition-block'

    def __init__(self, conditions):
        super().__init__(conditions)
        self._changes = {'type': self.TYPENAME, 'conditions': []}

    def condition_validated(self, rules, data):
        """
        Apply rules on data upon validating a condition.
        """
        diff = Converter.from_dict({'rules': rules}).apply(data)
        self._changes['conditions'] = diff['rules']

    def apply(self, data):
        super().apply(data)
        return self._changes


class _Rule(metaclass=_RegisteredRule):

    """
    A rule extracts an entry from a dict , performs an operation on the dict
    and updates the dict with the result of that operation (in-place update).
    Only one field from the input dict can be processed within a rule.
    """

    # Public subclasses of `_Rule` will have a TYPENAME attr set to classname
    # (lowercase) if not set in the subclass itself.
    TYPENAME = None

    def __init__(self, fieldname, *args, **kwargs):
        self.fieldname = fieldname
        self._configure(*args, **kwargs)

    def _configure(self, *args, **kwargs):
        """
        Configure the rule to be applied (e.g. compile a regexp) so that
        everything is ready at runtime to apply it.
        """
        raise NotImplementedError

    @staticmethod
    def track_changes(func):
        """
        Decorator for `Rule.apply(<data>)` methods that return a JSON-formatted
        diff of the changes made by the method itself.
        """
        def wrapper(self, data):
            # Handle data through a traceable dict
            tracker = TraceableDict(data)
            func(self, tracker)
            # We want to keep the object reference
            data.clear()
            data.update(tracker)
            return {'type': self.TYPENAME, 'changes': tracker.changes}

        return wrapper

    def apply(self, data):
        """
        Execute an operation on one field of the dict `data` and returns an
        diff.
        """
        raise NotImplementedError


class _RegexpRule(_Rule):

    """
    Define a regular expression that shall be applied through several kinds of
    operations to a string.
    If the regexp pattern has named capturing parenthesis it is used to update
    the `data` dict passed to `apply()`. If a group from the match object and
    a key from `data` have the same name, the group overrides the existing
    dict value.
    """

    def _configure(self, pattern, flags=0):
        self.regexp = re.compile(pattern, flags=flags)

    def _run_regexp(self, string):
        raise NotImplementedError

    @_Rule.track_changes
    def apply(self, data):
        try:
            string = data[self.fieldname]
        except KeyError:
            # No data to process
            log.debug('Regexp : unknown field %s, ignoring', self.fieldname)
        else:
            resdict = self._run_regexp(string)
            data.update(resdict)


class Extract(_RegexpRule):

    """
    Scan through a string looking for the first location where the regular
    expression pattern produces a match. What matters is the resulting dict of
    captured substrings.
    """

    def _configure(self, pattern, flags=0, pos=None, endpos=None):
        super()._configure(pattern, flags=flags)
        if not self.regexp.groupindex:
            raise TypeError("'{pattern}' has no named capturing group".format(
                            pattern=pattern))
        self._pos_args = tuple(f for f in (pos, endpos) if f is not None)

    def _run_regexp(self, string):
        args = (string,) + self._pos_args
        match = self.regexp.search(*args)
        if match is not None:
            return match.groupdict()
        else:
            return {}


class Sub(_RegexpRule):

    """
    Build a string obtained by replacing the leftmost non-overlapping
    occurrences of regexp pattern in fieldname from `data` by a replacement
    string.
    """

    def _configure(self, pattern, repl, flags=0, count=0):
        super()._configure(pattern, flags=flags)
        self.repl, self.count = repl, count

    def _run_regexp(self, string):
        res = self.regexp.sub(self.repl, string, count=self.count)
        return {self.fieldname: res}


class Set(_Rule):

    """
    Set or update a field in the `data` dict.
    """

    def _configure(self, value):
        self.value = value

    @_Rule.track_changes
    def apply(self, data):
        data[self.fieldname] = self.value


class Copy(_Rule):

    """
    Copy a data into another field.
    """

    def _configure(self, copy):
        self.copy = copy

    @_Rule.track_changes
    def apply(self, data):
        try:
            data[self.copy] = data[self.fieldname]
        except KeyError:
            log.debug('Copy : unknown field %s, ignoring', self.fieldname)


class Unset(_Rule):

    """
    Remove a field from the `data` dict.
    """

    def _configure(self):
        pass

    @_Rule.track_changes
    def apply(self, data):
        try:
            del data[self.fieldname]
        except KeyError:
            log.debug('Unset : unknown field %s, ignoring', self.fieldname)


class Lookup(_Rule):

    """
    Implements a dead-simple lookup table which perform case sensitive
    (default) or insensitive (icase=True) lookups.
    """

    def _configure(self, table=None, icase=False):
        self.table = table or dict()
        self.icase = icase
        if icase:
            self.table = {k.lower(): v for k, v in table.items()}

    @_Rule.track_changes
    def apply(self, data):
        """
        The 1st entry in the lookup table that matches the string from `data`
        replaces it. Note that entries in the lookup table are evaluated in an
        unpredictable order.
        """
        try:
            fieldval = str(data[self.fieldname])
            if self.icase:
                fieldval = fieldval.lower()
            data[self.fieldname] = self.table[fieldval]
        except KeyError as err:
            log.debug("Lookup: fieldname '%s' not in data, ignoring", err)
            return


class Lower(_Rule):

    """
    Lower case a string.
    """

    def _configure(self):
        pass

    @_Rule.track_changes
    def apply(self, data):
        fieldval = data[self.fieldname]
        data[self.fieldname] = fieldval.lower()


class Upper(_Rule):

    """
    Upper case a string.
    """

    def _configure(self):
        pass

    @_Rule.track_changes
    def apply(self, data):
        fieldval = data[self.fieldname]
        data[self.fieldname] = fieldval.upper()
