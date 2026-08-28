import logging
import requests

from typing import Optional
from functools import lru_cache
from datetime import datetime, timedelta

from biotrainer_core.data_classes.autoeval import AutoEvalReport
from biotrainer_core.data_classes.autoeval import PBCSupervisedDatasetName, all_pbc_supervised_datasets

logger = logging.getLogger(__name__)

_PREDEFINED_EMBEDDERS = {
    "one_hot_encoding",
    "random_embedder",
    "length_embedder",
    "AAOntology",
    "blosum62",
}

# VALIDATION CONSTANTS
# GENERAL
MAX_ALLOWED_TIME_DELTA = timedelta(days=60)
# PBC
N_EXPECTED_TASKS_PBC = len(all_pbc_supervised_datasets())
EXPECTED_MIN_SEQ_LEN_PBC = 0
EXPECTED_MAX_SEQ_LEN_PBC = 2000
# PGYM
N_EXPECTED_TASKS_PGYM = 3
# CONTACT
N_EXPECTED_TASKS_CONTACT = 3


@lru_cache(maxsize=12)
def _validate_model_id(model_id: str) -> Optional[str]:
    if model_id in _PREDEFINED_EMBEDDERS:
        return None

    url = f"https://huggingface.co/api/models/{model_id}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            # Model exists
            return None
        elif response.status_code == 401:
            # Model not found
            return "Model not found on huggingface!"
        else:
            # Handle other status codes
            return f"Unexpected huggingface status code: {response.status_code}"
    except requests.RequestException as e:
        return f"Error checking model availability on huggingface: {e}"


class AutoEvalReportValidator:
    """ Some hard-coded validation rules for AutoEvalReport, performed before storing and publishing"""

    def __init__(self, report: AutoEvalReport):
        self._report = report

    def check_official(self) -> bool:
        embedder_name = self._report.embedder_name

        if embedder_name in _PREDEFINED_EMBEDDERS:
            return True
        
        huggingface_error = _validate_model_id(embedder_name)

        if huggingface_error:
            logger.info(f"Encountered huggingface "
                        f"error while publishing model {self._report.embedder_name}: {huggingface_error}")
            return False
        return True

    def validate(self) -> Optional[str]:
        validation_functions = [
            lambda report: self.validate_embedder_name(report),
            lambda report: self.validate_training_date(report),
            lambda report: self.validate_any_result_exists(report),
            lambda report: self.validate_supervised_results(report),
            lambda report: self.validate_zeroshot_results(report),
            lambda report: self.validate_zeroshot_contact_results(report),
            lambda report: self.validate_supervised_contact_results(report),
        ]
        for func in validation_functions:
            error = func(self._report)
            if error:
                return error
        return None

    @staticmethod
    def validate_embedder_name(report: AutoEvalReport) -> Optional[str]:
        embedder_name = report.embedder_name
        if len(embedder_name) == 0:
            return "Embedder name is required"
        return None

    @staticmethod
    def validate_training_date(report: AutoEvalReport) -> Optional[str]:
        training_date = report.training_date
        try:
            # Parse the training_date
            training_date_obj = datetime.strptime(training_date, "%Y-%m-%d")
        except ValueError:
            return "Invalid date format. Expected YYYY-MM-DD."

        current_date = datetime.now()
        n_days_ago = current_date - MAX_ALLOWED_TIME_DELTA

        # Check if the date is in the future
        if training_date_obj > (current_date + timedelta(days=1)):  # Account for time zone differences
            return "Training date cannot be in the future."

        # Check if the date is older than MAX_ALLOWED_TIME_DELTA.days
        if training_date_obj < n_days_ago:
            return f"Training result cannot be older than {MAX_ALLOWED_TIME_DELTA.days} days."

        return None

    @staticmethod
    def validate_any_result_exists(report: AutoEvalReport) -> Optional[str]:
        all_reports = [report.supervised_results, report.zeroshot_results, report.zeroshot_contact_results,
                       report.supervised_contact_results]

        all_empty = all(len(report) == 0 for report in all_reports)
        if all_empty:
            return "No results found for any framework!"
        return None

    @staticmethod
    def validate_supervised_results(report: AutoEvalReport) -> Optional[str]:
        supervised_results = report.supervised_results

        if len(supervised_results) == 0:
            return None

        pbc_results = supervised_results.get("PBC_SUPERVISED", None)
        if pbc_results is None:
            return "Supervised results must contain PBC task."

        if len(pbc_results.results) != N_EXPECTED_TASKS_PBC:
            return f"Supervised results must contain {N_EXPECTED_TASKS_PBC} tasks."

        if pbc_results.min_seq_len != EXPECTED_MIN_SEQ_LEN_PBC or pbc_results.max_seq_len != EXPECTED_MAX_SEQ_LEN_PBC:
            return (f"Supervised results must have "
                    f"min_seq_len={EXPECTED_MIN_SEQ_LEN_PBC} and "
                    f"max_seq_len={EXPECTED_MAX_SEQ_LEN_PBC} for publishing.")

        all_tasks = set(list(pbc_results.results.keys()))

        if len(all_tasks) != len(list(pbc_results.results.keys())):
            return "Found duplicate tasks in supervised results."

        for pbc_dataset in PBCSupervisedDatasetName:
            if not any(pbc_dataset.value in task for task in all_tasks):
                return f"Supervised results must contain results for {pbc_dataset} dataset."

        return None

    @staticmethod
    def validate_zeroshot_results(report: AutoEvalReport) -> Optional[str]:
        zeroshot_results = report.zeroshot_results

        if len(zeroshot_results) == 0:
            return None

        pgym_results = zeroshot_results.get("PGYM", None)
        if pgym_results is None:
            return "Zero-shot results must contain PGYM task."

        if len(pgym_results.task_results) != N_EXPECTED_TASKS_PGYM:
            return f"Zero-shot results must contain {N_EXPECTED_TASKS_PGYM} tasks."

        return None

    @staticmethod
    def validate_zeroshot_contact_results(report: AutoEvalReport) -> Optional[str]:
        zeroshot_contact_results = report.zeroshot_contact_results

        if len(zeroshot_contact_results) == 0:
            return None

        pbc_results = zeroshot_contact_results.get("PBC_ZEROSHOT_CONTACT", None)
        if pbc_results is None:
            return "Zeroshot contact results must contain PBC framework."

        if len(pbc_results.task_results) != N_EXPECTED_TASKS_CONTACT:
            return f"Zeroshot contact results must contain {N_EXPECTED_TASKS_CONTACT} tasks."

        return None

    @staticmethod
    def validate_supervised_contact_results(report: AutoEvalReport) -> Optional[str]:
        supervised_contact_results = report.supervised_contact_results

        if len(supervised_contact_results) == 0:
            return None

        pbc_results = supervised_contact_results.get("PBC_SUPERVISED_CONTACT", None)
        if pbc_results is None:
            return "Supervised contact results must contain PBC framework."

        if len(pbc_results.task_results) != N_EXPECTED_TASKS_CONTACT:
            return f"Supervised contact results must contain {N_EXPECTED_TASKS_CONTACT} tasks."

        return None
