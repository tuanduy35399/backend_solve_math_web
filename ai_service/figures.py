"""Interactive 2D figures the tutor can embed in a chat message.

The model describes a figure declaratively: slider parameters, point coordinates as
arithmetic expressions of those parameters, and shapes drawn between points. The
frontend evaluates the same expression subset with its own parser (no eval), so the
grammar here must stay in sync with src/lib/figure-expr.js.
"""
import ast
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PARAM_NAME = r'^[a-zA-Z][a-zA-Z0-9_]{0,11}$'
POINT_NAME = r"^[A-Za-z][A-Za-z0-9']{0,3}$"
EXPR_CHARS = re.compile(r'^[0-9A-Za-z_+\-*/^().,\s]+$')
# Trigonometry works in degrees, matching school geometry.
FUNCTIONS = {
    'sqrt': math.sqrt, 'abs': abs, 'min': min, 'max': max,
    'sin': lambda d: math.sin(math.radians(d)), 'cos': lambda d: math.cos(math.radians(d)),
    'tan': lambda d: math.tan(math.radians(d)),
    'asin': lambda x: math.degrees(math.asin(x)), 'acos': lambda x: math.degrees(math.acos(x)),
    'atan': lambda x: math.degrees(math.atan(x)),
}
CONSTANTS = {'pi': math.pi}
LIMIT = 1e4


def evaluate(expr, values):
    """Evaluate the shared expression subset; raise ValueError for anything else."""
    if not isinstance(expr, str) or not 0 < len(expr) <= 200 or not EXPR_CHARS.match(expr) or '**' in expr:
        raise ValueError('Biểu thức không hợp lệ.')
    tree = ast.parse(expr.replace('^', '**'), mode='eval')

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in values: return values[node.id]
            if node.id in CONSTANTS: return CONSTANTS[node.id]
            raise ValueError(f'Tên chưa khai báo: {node.id}')
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = walk(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10: raise ValueError('Số mũ quá lớn.')
            return {ast.Add: left + right, ast.Sub: left - right, ast.Mult: left * right,
                    ast.Div: left / right if right else math.nan,
                    ast.Pow: left ** right if left >= 0 or float(right).is_integer() else math.nan}[type(node.op)]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS
                and not node.keywords and 1 <= len(node.args) <= (2 if node.func.id in ('min', 'max') else 1)):
            try: return float(FUNCTIONS[node.func.id](*[walk(a) for a in node.args]))
            except ValueError: return math.nan
        raise ValueError('Biểu thức chứa thành phần không được hỗ trợ.')

    return walk(tree)


class FigureParam(BaseModel):
    model_config = ConfigDict(extra='ignore')
    name: str = Field(pattern=PARAM_NAME)
    label: str = Field(min_length=1, max_length=40)
    min: float = Field(ge=-LIMIT, le=LIMIT, allow_inf_nan=False)
    max: float = Field(ge=-LIMIT, le=LIMIT, allow_inf_nan=False)
    step: float = Field(gt=0, le=LIMIT, allow_inf_nan=False)
    value: float = Field(ge=-LIMIT, le=LIMIT, allow_inf_nan=False)
    unit: str = Field(default='', max_length=10)

    @model_validator(mode='after')
    def check_range(self):
        if not self.min < self.max or not self.min <= self.value <= self.max or (self.max - self.min) / self.step > 10000:
            raise ValueError('Khoảng tham số không hợp lệ.')
        return self


class FigureShape(BaseModel):
    model_config = ConfigDict(extra='ignore')
    type: Literal['segment', 'line', 'polygon', 'circle', 'angle', 'point']
    points: list[str] = Field(min_length=1, max_length=12)
    radius: str | None = Field(default=None, max_length=200)
    label: str = Field(default='', max_length=40)
    dashed: bool = False
    fill: bool = False
    right: bool = False
    highlight: bool = False

    @model_validator(mode='after')
    def check_arity(self):
        counts = {'segment': (2, 2), 'line': (2, 2), 'polygon': (3, 12), 'circle': (1, 2), 'angle': (3, 3), 'point': (1, 1)}
        low, high = counts[self.type]
        if not low <= len(self.points) <= high: raise ValueError(f'{self.type} cần {low}–{high} điểm.')
        if self.type == 'circle' and len(self.points) == 1 and not self.radius:
            raise ValueError('Đường tròn cần radius hoặc một điểm nằm trên đường tròn.')
        return self


class FigureMeasure(BaseModel):
    model_config = ConfigDict(extra='ignore')
    label: str = Field(min_length=1, max_length=60)
    expr: str = Field(min_length=1, max_length=200)
    unit: str = Field(default='', max_length=10)
    decimals: int = Field(default=2, ge=0, le=3)


class Figure(BaseModel):
    model_config = ConfigDict(extra='ignore')
    title: str = Field(default='', max_length=120)
    caption: str = Field(default='', max_length=300)
    params: list[FigureParam] = Field(default_factory=list, max_length=6)
    points: dict[str, list[str]] = Field(min_length=1, max_length=26)
    shapes: list[FigureShape] = Field(min_length=1, max_length=40)
    measures: list[FigureMeasure] = Field(default_factory=list, max_length=6)

    @field_validator('points', mode='before')
    @classmethod
    def coordinates_as_text(cls, value):
        # Accept numeric coordinates; the frontend parser receives strings.
        if isinstance(value, dict):
            return {k: [str(c) for c in v] if isinstance(v, list) else v for k, v in value.items()}
        return value

    @model_validator(mode='after')
    def check_references(self):
        names = [p.name for p in self.params]
        if len(set(names)) != len(names) or set(names) & (set(FUNCTIONS) | set(CONSTANTS)):
            raise ValueError('Tên tham số trùng hoặc trùng tên hàm.')
        values = {p.name: p.value for p in self.params}
        for name, coords in self.points.items():
            if not re.match(POINT_NAME, name) or len(coords) != 2: raise ValueError('Điểm không hợp lệ.')
            if not all(math.isfinite(v) and abs(v) <= LIMIT for v in (evaluate(c, values) for c in coords)):
                raise ValueError(f'Tọa độ điểm {name} không xác định tại giá trị mặc định.')
        for shape in self.shapes:
            if any(p not in self.points for p in shape.points): raise ValueError('Hình tham chiếu điểm chưa khai báo.')
            if shape.radius is not None: evaluate(shape.radius, values)
        for measure in self.measures: evaluate(measure.expr, values)
        return self
