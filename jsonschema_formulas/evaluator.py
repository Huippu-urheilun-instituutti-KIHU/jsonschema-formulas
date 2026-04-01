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
        """Initialize the FormulaEvaluator with a JSON schema.
        Args:
            schema (dict): The JSON schema defining the structure and formulas.
        """
        self.schema = schema
        self.data = {}
        self.__allowed_functions = self.base_allowed_functions.copy()
        self.__allowed_functions.update(self.__get_formula_functions())

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
        self.__process_properties(self.schema.get("properties", {}), self.data, self.data)
        self.__drop_temporary_fields(self.schema.get("properties", {}), self.data)
        return self.data

    @formula_function
    def avg_of_n_max(lst: list, n: int) -> float:
        """Calculate the average of the top n maximum values in a list.

        Args:
            lst (list): The list of numbers.
            n (int): The number of top elements to consider.

        Returns:
            float: The average of the top n maximum values.
        """

        top_n = sorted(lst)[-n:]
        return sum(top_n) / max(1, len(top_n))

    @formula_function
    def avg_of_n_min(lst: list, n: int) -> float:
        """Calculate the average of the bottom n minimum values in a list.

        Args:
            lst (list): The list of numbers.
            n (int): The number of bottom elements to consider.

        Returns:
            float: The average of the bottom n minimum values.
        """

        bottom_n = sorted(lst)[:n]
        return sum(bottom_n) / max(1, len(bottom_n))

    @formula_function
    def average_of_field_in_objects(objects: list, field: str) -> float:
        """Calculate the average of a specific field in a list of objects.
        Args:
            objects (list): The list of objects (dictionaries).
            field (str): The field name to average.
        Returns:
            float: The average value of the specified field.
        """

        values = [obj.get(field, 0) for obj in objects if isinstance(obj, dict)]
        return sum(values) / max(1, len(values))

    @formula_function
    def max_object_by_field(objects: list, field: str) -> dict:
        """Find the object with the maximum value for a specific field.
        Args:
            objects (list): The list of objects (dictionaries).
            field (str): The field name to compare.
        Returns:
            dict: The object with the maximum value for the specified field.
        """

        if not objects:
            return {}
        return max(objects, key=lambda obj: obj.get(field, float('-inf')))

    @formula_function
    def min_object_by_field(objects: list, field: str) -> dict:
        """Find the object with the minimum value for a specific field.
        Args:
            objects (list): The list of objects (dictionaries).
            field (str): The field name to compare.
        Returns:
            dict: The object with the minimum value for the specified field.
        """

        if not objects:
            return {}
        return min(objects, key=lambda obj: obj.get(field, float('inf')))

    def __process_properties(self, properties: dict, data_node: dict, _this: dict = None):
        """Process the properties of the schema against the data node.

        Args:
            properties (dict): The schema properties.
            data_node (dict): The data node to process.
            _this (dict): The current object context for formulas.

        Raises:
            TypeError: If data_node is not a dict.
            FormulaEvaluationError: If there is an error during formula evaluation.
        """

        if _this is None:
            _this = data_node

        for field, props in properties.items():
            if "x-formula" in props:
                formula = props["x-formula"]
                # define allowed names every time to capture current data state
                allowed_names = {k: v for k, v in self.data.items()}
                allowed_names["_this"] = _this
                allowed_names.update(self.__allowed_functions)
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
                self.__process_properties(props["properties"], data_node[field], data_node[field])

            # Recurse into array item properties
            if props.get("type") == "array" and isinstance(props.get("items"), dict) and "properties" in props["items"]:
                for item in data_node.get(field, []):
                    if isinstance(item, dict):
                        self.__process_properties(props["items"]["properties"], item, item)

    def __drop_temporary_fields(self, properties: dict, data_node: dict):
        """Drop temporary fields marked with 'x-temporary' from the data node.
        Args:
            properties (dict): The schema properties.
            data_node (dict): The data node to process.
        """

        for field, props in properties.items():
            # Drop temporary fields
            if props.get("x-temporary") and field in data_node:
                del data_node[field]

            # Recurse into nested object properties
            if props.get("type") == "object" and "properties" in props:
                if field in data_node and isinstance(data_node[field], dict):
                    self.__drop_temporary_fields(props["properties"], data_node[field])

            # Recurse into array item properties
            if props.get("type") == "array" and isinstance(props.get("items"), dict) and "properties" in props["items"]:
                for item in data_node.get(field, []):
                    if isinstance(item, dict):
                        self.__drop_temporary_fields(props["items"]["properties"], item)

    @classmethod
    def __get_formula_functions(cls):
        """
        Collect all formula_function decorated static methods.

        Returns:
            dict: A dictionary of function names to function objects.
        """
        functions = {}

        for klass in reversed(cls.__mro__):
            for name, attr in klass.__dict__.items():
                if isinstance(attr, staticmethod):
                    fn = attr.__func__
                    if getattr(fn, "_is_formula_function", False):
                        functions[name] = fn

        return functions