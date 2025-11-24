# Em um novo arquivo, ex: service/config.py
from dataclasses import dataclass
from enum import Enum

class ClusteringAlgorithm(Enum):
    CKMEANS = "ckmeans"
    GREEDY = "greedy_clustering"

class RoutingAlgorithm(Enum):
    BRKGA = "brkga"
    GREEDY = "greedy_routing"

class CombinedAlgorithm(Enum):
    GREEDY_COMBINED = "greedy_combined"

@dataclass
class SimulationConfig:
    clustering_algo: ClusteringAlgorithm = ClusteringAlgorithm.CKMEANS
    routing_algo: RoutingAlgorithm = RoutingAlgorithm.BRKGA
    combined_algo: CombinedAlgorithm = None
