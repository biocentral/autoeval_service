import logging
import requests
import re
import math

from typing import Optional, Any
from functools import lru_cache
from datetime import datetime, timedelta

from biotrainer_core.data_classes.autoeval import AutoEvalReport
from biotrainer_core.data_classes.autoeval import PBCSupervisedDatasetName, all_pbc_supervised_datasets
from biotrainer_core.data_classes.bioengineer_data_classes import ZeroShotMethod

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
MAX_EMBEDDER_NAME_LENGTH = 150
EMBEDDER_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_.\-]+(/[a-zA-Z0-9_.\-]+)?$")

# FRAMEWORKS
ALLOWED_SUPERVISED_FRAMEWORKS = {"PBC_SUPERVISED"}
ALLOWED_ZEROSHOT_FRAMEWORKS = {"PGYM"}
ALLOWED_ZEROSHOT_CONTACT_FRAMEWORKS = {"PBC_ZEROSHOT_CONTACT"}
ALLOWED_SUPERVISED_CONTACT_FRAMEWORKS = {"PBC_SUPERVISED_CONTACT"}

# PBC
N_EXPECTED_TASKS_PBC = len(all_pbc_supervised_datasets())
EXPECTED_MIN_SEQ_LEN_PBC = 0
EXPECTED_MAX_SEQ_LEN_PBC = 2000

# PGYM
N_EXPECTED_TASKS_PGYM = 3
EXPECTED_TASKS_PGYM = {"PGYM-virus", "PGYM-nonvirus", "PGYM-total"}

# CONTACT
N_EXPECTED_TASKS_CONTACT = 3
EXPECTED_TASKS_CONTACT = {"casp14", "casp15", "selected_protein"}

