from pydantic import BaseModel


class ProblemValidationResponse(BaseModel):
    valid: bool
