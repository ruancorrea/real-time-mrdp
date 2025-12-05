from collections import defaultdict
from typing import List, Dict, Any
import numpy as np

from service.strategies import HybridStrategy
from service.structures import Delivery, Vehicle
from service.distances import get_distance_matrix, get_time_matrix
from service.helpers import datetimes_map_to_minutes, evaluate_sequence, minutes_to_datetime

class GreedyHybridStrategy(HybridStrategy):
    """
    Estratégia híbrida que constrói a solução de forma gulosa,
    inserindo um pedido por vez na melhor posição possível.
    """

    def generate_solution(
        self,
        deliveries: List[Delivery],
        vehicles: List[Vehicle],
        depot_origin: np.array,
        avg_speed_kmh: int
    ) -> Dict[int, Dict[str, Any]]:
        """
        Gera uma solução completa (atribuição e roteirização) usando uma
        heurística de inserção gulosa.
        """
        if not deliveries or not vehicles:
            return {}

        # 1. Prepara os dados
        delivery_map = {d.id: d for d in deliveries}
        delivery_ids = list(delivery_map.keys())
        
        all_points = np.array(
            [depot_origin.tolist()] + [[d.point.lng, d.point.lat] for d in deliveries]
        )
        
        # Mapeia IDs de entrega para índices na matriz de distância/tempo
        id_to_idx = {d_id: i + 1 for i, d_id in enumerate(delivery_ids)}
        idx_to_id = {i + 1: d_id for i, d_id in enumerate(delivery_ids)}
        depot_idx = 0

        distance_matrix = get_distance_matrix(all_points)
        time_matrix = get_time_matrix(distance_matrix, avg_speed_kmh)

        # Converte datetimes para minutos
        p_dt_map = {id_to_idx[d.id]: d.preparation_dt for d in deliveries}
        t_dt_map = {id_to_idx[d.id]: d.time_dt for d in deliveries}
        p_min, t_min, ref_ts = datetimes_map_to_minutes(p_dt_map, t_dt_map)

        # 2. Inicializa a solução
        routes = {v.id: [] for v in vehicles}
        remaining_capacities = {v.id: v.capacity for v in vehicles}
        unassigned_deliveries = set(delivery_ids)

        # 3. Loop de inserção gulosa
        while unassigned_deliveries:
            best_insertion = None
            min_cost_increase = float('inf')

            # Para cada pedido não alocado
            for delivery_id in unassigned_deliveries:
                delivery = delivery_map[delivery_id]
                delivery_idx = id_to_idx[delivery_id]

                # Para cada veículo
                for vehicle in vehicles:
                    if remaining_capacities[vehicle.id] < delivery.size:
                        continue

                    current_route_indices = [id_to_idx[d_id] for d_id in routes[vehicle.id]]
                    
                    # Custo da rota atual (pode ser 0 se vazia)
                    original_cost = 0
                    if current_route_indices:
                        eval_res = evaluate_sequence(current_route_indices, time_matrix, p_min, t_min, depot_index=depot_idx)
                        original_cost = eval_res["total_penalty"] # Foco na penalidade

                    # Testa a inserção em cada posição possível
                    for i in range(len(current_route_indices) + 1):
                        temp_route = current_route_indices[:i] + [delivery_idx] + current_route_indices[i:]
                        
                        eval_res = evaluate_sequence(temp_route, time_matrix, p_min, t_min, depot_index=depot_idx)
                        new_cost = eval_res["total_penalty"]
                        
                        cost_increase = new_cost - original_cost

                        if cost_increase < min_cost_increase:
                            min_cost_increase = cost_increase
                            best_insertion = (vehicle.id, i, delivery_id)
            
            # 4. Aplica a melhor inserção encontrada
            if best_insertion:
                vehicle_id, position, delivery_id = best_insertion
                
                routes[vehicle_id].insert(position, delivery_id)
                remaining_capacities[vehicle_id] -= delivery_map[delivery_id].size
                unassigned_deliveries.remove(delivery_id)
            else:
                # Não há mais inserções possíveis (ex: capacidade)
                print(f"Não foi possível alocar {len(unassigned_deliveries)} pedidos.")
                break

        # 5. Formata a solução final
        solution = {}
        for vehicle_id, route_ids in routes.items():
            if not route_ids:
                continue

            route_indices = [id_to_idx[d_id] for d_id in route_ids]
            final_eval = evaluate_sequence(route_indices, time_matrix, p_min, t_min, depot_index=depot_idx)

            # Constrói o dicionário de resultados completo, similar ao BRKGA
            from datetime import timedelta
            from copy import deepcopy

            arrival_datetimes = [minutes_to_datetime(t, ref_ts) for t in final_eval["arrival_times"]]
            start_datetime = minutes_to_datetime(final_eval["start_time"], ref_ts)
            
            arrivals_map = {node_idx: arrival_datetimes[i] for i, node_idx in enumerate(route_indices)}
            penalties_map = {node_idx: final_eval["penalties"][i] for i, node_idx in enumerate(route_indices)}
            return_time = start_datetime + timedelta(minutes=final_eval["total_route_time"])

            # O node_map para esta rota específica
            node_map = {idx: delivery_map[idx_to_id[idx]] for idx in route_indices}

            # Monta o dicionário final para este veículo
            vehicle_solution = deepcopy(final_eval)
            vehicle_solution.update({
                "sequence": route_indices,
                "node_map": node_map,
                "deliveries": [delivery_map[d_id] for d_id in route_ids],
                "arrival_datetimes": arrival_datetimes,
                "start_datetime": start_datetime,
                "arrivals_map": arrivals_map,
                "penalties_map": penalties_map,
                "ref_timestamp_seconds": ref_ts,
                "return_depot": return_time,
            })
            solution[vehicle_id] = vehicle_solution

        return solution