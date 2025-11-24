from service.config import (
    SimulationConfig,
    ClusteringAlgorithm,
    RoutingAlgorithm,
    CombinedAlgorithm
)

from service.strategies import (
    CKMeansClustering,
    GreedyClustering,
    BRKGARouting,
    GreedyRouting
)

def get_strategies(config: SimulationConfig):
    '''Fábrica que retorna as instâncias de estratégia com base na config.'''
    
    # Lógica para o caso combinado (opção 5)
    if config.combined_algo == CombinedAlgorithm.GREEDY_COMBINED:
        pass
        '''

            # self.combined_strategy = GlobalCheapestInsertionStrategy()
            self.clustering_strategy = None
            self.routing_strategy = None
        else:
            self.clustering_strategy, self.routing_strategy = get_strategies(config)
        '''

    # Lógica para os casos separados
    clustering_strategy_map = {
        ClusteringAlgorithm.CKMEANS: CKMeansClustering,
        ClusteringAlgorithm.GREEDY: GreedyClustering,
    }
    
    routing_strategy_map = {
        RoutingAlgorithm.BRKGA: BRKGARouting,
        RoutingAlgorithm.GREEDY: GreedyRouting,
    }

    return (
        clustering_strategy_map[config.clustering_algo](),
        routing_strategy_map[config.routing_algo]()
    )