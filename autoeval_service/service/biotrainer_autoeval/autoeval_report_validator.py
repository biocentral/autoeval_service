import requests

from typing import Optional
from functools import lru_cache
from datetime import datetime, timedelta

from .autoeval_report import AutoEvalReport

# TODO Replace Biotrainer and autoeval constants
_PREDEFINED_EMBEDDERS = {
    "one_hot_encoding",
    "random_embedder",
    "AAOntology",
    "blosum62",
}

_PBC_DATASETS = {
    "binding",
    "conservation",
    "disorder",
    "membrane",
    "scl",
    "secondary_structure",
}

# VALIDATION CONSTANTS
# GENERAL
MAX_ALLOWED_TIME_DELTA = timedelta(days=60)
# PBC
N_EXPECTED_TASKS_PBC = 4
EXPECTED_MIN_SEQ_LEN_PBC = 0
EXPECTED_MAX_SEQ_LEN_PBC = 2000
# PGYM
N_EXPECTED_TASKS_PGYM = 3


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

    def validate(self) -> Optional[str]:
        validation_functions = [lambda report: self.validate_embedder_name(report),
                                lambda report: self.validate_training_date(report),
                                lambda report: self.validate_supervised_results(report),
                                lambda report: self.validate_zeroshot_results(report)]
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

        huggingface_error = _validate_model_id(embedder_name)
        if huggingface_error:
            return (f"Embedder name not found on huggingface: (Error - {huggingface_error})\n"
                    f"If you do want to submit your model, please contact us at info@biocentral.cloud.")
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
    def validate_supervised_results(report: AutoEvalReport) -> Optional[str]:
        supervised_results = report.supervised_results
        zeroshot_results = report.zeroshot_results

        if len(supervised_results) == 0:
            if len(zeroshot_results) > 0:
                return None
            return "No results found for any framework!"

        pbc_results = supervised_results.get("PBC", None)
        if pbc_results is None:
            return "Supervised results must contain PBC task."

        if len(pbc_results.results) != N_EXPECTED_TASKS_PBC:
            return f"Supervised results must contain {N_EXPECTED_TASKS_PBC} tasks."

        if pbc_results.min_seq_len != EXPECTED_MIN_SEQ_LEN_PBC or pbc_results.max_seq_len != EXPECTED_MAX_SEQ_LEN_PBC:
            return (f"Supervised results must have "
                    f"min_seq_len={EXPECTED_MIN_SEQ_LEN_PBC} and "
                    f"max_seq_len={EXPECTED_MAX_SEQ_LEN_PBC} for publishing.")

        # TODO Retrieve from biotrainer

        all_tasks = set(list(pbc_results.results.keys()))

        if len(all_tasks) != len(list(pbc_results.results.keys())):
            return "Found duplicate tasks in supervised results."

        for pbc_dataset in _PBC_DATASETS:
            if not any(pbc_dataset in task for task in all_tasks):
                return f"Supervised results must contain results for {pbc_dataset} dataset."

        return None

    @staticmethod
    def validate_zeroshot_results(report: AutoEvalReport) -> Optional[str]:
        supervised_results = report.supervised_results
        zeroshot_results = report.zeroshot_results

        if len(zeroshot_results) == 0:
            if len(supervised_results) > 0:
                return None
            return "No results found for any framework!"

        pgym_results = zeroshot_results.get("PGYM", None)
        if pgym_results is None:
            return "Zero-shot results must contain PGYM task."

        if len(pgym_results.aggregated_results) != N_EXPECTED_TASKS_PGYM:
            return f"Zero-shot results must contain {N_EXPECTED_TASKS_PGYM} tasks."

        return None
