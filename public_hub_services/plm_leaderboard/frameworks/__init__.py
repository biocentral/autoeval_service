from .flip_datasets import FLIP_DATASETS

def get_recommended_metrics(framework: str = "flip"):
    match framework:
        case "flip":
            return {dataset: values["evaluation_metric"] for dataset, values in FLIP_DATASETS.items()}

    return {}


__all__ = ["get_recommended_metrics", "FLIP_DATASETS"]