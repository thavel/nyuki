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


class _Rule(object):
    """
    A rule is applied to a dict and may update that dict (in-place update).
    Only one field from the input dict can be processed within a rule.
    """
    def __init__(self, fieldname, **kwargs):
        self.fieldname = fieldname
        self.configure(**kwargs)

    def configure(self, *args, **kwargs):
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
    operations to a string read from the input `data` dict.
    If the regexp pattern has named capturing parenthesis it is used to update
    the input dict. If a group from the match object and a key from the input
    dict have the same name, the group overrides the existing dict value.
    """
    def _compile(self, pattern, flags=0):
        self.regexp = re.compile(pattern, flags=flags)

    def _set_params(self, **kwargs):
        pass

    def configure(self, pattern='', flags=0, **kwargs):
        self._compile(pattern, flags=flags)
        self._set_params(**kwargs)

    def _run_regexp(self, *args, **kwargs):
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
    """
    def _set_params(self, pos=None, endpos=None):
        self.pos = pos
        self.endpos = endpos
        self._pos_args = tuple(f for f in (pos, endpos) if f is not None)

    def _run_regexp(self, string):
        args = (string,) + self._pos_args
        match = getattr(self.regexp, self._regexp_op)(*args)
        if match is not None:
            return match.groupdict()
        else:
            return {}


class Search(_RegexpRule):
    """
    Scan through a string looking for the first location where the regular
    expression pattern produces a match.
    """
    _regexp_op = 'search'


class Match(_RegexpRule):
    """
    Check if zero or more characters at the beginning of a string match the
    regular expression pattern.
    """
    _regexp_op = 'match'


class Sub(_RegexpRule):
    """
    Build a string obtained by replacing the leftmost non-overlapping
    occurrences of regexp pattern in fieldname from `data` by a replacement
    string.
    """
    def _set_params(self, repl='', count=0):
        self.repl = repl
        self.count = count

    def _run_regexp(self, string):
        res = self.regexp.sub(self.repl, string, count=self.count)
        return {self.fieldname: res}


class Set(_Rule):
    """
    Set or update a field in the `data` dict.
    """
    def configure(self, value=''):
        self.value = value

    def apply(self, data):
        data[self.fieldname] = self.value


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
    Implements a lookup table where the input value from `data` must match a
    regexp to be replaced by a new value from the table.
    """
    def configure(self, table={}):
        """
        'table' is a dict where keys can be a dict or a string (see LookupTable)
        """
        self.table = LookupTable(table)

    def apply(self, data):
        """
        The 1st entry in the lookup table that matches the value from `data`
        replaces it. Note that entries in the lookup table are evaluated in an
        unpredictable order.
        """
        field = data[self.fieldname]
        for regexp, value in self.table.items():
            if regexp.search(field) is not None:
                data[self.fieldname] = value
                break


# Inspired from this post:
# http://stackoverflow.com/questions/2060972/subclassing-python-dictionary-to-override-setitem
class LookupTable(dict):
    """
    Simple wrapper around dict() to build a lookup table where keys are compiled
    regular expressions.
    """
    def __init__(self, *args, **kwargs):
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


class _Converter(object):
    """
    A base class that can execute an ordered list of operations to a dict and
    outputs an updated dict.
    """
    def __init__(self):
        self._ops = []

    def append(self):
        raise NotImplementedError

    def insert(self):
        pass

    def apply(self):
        raise NotImplementedError