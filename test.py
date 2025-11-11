from json_formula_evaluator import FormulaEvaluator, FormulaEvaluationError, formula_function


class CustomFormulaEvaluator(FormulaEvaluator):
    @formula_function
    def double(x):
        return x * 2

    @formula_function
    def to_string(x):
        return str(x)

def main():
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "type": "number"
            },
            "doubled_value": {
                "type": "number",
                "x-formula": "double(value)"
            },
            "string_value": {
                "type": "string",
                "x-formula": "to_string(doubled_value)"
            },
            "test_object": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                }
            },
        }
    }

    evaluator = CustomFormulaEvaluator(schema)
    data = {
        "value": 10,
        "irrelevant_field": 42,
        "test_object": {
            "a": 1,
            "b": 2
        }
    }

    result = evaluator.evaluate(data)
    print(result)

if __name__ == "__main__":
    main()