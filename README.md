# JSON Schema formulas

A small library to evaluate calculated fields defined in a JSON Schema. JSON Formula Evaluator lets you declare formulas (using the `x-formula` keyword) inside a schema and computes derived values from other properties in the input data, while keeping results type-checked against the schema.

Key features

- Evaluate arithmetic and simple expressions that reference other properties.
- Compute derived fields defined in the schema (e.g., sums, ratios, concatenations).
- Integrates with JSON Schema types to ensure computed values match the declared type.
- Designed for safe, deterministic evaluation (no arbitrary code execution).

When to use

- Populate derived fields server-side before persisting or returning data.
- Implement spreadsheet-like calculations for JSON documents.
- Keep transformation logic close to the schema for maintainability.

Requirements

- Python 3.8+
- (See Install and Usage sections below for quick start and examples.)

## Install

```bash
pip install git+ssh://git@gitlab.com/k2315/jsonschema-formulas.git
```

## Usage

```python
from jsonschema_formulas import FormulaEvaluator

schema = {
    "type": "object",
    "properties": {
        "a": {"type": "number"},
        "b": {"type": "number"},
        "sum_ab": {
            "type": "number",
            "x-formula": "a + b"
        }
    }
}

data = {
    "a": 5,
    "b": 10
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'a': 5, 'b': 10, 'sum_ab': 15}

```

## Temporary fields

Temporary fields are helper properties in the schema that hold intermediate computed values during formula evaluation. Mark a property with "x-temporary": True to indicate it should be:

- Evaluated according to its "x-formula".
- Available for other formulas during the same evaluation run.
- Omitted from the final returned/serialized data (not persisted as part of the visible output).

Use temporary fields to break complex calculations into simpler steps or to cache intermediate results without altering the external data shape.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {"type": "number"}
        },
        "values_sum": {
            "type": "number",
            "x-formula": "sum(values)",
            "x-temporary": True
        },
        "values_count": {
            "type": "number",
            "x-formula": "len(values)",
            "x-temporary": True
        },
        "values_average": {
            "type": "number",
            "x-formula": "values_sum / values_count"
        },
    }
}
data = {
    "values": [1, 2, 3, 4, 5]
}
evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'a': 3, 'b': 4, 'sum_ab': 7}

```

## Nested fields

When defining formulas in nested computed fields, you must always use absolute paths when referencing fields.
This means that formulas should reference fields starting from the root (e.g., outer['x'] instead of just x).
Using absolute paths ensures that the evaluation works correctly regardless of where the field is located in the schema.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "outer": {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
                "product_xy": {
                    "type": "number",
                    "x-formula": "outer['x'] * outer['y']"
                }
            }
        }
    }
}
data = {
    "outer": {
        "x": 4,
        "y": 3
    }
}
evaluator = FormulaEvaluator(schema)
data = evaluator.evaluate(data)
# {
#     'outer': {
#         'x': 4,
#         'y': 3,
#         'product_xy': 12
#     }
# }
```

## Available functions

### sum _(Python built-in)_

Calculates the total sum of all numbers in a list.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {"type": "number"}
        },
        "values_sum": {
            "type": "number",
            "x-formula": "sum(values)"
        },
    }
}

data = {
    "values": [1, 2, 3, 4, 5]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'values': [1, 2, 3, 4, 5], 'values_sum': 15}

```

### min _(Python built-in)_

Returns the smallest value in a list.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {"type": "number"}
        },
        "values_min": {
            "type": "number",
            "x-formula": "min(values)"
        },
    }
}

data = {
    "values": [1, 2, 3, 4, 5]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'values': [1, 2, 3, 4, 5], 'values_min': 1}

```

### max _(Python built-in)_

Returns the largest value in a list.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {"type": "number"}
        },
        "values_max": {
            "type": "number",
            "x-formula": "max(values)"
        },
    }
}

data = {
    "values": [1, 2, 3, 4, 5]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'values': [1, 2, 3, 4, 5], 'values_max': 5}

```

### len _(Python built-in)_

Returns the number of elements in a list.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {"type": "number"}
        },
        "values_len": {
            "type": "number",
            "x-formula": "len(values)"
        },
    }
}

data = {
    "values": [1, 2, 3, 4, 5]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'values': [1, 2, 3, 4, 5], 'values_len': 5}
```

### map _(Python built-in)_

Applies a given function to each element in a list.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {"type": "number"}
        },
        "double_values": {
            "type": "array",
            "items": {"type": "number"},
            "x-formula": "list(map(lambda x: x * 2, values))"
        },
    }
}

