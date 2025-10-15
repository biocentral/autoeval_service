from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class PublishRequest(BaseModel):
    result: str = Field(..., description="JSON string containing result data")


class LeaderboardData(BaseModel):
    leaderboard: Dict[str, Any]
    recommended_metrics: Dict[str, Any]


class LeaderboardResponse(BaseModel):
    leaderboard: Dict[str, Any]
    recommended_metrics: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "leaderboard": {"model1": {"score": 0.95}},
                "recommended_metrics": {"accuracy": "primary"}
            }
        }


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None