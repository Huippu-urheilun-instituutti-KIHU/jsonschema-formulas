from json_formula_evaluator import FormulaEvaluator, FormulaEvaluationError, formula_function

def test_basic_evaluation():
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
    data = evaluator.evaluate(data)
    assert data["sum_ab"] == 15

def test_average_of_field_in_objects():
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
    data = evaluator.evaluate(data)
    assert data["average_value"] == 20.0

def test_avg_of_n_max():
    schema = {
        "type": "object",
        "properties": {
            "numbers": {
                "type": "array",
                "items": {"type": "number"}
            },
            "avg_top_2": {
                "type": "number",
                "x-formula": "avg_of_n_max(numbers, 2)"
            }
        }
    }
    data = {
        "numbers": [1, 3, 5, 7, 9]
    }
    evaluator = FormulaEvaluator(schema)
    data = evaluator.evaluate(data)
    assert data["avg_top_2"] == 8.0  # (9 + 7) / 2

def test_avg_of_n_min():
    schema = {
        "type": "object",
        "properties": {
            "numbers": {
                "type": "array",
                "items": {"type": "number"}
            },
            "avg_bottom_3": {
                "type": "number",
                "x-formula": "avg_of_n_min(numbers, 3)"
            }
        }
    }
    data = {
        "numbers": [10, 20, 30, 40, 50]
    }
    evaluator = FormulaEvaluator(schema)
    data = evaluator.evaluate(data)
    assert data["avg_bottom_3"] == 20.0  # (10 + 20 + 30) / 3

def test_max_object_by_field():
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
            "top_scorer": {
                "type": "object",
                "x-formula": "max_object_by_field(items, 'score')"
            }
        }
    }
    data = {
        "items": [
            {"name": "Alice", "score": 85},
            {"name": "Bob", "score": 92},
            {"name": "Charlie", "score": 88}
        ]
    }
    evaluator = FormulaEvaluator(schema)
    data = evaluator.evaluate(data)
    assert data["top_scorer"] == {"name": "Bob", "score": 92}

def test_min_object_by_field():
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
    data = evaluator.evaluate(data)
    assert data["lowest_scorer"] == {"name": "Alice", "score": 85}

def test_x_temporary_field_removal():
    schema = {
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"},
            "temp_sum": {
                "type": "number",
                "x-formula": "a + b",
                "x-temporary": True
            },
            "sum_ab": {
                "type": "number",
                "x-formula": "temp_sum"
            }
        }
    }
    data = {
        "a": 3,
        "b": 4
    }
    evaluator = FormulaEvaluator(schema)
    data = evaluator.evaluate(data)
    assert "temp_sum" not in data
    assert data["sum_ab"] == 7

def test_error_handling():
    schema = {
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"},
            "invalid_formula": {
                "type": "number",
                "x-formula": "a / b"  # Potential division by zero
            }
        }
    }
    data = {
        "a": 10,
        "b": 0
    }
    evaluator = FormulaEvaluator(schema)
    try:
        evaluator.evaluate(data)
        assert False, "Expected FormulaEvaluationError due to division by zero"
    except FormulaEvaluationError as e:
        assert "division by zero" in str(e)

def test_custom_function_extension():
    from json_formula_evaluator import formula_function

    class CustomFormulaEvaluator(FormulaEvaluator):

        @formula_function
        def double(x):
            return x * 2

    schema = {
        "type": "object",
        "properties": {
            "value": {"type": "number"},
            "doubled_value": {
                "type": "number",
                "x-formula": "double(value)"
            }
        }
    }
    data = {
        "value": 7
    }
    evaluator = CustomFormulaEvaluator(schema)
    data = evaluator.evaluate(data)
    assert data["doubled_value"] == 14