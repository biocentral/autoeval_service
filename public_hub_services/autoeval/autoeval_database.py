import os
import redis
import logging

from pathlib import Path
from typing import Optional, List

from .biotrainer_autoeval.autoeval_report import AutoEvalReport
from .models import PublishRequest, ComparisonStoreRequest

logger = logging.getLogger(__name__)


class AutoEvalDatabase:
    PUBLISH_PREFIX = "autoeval:publish:"
    COMPARISON_PREFIX = "autoeval:comparison:"
    ALL_PUBLISHED_KEY = "autoeval:all_published"

    def __init__(self):
        redis_url = os.environ.get('LEADERBOARD_REDIS_URL', 'redis://localhost:6380')

        logger.info('Connecting to redis URL: {}'.format(redis_url))
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

        logger.info(self.redis_client.info())

    def add_publish_request(self, request: PublishRequest) -> bool:
        uid = request.report.get_uid()
        key = f"{self.PUBLISH_PREFIX}{uid}"
        try:
            self.redis_client.set(key, request.model_dump_json())
            self.redis_client.sadd(self.ALL_PUBLISHED_KEY, uid)
            return True
        except Exception as e:
            logger.error(f"Error adding publish request: {str(e)}")
            return False

    def get_publish_request(self, uid: str) -> Optional[PublishRequest]:
        key = f"{self.PUBLISH_PREFIX}{uid}"
        data = self.redis_client.get(key)
        if not data:
            return None
        return PublishRequest.model_validate_json(data)

    def get_all_publish_requests(self) -> List[PublishRequest]:
        uids = self.redis_client.smembers(self.ALL_PUBLISHED_KEY)
        requests = []
        for uid in uids:
            req = self.get_publish_request(uid)
            if req:
                requests.append(req)
        return requests

    def add_comparison_request_report(self, request: ComparisonStoreRequest) -> Optional[str]:
        uid = request.report.get_uid()
        key = f"{self.COMPARISON_PREFIX}{uid}"
        try:
            # Store for 1 day (86400 seconds)
            self.redis_client.setex(key, 86400, request.report.model_dump_json())
            return uid
        except Exception as e:
            logger.error(f"Error adding comparison request: {str(e)}")
            return None

    def get_comparison_request_report(self, uid: str) -> Optional[AutoEvalReport]:
        key = f"{self.COMPARISON_PREFIX}{uid}"
        data = self.redis_client.get(key)
        if not data:
            return None
        return AutoEvalReport.model_validate_json(data)

    def _clear_database(self) -> bool:
        try:
            all_keys = self.redis_client.keys('autoeval:*')
            if all_keys:
                self.redis_client.delete(*all_keys)
            return True
        except Exception as e:
            logger.error(f"An error occurred while clearing the database: {str(e)}")
            return False


def init_autoeval_database_instance() -> AutoEvalDatabase:
    """Factory function to create the database instance"""
    return AutoEvalDatabase()
