from typing import Optional, List
from pydantic import BaseModel, Field

from biotrainer_core.data_classes.autoeval import AutoEvalReport, AutoEvalPublishedReport


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
    """ Response for retrieving all published reports"""
    reports: List[AutoEvalPublishedReport] = Field(description="List of all available reports")


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
