import ast


TYPES = [
    ast.Dict,
    ast.List,
    ast.NameConstant,
    ast.Num,
    ast.Set,
    ast.Str,
    ast.Tuple
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
EXPRESSIONS = [ast.Compare, ast.BoolOp, ast.UnaryOp]
ATTR_OPS = ['op', 'ops']
ATTR_VALUES = ['values', 'operand', 'comparators', 'left']
ATTR_COLLECTIONS = ['elts', 'keys', 'values']


def arithmetic_eval(expr):
    """
    Safely eval an arithmetic expression (for a condition block).
    """
    node = ast.parse(expr, mode='eval').body
    _is_arithmetic(node)
    return bool(eval(expr))


def _is_arithmetic(node):
    """
    Recursive method that raises either a `TypeError` or a `SyntaxError` if
    the given expression is not a valid and safe arithmetic expression.
    """
    ntype = type(node)

    # Check types
    if ntype in TYPES:
        for coll in ATTR_COLLECTIONS:
            for item in getattr(node, coll, []):
                _is_arithmetic(item)
        return

    # Check expressions
    if ntype not in EXPRESSIONS:
        raise TypeError("Not allowed expression: {}".format(ntype))

    # Check operators
    for op_name in ATTR_OPS:
        ops = getattr(node, op_name, [])

        if isinstance(ops, list):
            ops_type = set([type(op) for op in ops])
            ops_invalid = ops_type.difference(OPERATORS)
        else:
            ops_type = type(ops)
            ops_invalid = ops_type if ops_type not in OPERATORS else {}
        if ops_invalid:
            raise TypeError("Not allowed operators: {}".format(ops_invalid))

    # Check values
    for val_name in ATTR_VALUES:
        vals = getattr(node, val_name, [])
        if isinstance(vals, list):
            for val in vals:
                _is_arithmetic(val)
        else:
            _is_arithmetic(vals)
