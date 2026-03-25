from typing import Dict, List
from utils.fs import get_configs

class LLMProvider:
    def __init__(self, name: str) -> None:
        self.name = name

class LLMRouter:
    def __init__(self) -> None:
        self.providers: Dict[str, List[LLMProvider]] = {
            "local": [

            ],
            "cloud": [

            ]
        }


def main():
    router = LLMRouter()
    configs = get_configs()
   
    print(configs['roles.toml'])
    print(configs['tickers.toml'])

    # TODO: LLM recursion pipeline:
    # Ingestion
    # Corroboration
    # Evidence Fusion
    # Temporal Normalization
    # World State Model
    # Global Constraint Index

    # TODO: Hybrid staged pipeline:
    # Time-series constraint
    # DAG trajectory
    # KL-Divergence


if __name__ == "__main__":
    main()
