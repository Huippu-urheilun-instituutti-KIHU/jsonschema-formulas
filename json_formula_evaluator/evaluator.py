import copy
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    formula_function = staticmethod
else:
    def formula_function(fn: Callable) -> staticmethod:
        fn._is_formula_function = True  # type: ignore[attr-defined]
        return staticmethod(fn)

class FormulaEvaluationError(Exception):
    pass

class FormulaEvaluator:
    base_allowed_functions = {
        "sum": sum,
        "min": min,
        "max": max,
        "len": len,
        "map": map,
        "sorted": sorted,
        "list": list,
    }

    def __init__(self, schema: dict):
        self.schema = schema
        self.data = {}

    def evaluate(self, data: dict) -> dict:
        """Evaluate the given data against the schema.

        Args:
            data (dict): The data to evaluate.

        Returns:
            dict: The evaluated data.

        Raises:
            FormulaEvaluationError: If there is an error during formula evaluation.
        """

        self.data = copy.deepcopy(data)
        self.__process_properties(self.schema.get("properties", {}), self.data)
        self.__drop_temporary_fields(self.schema.get("properties", {}), self.data)
        return self.data

    @formula_function
    def avg_of_n_max(lst: list, n: int|float) -> float:
        top_n = sorted(lst)[-n:]
        return sum(top_n) / max(1, len(top_n))

    @formula_function
    def avg_of_n_min(lst: list, n: int|float) -> float:
        bottom_n = sorted(lst)[:n]
        return sum(bottom_n) / max(1, len(bottom_n))

    @formula_function
    def average_of_field_in_objects(objects: list, field: str) -> float:
        values = [obj.get(field, 0) for obj in objects if isinstance(obj, dict)]
        return sum(values) / max(1, len(values))

    @formula_function
    def max_object_by_field(objects: list, field: str) -> dict:
        if not objects:
            return {}
        return max(objects, key=lambda obj: obj.get(field, float('-inf')))

    @formula_function
    def min_object_by_field(objects: list, field: str) -> dict:
        if not objects:
            return {}
        return min(objects, key=lambda obj: obj.get(field, float('inf')))

    def __process_properties(self, properties: dict, data_node: dict):
        for field, props in properties.items():
            # Evaluate formula if present
            if "x-formula" in props:
                formula = props["x-formula"]
                # Safe evaluation context
                allowed_names = {k: v for k, v in self.data.items()}
                allowed_names.update(self.__allowed_functions())
                try:
                    result = eval(formula, {"__builtins__": {}}, allowed_names)
                    # Ensure data_node is a dict and set the value
                    if not isinstance(data_node, dict):
                        raise TypeError("data_node is not a dict")
                    data_node[field] = result
                except Exception as e:
                    raise FormulaEvaluationError(f"Error evaluating formula for field '{field}': {e}")

            # Recurse into nested object properties
            if props.get("type") == "object" and "properties" in props:
                if field not in data_node or not isinstance(data_node[field], dict):
                    data_node[field] = {}
                self.__process_properties(props["properties"], data_node[field])

            # If array of objects, recurse into each element
            elif props.get("type") == "array" and "items" in props:
                items = props["items"]
                if field in data_node and isinstance(data_node[field], list):
                    if items.get("type") == "object" and "properties" in items:
                        for elem in data_node[field]:
                            if isinstance(elem, dict):
                                self.__process_properties(items["properties"], elem)

    def __drop_temporary_fields(self, properties: dict, data_node: dict):
        for field, props in properties.items():
            # Drop temporary fields
            if props.get("x-temporary") and field in data_node:
                del data_node[field]

            # Recurse into nested object properties
            if props.get("type") == "object" and "properties" in props:
                if field in data_node and isinstance(data_node[field], dict):
                    self.__drop_temporary_fields(props["properties"], data_node[field])

            # If array of objects, recurse into each element
            elif props.get("type") == "array" and "items" in props:
                items = props["items"]
                if field in data_node and isinstance(data_node[field], list):
                    if items.get("type") == "object" and "properties" in items:
                        for elem in data_node[field]:
                            if isinstance(elem, dict):
                                self.__drop_temporary_fields(items["properties"], elem)

    def __allowed_functions(self):
        """Return base + all @formula_function decorated static methods."""
        functions = self.base_allowed_functions.copy()

        for name, attr in self.__class__.__dict__.items():
            if isinstance(attr, staticmethod):
                fn = attr.__func__
                if getattr(fn, "_is_formula_function", False):
                    functions[name] = fn

        return functions