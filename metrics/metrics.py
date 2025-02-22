from abc import abstractmethod

from typing import List, Dict
from nlg_eval_via_simi_measures.bary_score import BaryScoreMetric
from nlg_eval_via_simi_measures.depth_score import DepthScoreMetric
from nlg_eval_via_simi_measures.infolm import InfoLM
from tqdm import tqdm
import evaluate


class Metric:
    @abstractmethod
    def __init__(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def __call__(self, *args, **kwargs) -> List[float]:
        raise NotImplementedError


SCORE_FIELD_NAME = {
    "bleu": "bleu",
    "chrf": "score",
    "meteor": "meteor",
    "bertscore": "f1",
    "sacrebleu": "score",
    "bary": "baryscore_W",
    "depth": "depth_score",
}


class HuggingFaceMetric(Metric):
    def __init__(self, name: str):
        self.name = name
        self.scorer = evaluate.load(name)

    def __call__(
        self, references: List[str], predictions: List[str], *args, **kwargs
    ) -> List[float]:
        assert len(references) == len(
            predictions
        ), "The number of references and predictions should be the same"
        if self.name == "bertscore":
            # BERTScore should be called specifying the language or the model type, so we default to English
            if "lang" not in kwargs and "model_type" not in kwargs:
                kwargs["model_type"] = "distilbert-base-uncased"

            print("Computing BERTScore...")
            bert_scores = self.scorer.compute(
                references=[[reference] for reference in references],
                predictions=predictions,
                *args,
                **kwargs,
            )
            return bert_scores[SCORE_FIELD_NAME[self.name]]

        return [
            self.scorer.compute(
                references=[[reference]],
                predictions=[prediction],
                *args,
                **kwargs,
            )[SCORE_FIELD_NAME[self.name]]
            for reference, prediction in tqdm(zip(references, predictions))
        ]


class NLGEvalViaSimilarityMeasuresMetric(Metric):
    def __init__(self, name: str, *args, **kwargs):
        self.name = name
        kwargs["model_name"] = kwargs.get("model_name", "distilbert-base-uncased")
        if name == "bary":
            self.scorer = BaryScoreMetric(*args, **kwargs)
        elif name == "depth":
            kwargs["layers_to_consider"] = kwargs.get("layers_to_consider", 5)
            self.scorer = DepthScoreMetric(*args, **kwargs)
        elif name == "infolm":
            self.scorer = InfoLM(*args, **kwargs)
        else:
            raise ValueError(
                f"Unknown metric {name}, expected one of bary, depth, infolm"
            )

    def __call__(self, references: List[str], predictions: List[str]) -> List[float]:
        assert len(references) == len(
            predictions
        ), "The number of references and predictions should be the same"
        self.scorer.prepare_idfs(references, predictions)
        return self.scorer.evaluate_batch(references, predictions)[
            self.scorer.measure_to_use
            if self.name == "infolm"
            else SCORE_FIELD_NAME[self.name]
        ]


def load_all_metrics() -> Dict[str, Metric]:
    return {
        "bleu": HuggingFaceMetric("bleu"),
        "chrf": HuggingFaceMetric("chrf"),
        "meteor": HuggingFaceMetric("meteor"),
        "bertscore": HuggingFaceMetric("bertscore"),
        "sacrebleu": HuggingFaceMetric("sacrebleu"),
        "bary": NLGEvalViaSimilarityMeasuresMetric("bary"),
        "depth": NLGEvalViaSimilarityMeasuresMetric("depth"),
        "infolm": NLGEvalViaSimilarityMeasuresMetric("infolm"),
    }


if __name__ == "__main__":
    import json

    metrics = load_all_metrics()

    references = ["I like my cakes very much", "I hate these cakes!"]
    predictions = ["I adore my cakes", "These cakes are bad!"]

    scores = {}
    for name, metric in metrics.items():
        scores[name] = metric(references, predictions)

    print(json.dumps(scores, indent=2))
