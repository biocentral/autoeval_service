# app/plm_leaderboard/router.py
import logging
from fastapi import APIRouter, HTTPException, Depends

from .models import PublishRequest, LeaderboardResponse, ErrorResponse
from .service import PLMLeaderboardService
from .dependencies import get_plm_leaderboard_service

logger = logging.getLogger(__name__)

# Create router for this module
router = APIRouter(
    prefix="/plm_leaderboard",
    tags=["plm-leaderboard"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/",
    response_model=LeaderboardResponse,
    summary="Get PLM Leaderboard",
    description="Retrieve the current PLM leaderboard data with recommended metrics"
)
async def get_plm_leaderboard(
        service: PLMLeaderboardService = Depends(get_plm_leaderboard_service)
):
    """Get PLM Leaderboard data"""
    logger.info('[GET] PLM Leaderboard')

    try:
        leaderboard_data = await service.get_leaderboard_data()
        return leaderboard_data
    except Exception as e:
        logger.error(f"Error getting leaderboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/publish/",
    response_model=LeaderboardResponse,
    responses={400: {"model": ErrorResponse}},
    summary="Publish PLM Data",
    description="Publish new data to the PLM leaderboard"
)
async def publish_plm_leaderboard(
        publish_request: PublishRequest,
        service: PLMLeaderboardService = Depends(get_plm_leaderboard_service)
):
    """Publish data to PLM Leaderboard"""
    logger.info('[POST] PLM Leaderboard Publish')

    try:
        leaderboard_data = await service.publish_data(publish_request.result)
        return leaderboard_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error publishing data: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
