from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class FlatResultDataValidator:
    def __call__(self, value) -> None:
        if value is None:
            return
        if not isinstance(value, dict):
            raise ValidationError("Table data must be an object.")

        columns = value.get("columns")
        cells = value.get("flattened_rows")
        width = value.get("column_count")

        if not isinstance(columns, list) or not all(isinstance(column, str) for column in columns):
            raise ValidationError("Table columns must be a list of strings.")
        if not isinstance(cells, list) or not all(isinstance(cell, str) for cell in cells):
            raise ValidationError("Table cells must be a list of strings.")
        if type(width) is not int or width < 0 or len(columns) != width:
            raise ValidationError("Column count must be a non-negative integer matching the column names.")
        if (width == 0 and cells) or (width > 0 and len(cells) % width != 0):
            raise ValidationError("Table cells must form complete rows.")
