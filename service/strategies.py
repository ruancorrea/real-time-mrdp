from abc import ABC, abstractmethod
from typing import List, Dict, Any
import numpy as np

from service.structures import Delivery, Vehicle 

class ClusteringStrategy(ABC):
    @abstractmethod
    def cluster(
        self,
        deliveries: List[Delivery],
        vehicles: List[Vehicle],
        depot_origin: np.array
    ) -> Dict[int, List[Delivery]]:
        '''
        Recebe uma lista de entregas e veículos, e retorna um dicionário
        mapeando o ID do veículo para uma lista de entregas atribuídas a ele.
        '''
        pass

class RoutingStrategy(ABC):
    @abstractmethod
    def generate_routes(
        self,
        deliveries_by_vehicle: Dict[int, List[Delivery]],
        depot_origin: np.array,
        avg_speed_kmh: int
    ) -> Dict[int, Dict[str, Any]]:
        '''
        Recebe as entregas agrupadas por veículo e retorna os detalhes da rota para cada um.
        O dicionário de retorno deve conter a rota otimizada (sequência, tempos, etc.).
        '''
        pass


# --- CLUSTERING ---

from service.clustering.ckmeans import capacitated_kmeans
from service.heuristics.greedy_clustering import sequential_assignment_heuristic

class CKMeansClustering(ClusteringStrategy):
    def cluster(
        self,
        deliveries: List[Delivery],
        vehicles: List[Vehicle],
        depot_origin: np.array
    ) -> Dict[int, List[Delivery]]:
        print("  -> Usando Estratégia de Clusterização: CK-Means")
        
        delivery_map = {i: d for i, d in enumerate(deliveries)}
        print(deliveries)
        points = np.array([[d.point.lat, d.point.lng] for d in deliveries])
        weights = np.array([d.size for d in deliveries])
        vehicle_capacity = int(np.mean([v.capacity for v in vehicles]))
        n_clusters = min(len(vehicles), len(deliveries))
        
        if n_clusters == 0: return {}
        
        assignments, _ = capacitated_kmeans(points, weights, n_clusters, vehicle_capacity)
        
        # Mapeia os clusters para os veículos disponíveis
        clusters = defaultdict(list)
        for delivery_idx, cluster_id in enumerate(assignments):
            clusters[cluster_id].append(deliveries[delivery_idx])
            
        vehicle_iterator = iter(vehicles)
        deliveries_by_vehicle = {}
        for cluster_id, deliveries_in_cluster in clusters.items():
            try:
                vehicle = next(vehicle_iterator)
                deliveries_by_vehicle[vehicle.id] = deliveries_in_cluster
            except StopIteration:
                break
        
        return deliveries_by_vehicle

class GreedyClustering(ClusteringStrategy):
    def cluster(
        self,
        deliveries: List[Delivery],
        vehicles: List[Vehicle],
        depot_origin: np.array
    ) -> Dict[int, List[Delivery]]:
        print("  -> Usando Estratégia de Clusterização: Greedy (Sequential Assignment)")
        return sequential_assignment_heuristic(deliveries, vehicles, depot_origin)


# --- ROUTES ---

from service.metaheuristics.brkga import brkga_for_routing_with_depot
from service.heuristics.greedy_routing import cheapest_insertion_heuristic

class BRKGARouting(RoutingStrategy):
    def generate_routes(
        self,
        deliveries_by_vehicle: Dict[int, List[Delivery]],
        depot_origin: np.array,
        avg_speed_kmh: int
    ) -> Dict[int, Dict[str, Any]]:
        print("  -> Usando Estratégia de Roteirização: BRKGA")
        routes_details = {}
        for vehicle_id, deliveries in deliveries_by_vehicle.items():
            if not deliveries: continue
            print(f"  -> Roteirizando para Veículo {vehicle_id} com {len(deliveries_in_cluster)} pedidos.")
            node_map = {i: d for i, d in enumerate(deliveries_in_cluster)}
            node_ids = list(node_map.keys())

            cluster_points = np.array(
                [depot_origin.tolist()] + [[d.point.lng, d.point.lat] 
                for d in deliveries_in_cluster]
            )
            distance_matrix = get_distance_matrix(cluster_points)
            time_matrix = get_time_matrix(distance_matrix, avg_speed_kmh)

            P_dt_map = {i: d.preparation_dt for i, d in node_map.items()}
            T_dt_map = {i: d.time_dt for i, d in node_map.items()}
            depot_index = len(deliveries_in_cluster)

            seq, _, asap_eval_dt = brkga_for_routing_with_depot(
                node_ids=node_ids,
                travel_time=time_matrix,
                P_dt_map=P_dt_map,
                T_dt_map=T_dt_map,
                depot_index=depot_index
            )
            asap_eval_dt["sequence"] = seq
            routes_details[vehicle_id] = ev_dt

        return routes_details
        
class GreedyRouting(RoutingStrategy):
    def generate_routes(
        self,
        deliveries_by_vehicle:
        Dict[int, List[Delivery]],
        depot_origin: np.array,
        avg_speed_kmh: int
    ) -> Dict[int, Dict[str, Any]]:
        print("  -> Usando Estratégia de Roteirização: Greedy (Cheapest Insertion)")
        routes_details = {}
        for vehicle_id, deliveries in deliveries_by_vehicle.items():
            if not deliveries: continue
            
            route_details = cheapest_insertion_heuristic(deliveries, depot_origin, avg_speed_kmh)
            routes_details[vehicle_id] = route_details
            
        return routes_details