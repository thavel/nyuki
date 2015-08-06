import re

"""
Overall philosophy
dict => data processing block => dict

Detailed data flow within a data processing block
This is an object that embeds an ordered list of rules to apply.
dict => enter data processing block
     => apply 1st rule
        => extract field from dict
        => apply operation to field
        => update dict with operation's output
     => apply 2nd rule
        => ...
There can be only 1 type of rule within a data processing block
"""


# Inspired from https://github.com/faif/python-patterns/blob/master/registry.py
class _RegisteredRules(type):
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


class _ListRules(list):
    """
    Subclass of `list()` that makes sure each element of it is an instance of
    a predefined class (e.g. `Search()`).
    """
    def __init__(self, rule_cls, *iterable):
        super(_ListRules, self).__init__()
        self._rule_cls = rule_cls
        if iterable:
            self.extend(*iterable)

    def _check_type(self, item):
        if self._rule_cls is not None and not isinstance(item, self._rule_cls):
            err = 'item is not of type {cls}'
            raise TypeError(err.format(cls=self._rule_cls.__name__))

    def append(self, item):
        """
        Check the object type of 'item' before appending to the list.
        """
        self._check_type(item)
        super(_ListRules, self).append(item)

    def extend(self, iterable):
        """
        Scan through 'iterable' to check object types before extending the
        list.
        """
        for item in iterable:
            self._check_type(item)
        super(_ListRules, self).extend(iterable)

    def insert(self, index, item):
        """
        Check the object type of 'item' before appending to the list.
        """
        self._check_type(item)
        super(_ListRules, self).insert(index, item)


class Converter(object):
    """
    A base class that can apply a (ordered) list of rules to a dict.
    """
    def __init__(self, rule_cls, rules=[]):
        if not issubclass(rule_cls, _Rule):
            err = '{obj} is not a subclass of _Rule'
            raise TypeError(err.format(obj=rule_cls))
        self._rule_cls = rule_cls
        self._rules = _ListRules(rule_cls, rules)

    @property
    def type(self):
        return self._rule_cls.TYPENAME

    @property
    def rules(self):
        return self._rules

    @classmethod
    def from_dict(cls, config):
        """
        Create a `Converter()` object from dict 'config'. The dict must look
        like the following:
            {
                "type": <rule-type-name>,       # lower-case
                "rules": [
                    {"fieldname": <name>, ...}, # + rule-type dependent items
                    {"fieldname": <name>, ...},
                ]
            }
        """
        rule_cls = _RegisteredRules.get()[config['type']]
        rules = []
        for params in config['rules']:
            rules.append(rule_cls(**params))
        return cls(rule_cls, rules=rules)

    def apply(self, data):
        """
        Apply each rule sequentially to `data` (in-place update)
        """
        for rule in self.rules:
            rule.apply(data)


