import ast


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
