from collections import defaultdict
import logging
import re

from nyuki.workflow.tasks.utils.arithmetics import arithmetic_eval


log = logging.getLogger(__name__)


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
    def get(mcs):
        return mcs._registry


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
            rule_cls = _RegisteredRule.get()[rule['type']]
            rules.append(rule_cls(**rule))
        return cls(rules=rules)

    def apply(self, data):
        for rule in self.rules:
            rule.apply(data)


class ConditionBlock(metaclass=_RegisteredRule):

    TYPENAME = 'condition-block'

    def __init__(self, conditions, type=None):
        # Check there is at least one condition
        if len(conditions) == 0:
            raise ValueError('Condition block must contain at least one condition')
        # Check first condition is 'if'
        if conditions[0]['type'] != 'if':
            raise TypeError("First condition type must be 'if'")
        # Check no 'if' or 'else' are in-between
        if len(conditions) >= 2:
            if conditions[-1]['type'] == 'if':
                raise TypeError("Last condition type must not be 'if'")
            mid_condition_types = [c['type'] for c in conditions[1:-1]]
            if 'if' in mid_condition_types or 'else' in mid_condition_types:
                raise TypeError(
                    "'if' or 'else' must be respectively first and last types"
                )
        self._conditions = conditions

    def _clean_condition(self, condition, data):
        """
        Format the condition string:
        nb: strings should be {some_string!r} (includes '')
        """
        # Unknown fields will be converted to None
        format_fields = defaultdict(lambda: None)
        format_fields.update(data)
        return condition.format(**format_fields)

    def apply(self, data):
        """
        Apply conditions depending on the length of the condition array,
        as it must always start with 'if' and end with 'elif', 'else'
        or nothing.
        """
        for cond in self._conditions:
            # If type 'else', apply it and leave
            if cond['type'] == 'else':
                Converter.from_dict(cond).apply(data)
                return
            # Else find the condition and apply it
            cleaned = self._clean_condition(cond['condition'], data)
            log.debug('arithmetics: trying %s', cond['condition'])
            if arithmetic_eval(cleaned):
                log.debug(
                    'arithmetics: validated condition "%s" as "%s"',
                    cond['condition'],
                    cleaned
                )
                Converter.from_dict(cond).apply(data)
                return


class _Rule(metaclass=_RegisteredRule):

    """
    A rule extracts an entry from a dict , performs an operation on the dict
    and updates the dict with the result of that operation (in-place update).
    Only one field from the input dict can be processed within a rule.
    """

    # Public subclasses of `_Rule` will have a TYPENAME attr set to classname
    # (lowercase) if not set in the subclass itself.
    TYPENAME = None

    def __init__(self, fieldname, *args, type=None, **kwargs):
        self.fieldname = fieldname
        self._configure(*args, **kwargs)

    def _configure(self, *args, **kwargs):
        """
        Configure the rule to be applied (e.g. compile a regexp) so that
        everything is ready at runtime to apply it.
        """
        raise NotImplementedError

    def apply(self, data):
        """
        Execute an operation on one field of the dict `data` and returns an
        updated dict. If no data could be processed, this method must return
        the unchanged `data` dict.
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

    def apply(self, data):
        data[self.fieldname] = self.value


class Unset(_Rule):

    """
    Remove a field from the `data` dict.
    """

    def _configure(self):
        pass

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

    def apply(self, data):
        """
        The 1st entry in the lookup table that matches the string from `data`
        replaces it. Note that entries in the lookup table are evaluated in an
        unpredictable order.
        """
        try:
            fieldval = data[self.fieldname]
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

    def apply(self, data):
        fieldval = data[self.fieldname]
        data[self.fieldname] = fieldval.lower()


class Upper(_Rule):

    """
    Upper case a string.
    """

    def _configure(self):
        pass

    def apply(self, data):
        fieldval = data[self.fieldname]
        data[self.fieldname] = fieldval.upper()
