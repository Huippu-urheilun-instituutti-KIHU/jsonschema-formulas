class FormulaEvaluationError(Exception):
    pass

class FormulaEvaluator:
    def __init__(self, schema):
        self.schema = schema
        self.data = {}

    def evaluate(self, data):
        self.data = data
        self.__process_properties(self.schema.get("properties", {}), data)
        self.__drop_temporary_fields(self.schema.get("properties", {}), data)

    @staticmethod
    def avg_of_n_max(lst: list, n: int|float) -> float:
        top_n = sorted(lst)[-n:]
        return sum(top_n) / max(1, len(top_n))

    @staticmethod
    def avg_of_n_min(lst: list, n: int|float) -> float:
        bottom_n = sorted(lst)[:n]
        return sum(bottom_n) / max(1, len(bottom_n))

    @staticmethod
    def average_of_field_in_objects(objects: list, field: str) -> float:
        values = [obj.get(field, 0) for obj in objects if isinstance(obj, dict)]
        return sum(values) / max(1, len(values))

    @staticmethod
    def max_object_by_field(objects: list, field: str) -> dict:
        if not objects:
            return {}
        return max(objects, key=lambda obj: obj.get(field, float('-inf')))

    @staticmethod
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
                allowed_names.update({
                    "sum": sum, "min": min, "max": max, "len": len, "map": map, "sorted": sorted, "list": list,
                    "avg_of_n_max": self.avg_of_n_max, "avg_of_n_min": self.avg_of_n_min,
                    "average_of_field_in_objects": self.average_of_field_in_objects, "max_object_by_field": self.max_object_by_field,
                    "min_object_by_field": self.min_object_by_field
                })
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

    def __drop_temporary_fields(self, properties: dict, data_node: dict = None):
        if data_node is None:
            data_node = data
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

