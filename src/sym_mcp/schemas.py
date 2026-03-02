from __future__ import annotations

from pydantic import BaseModel, Field


class SympyInput(BaseModel):
    code: str = Field(..., min_length=1, description="包含 Python/SymPy 逻辑并通过 print 输出结果")

