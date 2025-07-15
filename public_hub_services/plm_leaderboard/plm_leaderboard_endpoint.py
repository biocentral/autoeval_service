import json
import logging

from .frameworks import get_recommended_metrics
from .plm_leaderboard_database import PLMLeaderboardDatabase

from flask import Blueprint, jsonify, current_app, request

logger = logging.getLogger(__name__)

plm_leaderboard_service_route = Blueprint('plm_leaderboard', __name__)

def _get_leaderboard_dict(plm_leaderboard_db):
    all_data = plm_leaderboard_db.get_all_data()
    recommended_metrics = get_recommended_metrics(framework="flip")
    return {"leaderboard": all_data, "recommended_metrics": recommended_metrics}

@plm_leaderboard_service_route.route('/plm_leaderboard/', methods=['GET'])
def plm_leaderboard():
    logger.info('[GET] PLM Leaderboard')
    plm_leaderboard_db: PLMLeaderboardDatabase = current_app.config["PLM_LEADERBOARD_DATABASE"]
    return jsonify(_get_leaderboard_dict(plm_leaderboard_db))

@plm_leaderboard_service_route.route('/plm_leaderboard_publish/', methods=['POST'])
def plm_leaderboard_publish():
    logger.info('[POST] PLM Leaderboard Publish')

    publish_data = request.get_json()
    result = json.loads(publish_data["result"])

    plm_leaderboard_db: PLMLeaderboardDatabase = current_app.config["PLM_LEADERBOARD_DATABASE"]
    logger.info('[POST] PLM Leaderboard DATABASE SUCCESS')

    publishing_error = plm_leaderboard_db.add_publishing_data(result=result)
    if publishing_error != "":
        return jsonify({"error": publishing_error})

    return jsonify(_get_leaderboard_dict(plm_leaderboard_db))
