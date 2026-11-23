"""Formulas are checked before they run: only a safe subset of Python expressions is allowed."""
import pytest

from jsonschema_formulas import (
    FormulaEvaluationError,
    FormulaEvaluator,
    InvalidFormulaError,
    formula_function,
)


def schema_with(formula, **props):
    return {
        "type": "object",
        "properties": {
            "values": {"type": "array", "items": {"type": "number"}},
            "result": {"x-formula": formula, **props},
        },
    }


# A working sandbox escape against plain eval() with {"__builtins__": {}}.
ESCAPE = (
    "[inner.__globals__['__import__']('os').system('echo pwned') "
    "for c in ().__class__.__bases__[0].__subclasses() "
    "for inner in [c.__init__] "
    "if inner.__class__.__name__ == 'function' and '__import__' in inner.__globals__][0]"
)

REFUSED = {
    "sandbox escape": ESCAPE,
    "attribute": "values.__class__",
    "harmless-looking attribute": "values.count(1)",
    "method on a string": "'{0}'.format(values)",
    "dunder name": "__import__('os')",
    "dunder builtins": "__builtins__",
    "f-string": "f'{values}'",
    "power": "10 ** 10 ** 10",
    "bit shift": "1 << 100000000",
    "walrus": "(x := 1)",
    "star argument": "max(*values)",
    "double-star argument": "max(**values)",
    "set comprehension": "{v for v in values}",
    "dict comprehension": "{v: v for v in values}",
    "calling a data value": "values(1)",
    "calling a call's result": "max(values)(1)",
    "calling a subscript": "values[0](1)",
    "calling a lambda": "(lambda: 1)()",
    "unknown function": "getattr(values, 'x')",
    "builtin that is not allowed": "open('x')",
    "lambda argument hiding a function": "list(map(lambda max: max, values))",
    "loop variable hiding a function": "[sum for sum in values]",
    "dunder lambda argument": "list(map(lambda __x: __x, values))",
    "bytes constant": "b'x'",
    "ellipsis": "...",
    "statement": "import os",
    "syntax error": "values +",
    "too long": "1" + " + 1" * 1000,
}


@pytest.mark.parametrize("formula", REFUSED.values(), ids=REFUSED.keys())
def test_refused_when_the_evaluator_is_made(formula):
    with pytest.raises(InvalidFormulaError):
        FormulaEvaluator(schema_with(formula))


@pytest.mark.parametrize("formula", REFUSED.values(), ids=REFUSED.keys())
def test_check_schema_refuses(formula):
    with pytest.raises(InvalidFormulaError):
        FormulaEvaluator.check_schema(schema_with(formula))


def test_invalid_formula_is_a_formula_evaluation_error():
    # Code that already catches FormulaEvaluationError keeps working.
    assert issubclass(InvalidFormulaError, FormulaEvaluationError)


def test_a_formula_must_be_a_string():
    with pytest.raises(InvalidFormulaError, match="must be a string"):
        FormulaEvaluator.check_schema(schema_with(["a + b"]))


def test_formulas_are_found_where_they_are_evaluated():
    schema = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {"bad": {"x-formula": "outer.x"}},
            },
            "sets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"worse": {"x-formula": "_this.__class__"}},
                },
            },
        },
    }
    with pytest.raises(InvalidFormulaError) as error:
        FormulaEvaluator.check_schema(schema)
    # Every bad formula is reported, with its place in the schema.
    assert "'outer.bad'" in str(error.value)
    assert "'sets[].worse'" in str(error.value)


def test_nothing_runs_when_a_formula_is_refused():
    calls = []

    class Evaluator(FormulaEvaluator):
        @formula_function
        def record(x):
            calls.append(x)
            return x

    schema = {
        "type": "object",
        "properties": {
            "first": {"x-formula": "record(1)"},
            "second": {"x-formula": "values.__class__"},
        },
    }
    with pytest.raises(InvalidFormulaError):
        Evaluator(schema).evaluate({"values": []})
    assert calls == []


def test_a_formula_added_after_the_evaluator_was_made_is_checked_too():
    schema = schema_with("sum(values)")
    evaluator = FormulaEvaluator(schema)
    schema["properties"]["result"]["x-formula"] = ESCAPE
    with pytest.raises(InvalidFormulaError):
        evaluator.evaluate({"values": [1]})


def test_compile_formula():
    assert eval(FormulaEvaluator.compile_formula("max([1, 2])"), {"__builtins__": {}},
                FormulaEvaluator.allowed_functions()) == 2
    with pytest.raises(InvalidFormulaError):
        FormulaEvaluator.compile_formula("values.__class__")


def test_custom_functions_may_be_called():
    class Evaluator(FormulaEvaluator):
        @formula_function
        def double(x):
            return x * 2

    assert Evaluator(schema_with("double(sum(values))")).evaluate({"values": [1, 2]})["result"] == 6
    # ... but only by the evaluator that defines them.
    with pytest.raises(InvalidFormulaError):
        FormulaEvaluator(schema_with("double(1)"))


ALLOWED = {
    "arithmetic": ("(values[0] + values[1] - 1) * 2 / 4 // 1 % 5", 1.0),
    "negation": ("-values[0] + +1", 0),
    "slice": ("sum(sorted(values)[-2:])", 7),
    "keyword argument": ("sorted(values, reverse=True)[0]", 4),
    "lambda": ("sorted([{'v': v} for v in values], key=lambda r: r['v'])[0]['v']", 1),
    "map": ("list(map(lambda x: x * 2, values))", [2, 4, 6, 8]),
    "list comprehension": ("[v for v in values if v > 2]", [3, 4]),
    "generator": ("sum(v for v in values)", 10),
    "nested comprehension": ("[a * b for a in values for b in values if a == b]", [1, 4, 9, 16]),
    "comparison": ("values[0] < values[1] <= 2 != 3", True),
    "membership": ("3 in values and 5 not in values", True),
    "boolean": ("not (values[0] > 1 or None is not None)", True),
    "conditional": ("'big' if max(values) > 3 else 'small'", "big"),
    "literals": ("[len(values), (1, 2), {'a': 1}, None, True, 1.5]",
                 [4, (1, 2), {"a": 1}, None, True, 1.5]),
    "string key with underscores": ("{'_2_best': 1}['_2_best']", 1),
    "_this": ("_this['values'][0]", 1),
}


@pytest.mark.parametrize("formula, expected", ALLOWED.values(), ids=ALLOWED.keys())
def test_allowed(formula, expected):
    assert FormulaEvaluator(schema_with(formula)).evaluate({"values": [1, 2, 3, 4]})["result"] == expected


def test_runtime_errors_are_still_formula_evaluation_errors():
    with pytest.raises(FormulaEvaluationError) as error:
        FormulaEvaluator(schema_with("values[0] / 0")).evaluate({"values": [1]})
    assert not isinstance(error.value, InvalidFormulaError)
