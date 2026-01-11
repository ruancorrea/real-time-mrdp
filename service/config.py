# Em um novo arquivo, ex: service/config.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class ClusteringAlgorithm(Enum):
    CKMEANS = "ckmeans"
    GREEDY = "greedy_clustering"

class RoutingAlgorithm(Enum):
    BRKGA = "brkga"
    GREEDY = "greedy_routing"

class HybridAlgorithm(Enum):
    GREEDY_INSERTION = "greedy_insertion"
    BRKGA_HYBRID = "brkga_hybrid"
    MANUAL = "manual"

@dataclass
class SimulationConfig:
    clustering_algo: Optional[ClusteringAlgorithm] = None
    routing_algo: Optional[RoutingAlgorithm] = None
    hybrid_algo: Optional[HybridAlgorithm] = None

    def __str__(self):
        name = ''
        if self.clustering_algo:
            name += 'CLUSTERIZAÇÃO com ' + self.clustering_algo.value + ' | '
        if self.routing_algo:
            name += 'ROTEIRIZAÇÃO com ' + self.routing_algo.value
        if self.hybrid_algo:
            name += 'HÍBRIDO com ' + self.hybrid_algo.value
        return name


