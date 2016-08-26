import ast
from collections import defaultdict
import logging


log = logging.getLogger(__name__)


EXPRESSIONS = [
    # Types of values
    ast.Dict,
    ast.List,
    ast.NameConstant,
    ast.Num,
    ast.Set,
    ast.Str,
    ast.Tuple,
    # Types of operations
    ast.Compare,
    ast.BoolOp,
    ast.UnaryOp
]

OPERATORS = [
    ast.And,
    ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE,
    ast.Gt, ast.GtE,
    ast.In, ast.NotIn,
    ast.Invert,
    ast.Is, ast.IsNot,
    ast.Not,
    ast.Or,
    ast.UAdd,
    ast.USub
]

CONTEXTS = [ast.Load]

AUTHORIZED_TYPES = EXPRESSIONS + OPERATORS + CONTEXTS


def safe_eval(expr):
    """
    Ensures an expression only defines authorized operations (no call to
    functions, no variable assignement...) and evaluates it.
    """
    tree = ast.parse(expr, mode='eval').body
    for node in ast.walk(tree):
        if not type(node) in AUTHORIZED_TYPES:
            raise TypeError("forbidden type {} found in {}".format(node, expr))
    return bool(eval(expr))


class ConditionBlock:

    def __init__(self, conditions):
        # Check there is at least one condition
        if len(conditions) == 0:
            raise ValueError('no condition in condition block')
        # Check first condition is 'if'
        if conditions[0]['type'] != 'if':
            raise TypeError("first condition must be an 'if'")
        # Check next conditions (if any)
        if len(conditions) >= 2:
            for cond in conditions[1:-1]:
                # All intermediate conditions must be 'elif'
                if cond['type'] != 'elif':
                    raise TypeError("expected 'elif' condition,"
                                    " got '{}'".format(cond))
            # The last condition can be either an 'elif' or an 'else'
            if conditions[-1]['type'] not in ('elif', 'else'):
                raise TypeError("last condition must be 'elif' or 'else',"
                                " got '{}'".format(conditions[-1]))
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

    def condition_validated(self, condition, data):
        """
        To be overridden to do your own logic once the condition has
        been validated (True) by `self._evaluate`.
        """
        raise NotImplementedError

    def apply(self, data):
        """
        Iterate through the conditions and stop at first validated condition.
        """
        for condition in self._conditions:
            # If type 'else', set given next tasks and leave
            if condition['type'] == 'else':
                self.condition_validated(condition['rules'], data)
                return
            # Else find the condition and evaluate it
            cleaned = self._clean_condition(condition['condition'], data)
            log.debug('arithmetics: trying %s', condition)
            if safe_eval(cleaned):
                log.debug(
                    'arithmetics: validated condition "%s" as "%s"',
                    condition, cleaned
                )
                self.condition_validated(condition['rules'], data)
                return
