from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, EmailStr

from .biotrainer_autoeval.autoeval_report import AutoEvalReport


# TODO Share models between biotrainer and service

class PublishRequest(BaseModel):
    report: AutoEvalReport = Field(description="Report to publish")
    name: str = Field(description="Name of the publisher")
    email: EmailStr = Field(description="Email of the publisher")
    citation: Optional[str] = Field(default=None, description="Citation to be used for the model, must be a valid DOI")

    @field_validator('citation')
    def validate_citation(cls, v):
        if v is not None and not "doi" in str(v).lower():
            raise ValueError("Citation must be a valid DOI")
        if v is not None and len(v) > 100:
            raise ValueError("Citation must be less than 100 characters")
        return v


class ComparisonStoreRequest(BaseModel):
    """ Request for storing a report temporarily for comparison in the dashboard"""
    report: AutoEvalReport = Field(description="Report to store")


class ComparisonStoreResponse(BaseModel):
    """ Response for storing a report temporarily for comparison in the dashboard"""
    uid: str = Field(description="Unique identifier for the stored report")


class ComparisonRetrieveResponse(BaseModel):
    """ Response for retrieving a stored report for comparison """
    report: AutoEvalReport = Field(description="Report retrieved")


class ReportsResponse(BaseModel):
    reports: List[AutoEvalReport] = Field(description="List of all available reports")


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
