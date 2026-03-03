"""
Minimal AutoEval Report Model copied from biotrainer_autoeval:
https://github.com/sacdallago/biotrainer/tree/main/biotrainer/autoeval

Should use biotrainer directly in the future.
"""
from __future__ import annotations

import hashlib

from pathlib import Path
from pydantic import BaseModel, Field
from typing import Dict, Any, Union, Optional, List


class SupervisedFrameworkReport(BaseModel):
    min_seq_len: Optional[int] = Field(default=None, description="Minimum sequence length used during evaluation")
    max_seq_len: Optional[int] = Field(default=None, description="Maximum sequence length used during evaluation")
    results: Dict[str, Dict[str, Any]] = Field(description="Supervised autoeval results")

    def number_tasks(self):
        return len(self.results.keys())

    def get_task_names(self) -> List[str]:
        return list(self.results.keys())


class ZeroShotFrameworkReport(BaseModel):
    method: Any = Field(description="Scoring method used")
    aggregated_results: Dict[str, Any] = Field(description="Accumulated autoeval task results "
                                                                     "(combined_task_name -> RankingResult)")
    individual_results: Dict[str, Any] = Field(description="Individual autoeval task results "
                                                                     "(dataset_name -> RankingResult)")

    def number_tasks(self):
        return len(self.aggregated_results)

    def get_task_names(self) -> List[str]:
        return list(self.aggregated_results.keys())


class AutoEvalReport(BaseModel):
    embedder_name: str = Field(description="Name of the embedder")
    training_date: str = Field(description="Date of training")
    supervised_results: Dict[str, SupervisedFrameworkReport] = Field(description="Supervised autoeval results")
    zeroshot_results: Dict[str, ZeroShotFrameworkReport] = Field(description="Zero-Shot autoeval results")

    @staticmethod
    def get_file_name(embedder_name):
        return f'autoeval_report_{embedder_name.replace("/", "-")}.json'

    @classmethod
    def from_json_file(cls, file_path: Union[Path, str]) -> AutoEvalReport:
        """Load AutoEvalReport from a JSON file."""
        with open(file_path, 'r') as f:
            return cls.model_validate_json(f.read())

    def write(self, output_dir: Path):
        report_name = output_dir / self.get_file_name(self.embedder_name)

        print(f'Writing autoeval report to: {report_name}')
        with open(report_name, 'w') as report_file:
            report_file.write(self.model_dump_json(indent=4))

    def get_uid(self) -> str:
        h = hashlib.sha1()
        h.update(self.embedder_name.encode("utf-8"))
        h.update(self.training_date.encode("utf-8"))
        h.update(str(len(self.supervised_results)).encode("utf-8"))
        h.update(str(len(self.zeroshot_results)).encode("utf-8"))
        return h.hexdigest()