class _Rule(metaclass=_RegisteredRules):
    """
    A rule is applied to a dict and may update that dict (in-place update).
    Only one field from the input dict can be processed within a rule.
    """
    TYPENAME = None

    def __init__(self, fieldname, **kwargs):
        self.fieldname = fieldname
        self.config = kwargs
        self.configure()

    def configure(self):
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

    Valid `__init__` kwargs are: 'pattern', 'flags'
    """
    def _compile(self, pattern, flags=0):
        self.config['regexp'] = re.compile(pattern, flags=flags)

    def configure(self):
        pattern, flags = self.config['pattern'], self.config.get('flags')
        self._compile(pattern, flags=flags)

    def _run_regexp(self, string):
        pass

    def apply(self, data):
        try:
            string = data[self.fieldname]
            resdict = self._run_regexp(string)
        except KeyError:
            # no data to process
            pass
        else:
            data.update(resdict)


class _MatchSearchRule(_RegexpRule):
    """
    Match and search operations basically share a common logic: when the
    operation produces a match what matters is the resulting groupdict.

    Valid `__init__` kwargs are: 'pattern', 'flags', 'pos', 'endpos'
    """
    def configure(self):
        super(_MatchSearchRule, self).configure()
        pos, endpos = self.config['pos'], self.config['endpos']
        pos_args = tuple(f for f in (pos, endpos) if f is not None)
        self.config['pos_args'] = pos_args

    def _run_regexp(self, string):
        args = (string,) + self.config['pos_args']
        match = getattr(self.config['regexp'], self.TYPENAME)(*args)
        if match is not None:
            return match.groupdict()
        else:
            return {}


# Search.TYPENAME
# s = Search(*args, **kwargs)
# s._configure(*args, **kwargs)
# s.fieldname
# s.config
# s.apply(<dict>)
class Search(_MatchSearchRule):
    """
    Scan through a string looking for the first location where the regular
    expression pattern produces a match.

    Valid `__init__` kwargs are: see `_MatchSearchRule`
    """


class Match(_MatchSearchRule):
    """
    Check if zero or more characters at the beginning of a string match the
    regular expression pattern.

    Valid `__init__` kwargs are: see `_MatchSearchRule`
    """


class Sub(_RegexpRule):
    """
    Build a string obtained by replacing the leftmost non-overlapping
    occurrences of regexp pattern in fieldname from `data` by a replacement
    string.

    Valid `__init__` kwargs are: 'pattern', 'flags', 'repl', 'count'
    """
    def _run_regexp(self, string):
        regexp, repl = self.config['regexp'], self.config['repl']
        res = regexp.sub(repl, string, count=self.config['count'])
        return {self.fieldname: res}


class Set(_Rule):
    """
    Set or update a field in the `data` dict.

    Valid `__init__` kwargs is: 'value'
    """
    def configure(self):
        pass

    def apply(self, data):
        data[self.fieldname] = self.config['value']


class Unset(_Rule):
    """
    Remove a field from the `data` dict.
    """
    def configure(self):
        pass

    def apply(self, data):
        try:
            del data[self.fieldname]
        except KeyError:
            pass


class Lookup(_Rule):
    """
    Implements a dead-simple lookup table which perform case sensitive
    (default) or insensitive (icase=True) lookups.

    Valid `__init__` kwargs are: 'icase', 'table' (a dict)
    """
    def configure(self):
        self.config['table'] = LookupTable(self.config['table'])

    def apply(self, data):
        """
        The 1st entry in the lookup table that matches the value from `data`
        replaces it. Note that entries in the lookup table are evaluated in an
        unpredictable order.
        """
        field = data[self.fieldname]
        for regexp, value in self.config['table'].items():
            if regexp.search(field) is not None:
                data[self.fieldname] = value
                break


# Inspired from this post:
# http://stackoverflow.com/questions/2060972/subclassing-python-dictionary-to-override-setitem
class LookupTable(dict):
    """
    Simple wrapper around dict() to build a lookup table where keys are
    compiled regular expressions.
    """
    def __init__(self, *args, **kwargs):
        super(LookupTable, self).__init__()
        self.update(*args, **kwargs)

    def __setitem__(self, re_spec, value):
        """
        're_spec' is expected to be a dict with 'pattern' and 'flags' keys.
        If 're_spec' happens to be a string it is compiled as is without any
        other regexp flags.
        """
        if isinstance(re_spec, dict):
            regexp = re.compile(**re_spec)
        else:
            regexp = re.compile(re_spec)
        super(LookupTable, self).__setitem__(regexp, value)

    def update(self, *args, **kwargs):
        if args:
            if len(args) > 1:
                raise TypeError("update expected at most 1 arguments, got"
                                " {len}".format(len=len(args)))
            other = dict(args[0])
            for key in other:
                self[key] = other[key]
        for key in kwargs:
            self[key] = kwargs[key]

    def setdefault(self, key, value=None):
        if key not in self:
            self[key] = value
        return self[key]
