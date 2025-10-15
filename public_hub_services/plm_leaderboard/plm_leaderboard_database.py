import os
import json
import yaml
import redis
import logging

from pathlib import Path
from typing import Optional, List, Dict, Any

from ..utils import Constants

logger = logging.getLogger(__name__)


class PLMLeaderboardDatabase:
    key_delimiter = '\t'

    def __init__(self, backup_data: Optional[Path] = None):
        redis_url = os.environ.get('LEADERBOARD_REDIS_URL', 'redis://localhost:6380')

        logger.info('Connecting to redis URL: {}'.format(redis_url))
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

        logger.info(self.redis_client.info())

        if backup_data is not None:
            self._clear_database()
            self.load_leaderboard_to_redis(backup_data=backup_data)

    def load_leaderboard_to_redis(self, backup_data: Path):
        if backup_data.suffix in ['.yml', '.yaml']:
            self.import_from_yaml(backup_data)
        else:
            raise ValueError("Unsupported file format. Use .csv, .yml, or .yaml")

    def _get_entry_id(self, entry):
        entry_id = f"{entry['embedder_name']}{self.key_delimiter}{entry['training_date']}"
        return entry_id

    def _sanity_check_entry(self, entry: Dict[str, Dict[str, Any]]) -> str:
        # TODO Add proper verification
        NUM_EXPECTED_DATASETS = 8
        results = entry["results"]
        if len(results.keys()) != NUM_EXPECTED_DATASETS:
            return f"Number of expected datasets is not {NUM_EXPECTED_DATASETS}!"

        return ""

    def add_entry(self, entry: Dict[str, Dict[str, Any]]) -> bool:
        entry_id = self._get_entry_id(entry)
        self.redis_client.set(f"plm-leaderboard:{entry_id}", json.dumps(entry))

        # Add to set of all entries
        self.redis_client.sadd('plm-leaderboard:all_entries', entry_id)

        return True

    def add_publishing_data(self, result: Dict[str, Any]) -> str:
        logger.info(f'Publishing data.. {result}')

        entry_id = self._get_entry_id(result)
        existing_entry = self.get_entry(entry_id=entry_id)

        if existing_entry:
            return f"Entry with ID {entry_id} already exists"

        sanity_check_error = self._sanity_check_entry(entry=result)
        if sanity_check_error != "":
            return sanity_check_error

        if self.add_entry(result):
            # TODO Remove, only debug
            self.export_to_yaml(output_path=Constants.LOGGER_DIR / Path("published.yml"))
            return ""  # Success

        return "Failed to add entry to leaderboard!"

    def get_entry(self, entry_id: str) -> Optional[Dict[str, any]]:
        entry = self.redis_client.get(f"plm-leaderboard:{entry_id}")
        if not entry:
            return None

        return entry

    def get_all_data(self) -> List[Dict[str, any]]:
        all_entry_ids = self.redis_client.smembers('plm-leaderboard:all_entries')
        return [self.get_entry(entry_id) for entry_id in all_entry_ids]

    """
    def delete_entry(self, model_name: str) -> bool:
        entry_id = f"{model_name}"
        key = f"plm-leaderboard:{entry_id}"
        if self.redis_client.exists(key):
            self.redis_client.delete(key)
            self.redis_client.srem('plm-leaderboard:all_entries', entry_id)
            return True
        return False
    """

    def _clear_database(self) -> bool:
        try:
            all_keys = self.redis_client.keys('plm-leaderboard:*')
            if all_keys:
                self.redis_client.delete(*all_keys)
            return True
        except Exception as e:
            logger.error(f"An error occurred while clearing the database: {str(e)}")
            return False

    def export_to_yaml(self, output_path: Path):
        data = self.get_all_data()
        export = {'leaderboard': data}
        with open(output_path, 'w') as file:
            yaml.dump(export, file)

    def import_from_yaml(self, input_path: Path):
        with open(input_path, 'r') as file:
            data = yaml.safe_load(file)
        for entry in data['leaderboard']:
            entry_dict = json.loads(entry)
            self.add_entry(entry_dict)


def init_leaderboard_database_instance(backup_data: Optional[Path] = None) -> PLMLeaderboardDatabase:
    """Factory function to create the database instance"""
    return PLMLeaderboardDatabase(backup_data=backup_data)