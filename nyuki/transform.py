import logging
import re


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
    CONDITION_REGEX = re.compile(
        r"^(?P<first>('|<).+('|>)) (?P<op>[\!=\>\<\w ]+) (?P<second>('|<).+('|>))$"
    )
    OPS = {
        '==': lambda first, second: first == second,
        '!=': lambda first, second: first != second,
        '>': lambda first, second: int(first) > int(second),
        '>=': lambda first, second: int(first) >= int(second),
        '<=': lambda first, second: int(first) <= int(second),
        '<': lambda first, second: int(first) < int(second),
        'in': lambda first, second: first in second,
        'not in': lambda first, second: first not in second,
        'or': lambda first, second: first or second,
        'and': lambda first, second: first and second,
    }

    def __init__(self, conditions, type=None):
        self._conditions = conditions

    def _clean_condition(self, condition, data):
        """
        Parse the condition and return cleaned 'first', 'second' and 'op'
        variables to use in the lambda condition methods above.
        """
        m = self.CONDITION_REGEX.match(condition)
        if not m:
            log.error('condition failure: %s', condition)
            return

        first = m.group('first')
        second = m.group('second')
        op = m.group('op')

        # Check if 'first' is a key from data
        if first.startswith('<') and first.endswith('>'):
            first = data[first[1:-1]]
        # Check if 'first' is a mutiple-word string
        elif first.startswith("'") and first.endswith("'"):
            first = first[1:-1]

        if second.startswith('<') and second.endswith('>'):
            second = data[second[1:-1]]
        elif second.startswith("'") and second.endswith("'"):
            second = second[1:-1]

        return first, op, second

    def apply(self, data):
        """
        Apply conditions depending on the length of the condition array,
        as it must always start with 'if' and end with 'elif', 'else'
        or nothing.
        """
        for cond in self._conditions:
            log.critical(cond)
            # If type 'else', apply it and leave
            if cond['type'] == 'else':
                Converter.from_dict(cond).apply(data)
                return
            # Else find the condition and apply it
            first, op, second = self._clean_condition(cond['condition'], data)
            if self.OPS[op](first, second):
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