DANGEROUS_PATTERNS = [
    # HTML / Script / XSS injection
    re.compile(r"<\s*script\b", re.IGNORECASE),
    re.compile(r"<\s*/\s*script\b", re.IGNORECASE),
    re.compile(r"<\s*iframe\b", re.IGNORECASE),
    re.compile(r"<\s*object\b", re.IGNORECASE),
    re.compile(r"<\s*embed\b", re.IGNORECASE),
    re.compile(r"<\s*svg\b[^>]*\bonload\b", re.IGNORECASE),
    re.compile(r"<\s*img\b[^>]*\bonerror\b", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"vbscript\s*:", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"\bon(error|load|click|mouseover|focus|blur)\s*=", re.IGNORECASE),

    # Code execution / Command injection
    re.compile(r"__import__"),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\beval\s*\("),
    re.compile(r"\bos\.(system|popen)\b"),
    re.compile(r"\bsubprocess\.(Popen|run|call|check_output|check_call)\b"),
    re.compile(r"\b(sh|bash|cmd|powershell)\s+-c\b"),

    # Template injection
    re.compile(r"\{\{.*?}}"),
    re.compile(r"\$\{.*?}"),
    re.compile(r"<%.*?%>"),

    # Path traversal
    re.compile(r"\.\.[/\\]"),

    # Null byte
    re.compile(r"\x00"),
]


def _scan_for_injection(data: Any) -> Optional[str]:
    if isinstance(data, str):
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(data):
                return f"Potential security issue or code injection attempt detected"
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str):
                for pattern in DANGEROUS_PATTERNS:
                    if pattern.search(k):
                        return f"Potential security issue or code injection attempt detected in key."
            err = _scan_for_injection(v)
            if err:
                return err
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            err = _scan_for_injection(item)
            if err:
                return err
    return None


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
            lambda report: self.validate_security_injections(report),
            lambda report: self.validate_embedder_name(report),
            lambda report: self.validate_training_date(report),
            lambda report: self.validate_framework_names(report),
            lambda report: self.validate_any_result_exists(report),
            lambda report: self.validate_supervised_results(report),
            lambda report: self.validate_zeroshot_results(report),
            lambda report: self.validate_zeroshot_contact_results(report),
            lambda report: self.validate_supervised_contact_results(report),
            lambda report: self.validate_metric_values(report),
        ]
        for func in validation_functions:
            error = func(self._report)
            if error:
                return error
        return None

    @staticmethod
    def validate_embedder_name(report: AutoEvalReport) -> Optional[str]:
        embedder_name = report.embedder_name
        if not embedder_name or len(embedder_name.strip()) == 0:
            return "Embedder name is required"
        if len(embedder_name) > MAX_EMBEDDER_NAME_LENGTH:
            return f"Embedder name cannot exceed {MAX_EMBEDDER_NAME_LENGTH} characters."
        if embedder_name not in _PREDEFINED_EMBEDDERS:
            if not EMBEDDER_NAME_REGEX.match(embedder_name) or ".." in embedder_name:
                return f"Invalid embedder name format: {embedder_name}"
        return None

    @staticmethod
    def validate_security_injections(report: AutoEvalReport) -> Optional[str]:
        data = report.model_dump()
        return _scan_for_injection(data)

    @staticmethod
    def validate_framework_names(report: AutoEvalReport) -> Optional[str]:
        for fw in report.supervised_results.keys():
            if fw not in ALLOWED_SUPERVISED_FRAMEWORKS:
                return f"Unknown or unsupported supervised framework: '{fw}'."
        for fw in report.zeroshot_results.keys():
            if fw not in ALLOWED_ZEROSHOT_FRAMEWORKS:
                return f"Unknown or unsupported zero-shot framework: '{fw}'."
        for fw in report.zeroshot_contact_results.keys():
            if fw not in ALLOWED_ZEROSHOT_CONTACT_FRAMEWORKS:
                return f"Unknown or unsupported zero-shot contact framework: '{fw}'."
        for fw in report.supervised_contact_results.keys():
            if fw not in ALLOWED_SUPERVISED_CONTACT_FRAMEWORKS:
                return f"Unknown or unsupported supervised contact framework: '{fw}'."
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

        if pgym_results.method is None:
            return "Zero-shot results must specify a scoring method."

        for task_name in pgym_results.task_results.keys():
            if task_name not in EXPECTED_TASKS_PGYM and not task_name.startswith("PGYM-"):
                return f"Unexpected task '{task_name}' in zero-shot results."

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

        if pbc_results.method != ZeroShotMethod.JACOBIAN_CONTACT:
            return f"Zeroshot contact results must use {ZeroShotMethod.JACOBIAN_CONTACT.value} method."

        for task_name in pbc_results.task_results.keys():
            clean_name = task_name.split("-")[-1]
            if clean_name not in EXPECTED_TASKS_CONTACT:
                return f"Unexpected task '{task_name}' in zero-shot contact results."

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

        for task_name in pbc_results.task_results.keys():
            clean_name = task_name.split("-")[-1]
            if clean_name not in EXPECTED_TASKS_CONTACT:
                return f"Unexpected task '{task_name}' in supervised contact results."

        return None

    @staticmethod
    def _check_metric(name: str, mean: float, lower: float, upper: float) -> Optional[str]:
        for val, label in [(mean, "mean"), (lower, "lower bound"), (upper, "upper bound")]:
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                return f"Invalid numeric value (non-finite) for metric '{name}' ({label}: {val})."
        if lower > upper + 1e-4:
            return f"Invalid confidence interval for metric '{name}': lower bound ({lower}) exceeds upper bound ({upper})."

        name_lower = name.lower()
        corr_metrics = ["scc", "spearman", "matthews-corr-coeff", "mcc", "spearmans-corr-coeff"]
        fraction_metrics = ["accuracy", "balanced-accuracy", "precision", "recall", "f1_score", "macro-f1_score", "ndcg", "auc", "p@l"]

        if any(c in name_lower for c in corr_metrics):
            if mean < -1.0 - 1e-4 or mean > 1.0 + 1e-4:
                return f"Metric '{name}' value ({mean}) is out of expected correlation range [-1.0, 1.0]."
        elif any(f in name_lower for f in fraction_metrics):
            if mean < 0.0 - 1e-4 or mean > 1.0 + 1e-4:
                return f"Metric '{name}' value ({mean}) is out of expected range [0.0, 1.0]."
        return None

    @staticmethod
    def validate_metric_values(report: AutoEvalReport) -> Optional[str]:
        # Validate supervised metrics
        if "PBC_SUPERVISED" in report.supervised_results:
            pbc_results = report.supervised_results["PBC_SUPERVISED"]
            for task_res in pbc_results.results.values():
                if task_res.test_results:
                    for test_res in task_res.test_results.values():
                        for m in (test_res.bootstrapped_metrics or []):
                            err = AutoEvalReportValidator._check_metric(m.name, m.mean, m.lower, m.upper)
                            if err:
                                return err

        # Validate zero-shot metrics
        if "PGYM" in report.zeroshot_results:
            pgym_results = report.zeroshot_results["PGYM"]
            for task_res in pgym_results.task_results.values():
                if task_res.scc:
                    err = AutoEvalReportValidator._check_metric("scc", task_res.scc.mean, task_res.scc.lower, task_res.scc.upper)
                    if err:
                        return err
                if task_res.ndcg:
                    err = AutoEvalReportValidator._check_metric("ndcg", task_res.ndcg.mean, task_res.ndcg.lower, task_res.ndcg.upper)
                    if err:
                        return err
            if pgym_results.task_results_dev:
                for task_res in pgym_results.task_results_dev.values():
                    if task_res.scc:
                        err = AutoEvalReportValidator._check_metric("scc", task_res.scc.mean, task_res.scc.lower, task_res.scc.upper)
                        if err:
                            return err
                    if task_res.ndcg:
                        err = AutoEvalReportValidator._check_metric("ndcg", task_res.ndcg.mean, task_res.ndcg.lower, task_res.ndcg.upper)
                        if err:
                            return err

        # Validate zero-shot contact metrics
        if "PBC_ZEROSHOT_CONTACT" in report.zeroshot_contact_results:
            zs_contact = report.zeroshot_contact_results["PBC_ZEROSHOT_CONTACT"]
            for ds_res in zs_contact.task_results.values():
                for m in ds_res.aggregated_result:
                    err = AutoEvalReportValidator._check_metric(m.name, m.mean, m.lower, m.upper)
                    if err:
                        return err
            if zs_contact.task_results_dev:
                for ds_res in zs_contact.task_results_dev.values():
                    for m in ds_res.aggregated_result:
                        err = AutoEvalReportValidator._check_metric(m.name, m.mean, m.lower, m.upper)
                        if err:
                            return err

        # Validate supervised contact metrics
        if "PBC_SUPERVISED_CONTACT" in report.supervised_contact_results:
            sup_contact = report.supervised_contact_results["PBC_SUPERVISED_CONTACT"]
            for ds_res in sup_contact.task_results.values():
                for m in ds_res.aggregated_result:
                    err = AutoEvalReportValidator._check_metric(m.name, m.mean, m.lower, m.upper)
                    if err:
                        return err
            if sup_contact.task_results_dev:
                for ds_res in sup_contact.task_results_dev.values():
                    for m in ds_res.aggregated_result:
                        err = AutoEvalReportValidator._check_metric(m.name, m.mean, m.lower, m.upper)
                        if err:
                            return err

        return None
