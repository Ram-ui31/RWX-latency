"""Exactly one existing literal class-data assignment may change."""
import ast
import copy


def literal_assignment(old, new):
    before, after = ast.parse(old), ast.parse(new)

    def assignments(tree):
        found = {}
        def walk(node, owners=()):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    walk(child, (*owners, child.name))
                elif isinstance(child, ast.Assign) and owners and len(child.targets) == 1 and isinstance(child.targets[0], ast.Name):
                    name = child.targets[0].id
                    if not (name.isupper() or name in {"arg_types", "required_args"}):
                        continue
                    try:
                        value = ast.literal_eval(child.value)
                    except (ValueError, TypeError, SyntaxError):
                        continue
                    found[".".join((*owners, name))] = child
                elif not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    walk(child, owners)
        walk(tree)
        return found

    a, b = assignments(before), assignments(after)
    changed = [k for k in a.keys() & b.keys() if ast.dump(a[k]) != ast.dump(b[k])]
    if len(changed) != 1:
        return None
    name = changed[0]
    a[name].value = ast.Constant(None)
    b[name].value = ast.Constant(None)
    return name if ast.dump(before) == ast.dump(after) else None