data = {
    "values": [1, 2, 3, 4, 5]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'values': [1, 2, 3, 4, 5], 'double_values': [2, 4, 6, 8, 10]}

```

### sorted _(Python built-in)_

Returns a new list with all elements sorted in ascending order.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {"type": "number"}
        },
        "sorted_values": {
            "type": "array",
            "items": {"type": "number"},
            "x-formula": "sorted(values)"
        },
    }
}

data = {
    "values": [3, 4, 1, 10, 5]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'values': [3, 4, 1, 10, 5], 'sorted_values': [1, 3, 4, 5, 10]}

```

### avg_of_n_max

Calculates the average of the n highest values in a list.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {"type": "number"}
        },
        "best_2_avg": {
            "type": "array",
            "items": {"type": "number"},
            "x-formula": "avg_of_n_max(values, 2)"
        },
    }
}

data = {
    "values": [3, 4, 1, 10, 5]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'values': [3, 4, 1, 10, 5], 'best_2_avg': 7.5}

```

### avg_of_n_min

Calculates the average of the n lowest values in a list.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {"type": "number"}
        },
        "best_2_avg": {
            "type": "array",
            "items": {"type": "number"},
            "x-formula": "avg_of_n_min(values, 2)"
        },
    }
}

data = {
    "values": [3, 4, 1, 10, 5]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {'values': [3, 4, 1, 10, 5], 'best_2_avg': 2.0}

```

### average_of_field_in_objects

Calculates the average of a specific field across a list of objects.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "number"}
                }
            }
        },
        "average_value": {
            "type": "number",
            "x-formula": "average_of_field_in_objects(items, 'value')"
        }
    }
}

data = {
    "items": [
        {"value": 10},
        {"value": 20},
        {"value": 30}
    ]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {
#     'items': [
#         {'value': 10},
#         {'value': 20},
#         {'value': 30}
#     ],
#     'average_value': 20.0
# }

```

### max_object_by_field

Returns the object with the highest value in the specified field.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "score": {"type": "number"}
                }
            }
        },
        "lowest_scorer": {
            "type": "object",
            "x-formula": "min_object_by_field(items, 'score')"
        }
    }
}

data = {
    "items": [
        {"name": "Bob", "score": 92},
        {"name": "Alice", "score": 85},
        {"name": "Charlie", "score": 88}
    ]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)

# {
#     'items': [
#         {'name': 'Bob', 'score': 92},
#         {'name': 'Alice', 'score': 85},
#         {'name': 'Charlie', 'score': 88}
#     ],
#     'lowest_scorer': {'name': 'Alice', 'score': 85}
# }

```

### min_object_by_field

Returns the object with the lowest value in the specified field.

```python
from jsonschema_formulas import FormulaEvaluator
schema = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "score": {"type": "number"}
                }
            }
        },
        "highest_scorer": {
            "type": "object",
            "x-formula": "max_object_by_field(items, 'score')"
        }
    }
}

data = {
    "items": [
        {"name": "Bob", "score": 92},
        {"name": "Alice", "score": 85},
        {"name": "Charlie", "score": 88}
    ]
}

evaluator = FormulaEvaluator(schema)
evaluator.evaluate(data)
# {
#     'items': [
#         {'name': 'Bob', 'score': 92},
#         {'name': 'Alice', 'score': 85},
#         {'name': 'Charlie', 'score': 88}
#     ],
#     'highest_scorer': {'name': 'Bob', 'score': 92}
# }

```

## Extend FormulaEvaluator

You can extend the FormulaEvaluator class to add your own custom formula functions.
To do this, subclass FormulaEvaluator and define new functions decorated with @formula_function.
These functions will then be available for use in your schema formulas, just like any built-in functions.

**Note:** The @formula_function decorator automatically defines the function as a static method,
meaning it does not receive a self parameter. You should therefore define your custom functions
without self as the first argument.

```python
from jsonschema_formulas import FormulaEvaluator, formula_function

class CustomFormulaEvaluator(FormulaEvaluator):
    @formula_function
    def custom_function(x):
        return x * 2


schema = {
    "type": "object",
    "properties": {
        "a": {"type": "number"},
        "b": {"type": "number"},
        "custom_ab": {
            "type": "number",
            "x-formula": "custom_function(a) + custom_function(b)"
        }
    }
}

data = {
    "a": 5,
    "b": 10
}

evaluator = CustomFormulaEvaluator(schema)
evaluator.evaluate(data)
# {'a': 5, 'b': 10, 'custom_ab': 30}
```
