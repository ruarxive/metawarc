from datetime import datetime
from typing import Dict, List, Union, Optional
from pydantic import BaseModel, Field

class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["Detailed error message"])
