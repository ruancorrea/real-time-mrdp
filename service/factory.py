from service.config import (
    SimulationConfig,
    ClusteringAlgorithm,
    RoutingAlgorithm,
    HybridAlgorithm
)

from service.strategies import (
    CKMeansClustering,
    GreedyClustering,
    BRKGARouting,
    GreedyRouting,
    GreedyHybrid,
    BRKGAHybrid,
)
from service.heuristics.manual_assignment import ManualAssignmentStrategy

def get_strategies(config: SimulationConfig):
    '''Fábrica que retorna as instâncias de estratégia com base na config.'''

    # Se uma estratégia híbrida for definida, ela tem precedência
    if config.hybrid_algo:
        hybrid_strategy_map = {
            HybridAlgorithm.GREEDY_INSERTION: GreedyHybrid,
            HybridAlgorithm.BRKGA_HYBRID: BRKGAHybrid,
            HybridAlgorithm.MANUAL: ManualAssignmentStrategy,
        }
        return None, None, hybrid_strategy_map[config.hybrid_algo]()

    # Caso contrário, retorna as estratégias de clusterização e roteamento
    clustering_strategy_map = {
        ClusteringAlgorithm.CKMEANS: CKMeansClustering,
        ClusteringAlgorithm.GREEDY: GreedyClustering,
    }

    routing_strategy_map = {
        RoutingAlgorithm.BRKGA: BRKGARouting,
        RoutingAlgorithm.GREEDY: GreedyRouting,
    }

    clustering_strategy = clustering_strategy_map.get(config.clustering_algo)
    routing_strategy = routing_strategy_map.get(config.routing_algo)

    return clustering_strategy(), routing_strategy(), None