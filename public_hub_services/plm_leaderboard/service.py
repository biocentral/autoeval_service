# app/plm_leaderboard/service.py
import json
import logging

from .models import LeaderboardData
from .frameworks import get_recommended_metrics
from .plm_leaderboard_database import PLMLeaderboardDatabase

logger = logging.getLogger(__name__)


class PLMLeaderboardService:
    def __init__(self, database: PLMLeaderboardDatabase):
        self.database = database

    async def get_leaderboard_data(self) -> LeaderboardData:
        """Get complete leaderboard data"""
        all_data = await self.database.get_all_data()
        recommended_metrics = get_recommended_metrics(framework="flip")

        return LeaderboardData(
            leaderboard=all_data,
            recommended_metrics=recommended_metrics
        )

    async def publish_data(self, result_json: str) -> LeaderboardData:
        """Publish new data and return updated leaderboard"""
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")

        publishing_error = await self.database.add_publishing_data(result=result)
        if publishing_error:
            raise ValueError(publishing_error)

        return await self.get_leaderboard_data()