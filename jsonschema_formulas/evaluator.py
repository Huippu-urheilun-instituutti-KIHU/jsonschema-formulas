import ast
import copy
from types import CodeType
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    formula_function = staticmethod
else:
    def formula_function(fn: Callable) -> staticmethod:
        fn._is_formula_function = True  # type: ignore[attr-defined]
        return staticmethod(fn)

class FormulaEvaluationError(Exception):
    pass


class InvalidFormulaError(FormulaEvaluationError):
    """A formula is not valid formula syntax, or uses something formulas may not.

    Raised when a FormulaEvaluator is created (or by check_schema), before
    any formula runs.
    """


# Formulas are Python expressions, but only this subset of them. Everything
# else - above all attribute access (`x.y`), which every known way out of an
# eval() sandbox needs - is refused before a formula is ever run.
ALLOWED_NODES = (
    # structure
    ast.Expression, ast.Load, ast.Store,
    ast.Name, ast.Constant, ast.List, ast.Tuple, ast.Dict,
    ast.Subscript, ast.Slice,
    ast.Call, ast.keyword,
    ast.Lambda, ast.arguments, ast.arg,
    ast.ListComp, ast.GeneratorExp, ast.comprehension,
    ast.IfExp,
    # operators (no `**` or bit shifts: they build huge numbers from a short formula)
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
    ast.UnaryOp, ast.UAdd, ast.USub, ast.Not,
    ast.BoolOp, ast.And, ast.Or,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
)

ALLOWED_CONSTANTS = (int, float, str, bool, type(None))


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

    # A formula is one expression; real ones are a couple of hundred
    # characters at most. The limit keeps the parser away from pathological input.
    max_formula_length = 2000

    def __init__(self, schema: dict):
        """Initialize the FormulaEvaluator with a JSON schema.

        Every formula of the schema is checked and compiled here, so a schema
        with a formula that is not allowed fails before anything is evaluated.

        Args:
            schema (dict): The JSON schema defining the structure and formulas.

        Raises:
            InvalidFormulaError: If a formula in the schema is not allowed.
        """
        self.schema = schema
        self.data = {}
        self.__allowed_functions = self.allowed_functions()
        self.__compiled = self.__compile_schema(schema)

    @classmethod
    def allowed_functions(cls) -> dict:
        """The functions formulas may call: the base ones and every @formula_function."""
        functions = cls.base_allowed_functions.copy()
        functions.update(cls.__get_formula_functions())
        return functions

    @classmethod
    def check_schema(cls, schema: dict) -> None:
        """Check that every formula in the schema is allowed, without evaluating anything.

        Use this to refuse a schema before it is stored.

        Raises:
            InvalidFormulaError: Listing every formula that is not allowed.
        """
        cls.__compile_schema(schema)

    @classmethod
    def compile_formula(cls, formula: str) -> CodeType:
        """Check one formula and compile it.

        Raises:
            InvalidFormulaError: If the formula is not allowed.
        """
        return cls.__compile(formula, frozenset(cls.allowed_functions()))

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
                code = self.__compiled.get(formula)
                if code is None:  # the schema was changed after the evaluator was made
                    code = self.__compiled[formula] = self.compile_formula(formula)
                # define allowed names every time to capture current data state
                allowed_names = {k: v for k, v in self.data.items()}
                allowed_names["_this"] = _this
                allowed_names.update(self.__allowed_functions)
                try:
                    # Only a checked, compiled formula ever reaches eval().
                    result = eval(code, {"__builtins__": {}}, allowed_names)
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

    @classmethod
    def __compile_schema(cls, schema: dict) -> dict:
        """Check and compile every formula the evaluator would run, keyed by the formula.

        Walks the schema the same way evaluation does, and reports every
        formula that is not allowed at once.
        """
        function_names = frozenset(cls.allowed_functions())
        compiled: dict = {}
        errors: list[str] = []

        def walk(properties, path):
            if not isinstance(properties, dict):
                return
            for field, props in properties.items():
                if not isinstance(props, dict):
                    continue
                field_path = f"{path}.{field}" if path else str(field)
                if "x-formula" in props:
                    formula = props["x-formula"]
                    if not isinstance(formula, str):
                        errors.append(f"'{field_path}': a formula must be a string")
                    elif formula not in compiled:
                        try:
                            compiled[formula] = cls.__compile(formula, function_names)
                        except InvalidFormulaError as e:
                            errors.append(f"'{field_path}': {e}")
                if props.get("type") == "object":
                    walk(props.get("properties"), field_path)
                if props.get("type") == "array" and isinstance(props.get("items"), dict):
                    walk(props["items"].get("properties"), f"{field_path}[]")

        walk(schema.get("properties") if isinstance(schema, dict) else None, "")
        if errors:
            raise InvalidFormulaError("; ".join(errors))
        return compiled

    @classmethod
    def __compile(cls, formula, function_names: frozenset) -> CodeType:
        if not isinstance(formula, str):
            raise InvalidFormulaError("a formula must be a string")
        if len(formula) > cls.max_formula_length:
            raise InvalidFormulaError(f"formula is longer than {cls.max_formula_length} characters")
        try:
            tree = ast.parse(formula, mode="eval")
        except (SyntaxError, ValueError, RecursionError, MemoryError) as e:
            raise InvalidFormulaError(f"not a valid formula: {e}") from None

        nodes = list(ast.walk(tree))
        # Syntax that is not allowed at all first: it is the clearer message.
        for node in sorted(nodes, key=lambda n: isinstance(n, ALLOWED_NODES)):
            problem = cls.__node_problem(node, function_names)
            if problem:
                raise InvalidFormulaError(problem)

        return compile(tree, "<x-formula>", "eval")

    @staticmethod
    def __node_problem(node: ast.AST, function_names: frozenset) -> str | None:
        """Why a formula may not contain this node, or None if it may."""
        if not isinstance(node, ALLOWED_NODES):
            if isinstance(node, ast.Attribute):
                return f"attribute access ('.{node.attr}') is not allowed in formulas"
            return f"'{type(node).__name__}' is not allowed in formulas"

        if isinstance(node, ast.Name):
            if node.id.startswith("__"):
                return f"name '{node.id}' is not allowed in formulas"
            # A lambda argument or loop variable may not hide a function.
            if isinstance(node.ctx, ast.Store) and node.id in function_names:
                return f"'{node.id}' is a function and cannot be assigned to"
        elif isinstance(node, ast.arg):
            if node.arg.startswith("__"):
                return f"name '{node.arg}' is not allowed in formulas"
            if node.arg in function_names:
                return f"'{node.arg}' is a function and cannot be a lambda argument"
        elif isinstance(node, ast.Call):
            # Only the allowed functions can be called - never a value from the data.
            if not isinstance(node.func, ast.Name) or node.func.id not in function_names:
                return f"'{ast.unparse(node.func)}' is not a function formulas may call"
        elif isinstance(node, ast.keyword):
            if node.arg is None:
                return "'**' arguments are not allowed in formulas"
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, ALLOWED_CONSTANTS):
                return f"constant {node.value!r} is not allowed in formulas"
        elif isinstance(node, ast.comprehension):
            if node.is_async:
                return "async comprehensions are not allowed in formulas"
        return None