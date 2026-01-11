from typing import List, Dict, Any
import numpy as np
from datetime import timedelta
from copy import deepcopy

from service.structures import Delivery, Vehicle, Point
from service.strategies import HybridStrategy
from service.distances import get_distance_matrix, get_time_matrix
from service.helpers import (
    evaluate_sequence,
    datetimes_map_to_minutes,
    minutes_to_datetime
)

def manual_delivery_assignment(
    deliveries: List[Delivery],
    vehicles: List[Vehicle],
    time_matrix: np.ndarray,
    delivery_indices: Dict[str, int],
    depot_idx: int = 0,
    max_travel_time: float = 8.0, # Equivalente a ~4km a 30km/h
    stop_penalty_min: float = 2.0
) -> Dict[int, List[Delivery]]:
    """
    Agrupa entregas para veículos com base em uma heurística manual simples.
    Opera com base em tempo de viagem, não mais em distância.
    Retorna um dicionário mapeando ID do veículo para uma lista de entregas.
    """
    
    # 1️⃣ Enriquecer entregas com tempo de viagem do depósito e folga (slack)
    enriched_deliveries = []
    for d in deliveries:
        delivery_idx = delivery_indices[d.id]
        # O tempo de viagem é do depósito (índice 0) para a entrega
        travel_time = time_matrix[depot_idx, delivery_idx]
        slack = d.time - travel_time

        enriched_deliveries.append({
            "delivery": d,
            "travel_time": travel_time,
            "slack": slack
        })

    # 2️⃣ Ordenar por urgência (menor slack primeiro)
    enriched_deliveries.sort(key=lambda x: x["slack"])

    # 3️⃣ Agrupar rotas e alocar aos veículos
    assignments = {v.id: [] for v in vehicles}
    vehicles_sorted = sorted(vehicles, key=lambda v: v.capacity, reverse=True)
    
    assigned_deliveries = set()

    for vehicle in vehicles_sorted:
        for current_enriched in enriched_deliveries:
            if current_enriched["delivery"].id in assigned_deliveries:
                continue

            route = [current_enriched["delivery"]]
            assigned_deliveries.add(current_enriched["delivery"].id)

            # Tenta agrupar mais pedidos na mesma rota
            for candidate_enriched in enriched_deliveries:
                if len(route) >= vehicle.capacity:
                    break
                if candidate_enriched["delivery"].id in assigned_deliveries:
                    continue

                # Regra de agrupamento por tempo de viagem do depósito
                if candidate_enriched["travel_time"] <= max_travel_time:
                    route.append(candidate_enriched["delivery"])
                    assigned_deliveries.add(candidate_enriched["delivery"].id)
            
            assignments[vehicle.id].extend(route)
            # Se um veículo é totalmente preenchido, podemos parar de alocar para ele
            if len(assignments[vehicle.id]) >= vehicle.capacity:
                break
    
    return assignments


class ManualAssignmentStrategy(HybridStrategy):
    def generate_solution(
        self,
        deliveries: List[Delivery],
        vehicles: List[Vehicle],
        depot_origin: np.array,
        avg_speed_kmh: int
    ) -> Dict[int, Dict[str, Any]]:
        print("  -> Usando Estratégia Híbrida: Manual Assignment (com Penalidades)")

        if not deliveries or not vehicles:
            return {}

        depot_point = Point(lng=depot_origin[0], lat=depot_origin[1])
        
        # --- 1. Preparar Matrizes Globais e Mapeamentos ---
        all_points = [depot_point] + [d.point for d in deliveries]
        all_points_np = np.array([[p.lat, p.lng] for p in all_points])
        
        # Mapeamento do ID da entrega para seu índice na matriz (offset por 1 devido ao depósito)
        delivery_to_matrix_idx = {d.id: i + 1 for i, d in enumerate(deliveries)}
        matrix_idx_to_delivery = {i + 1: d for i, d in enumerate(deliveries)}

        dist_matrix_km = get_distance_matrix(all_points_np, metric='haversine')
        time_matrix_min = get_time_matrix(dist_matrix_km, avg_speed_kmh)

        # --- 2. Agrupar entregas por veículo ---
        assignments = manual_delivery_assignment(
            deliveries,
            vehicles,
            time_matrix_min,
            delivery_to_matrix_idx,
            depot_idx=0
        )

        # --- 3. Avaliar cada rota e calcular resultados detalhados ---
        solution = {}
        for vehicle_id, deliveries_for_vehicle in assignments.items():
            if not deliveries_for_vehicle:
                continue

            # --- a. Preparar dados para evaluate_sequence ---
            # O `seq` para evaluate_sequence deve ser o índice da entrega na lista original de `deliveries`,
            # não o índice da matriz global.
            delivery_map = {i: d for i, d in enumerate(deliveries_for_vehicle)}
            node_ids = list(delivery_map.keys())

            # Criar matriz de tempo apenas para os nós desta rota
            route_matrix_indices = [0] + [delivery_to_matrix_idx[d.id] for d in deliveries_for_vehicle]
            route_time_matrix = time_matrix_min[np.ix_(route_matrix_indices, route_matrix_indices)]
            
            # Converter datetimes para minutos relativos
            P_dt_map = {i: d.preparation_dt for i, d in delivery_map.items()}
            T_dt_map = {i: d.time_dt for i, d in delivery_map.items()}
            P_min, T_min, ref_ts = datetimes_map_to_minutes(P_dt_map, T_dt_map)
            
            # --- b. Chamar evaluate_sequence ---
            # A sequência aqui é simples, por ordem de agrupamento.
            # O depot_index para esta sub-matriz é 0.
            ev_min = evaluate_sequence(
                seq=node_ids,
                travel_time=route_time_matrix,
                P_min=P_min,
                T_min=T_min,
                depot_index=0
            )

            # --- c. Converter resultados para datetimes e formato final ---
            start_datetime = minutes_to_datetime(ev_min["start_time"], ref_ts)
            return_time = start_datetime + timedelta(minutes=ev_min["total_route_time"])
            
            arrivals_map = {
                node: minutes_to_datetime(ev_min["arrival_times"][i], ref_ts)
                for i, node in enumerate(node_ids)
            }
            penalties_map = {
                node: ev_min["penalties"][i]
                for i, node in enumerate(node_ids)
            }

            ev_with_dt = deepcopy(ev_min)
            ev_with_dt.update({
                "sequence": node_ids,
                "node_map": delivery_map,
                "arrival_datetimes": list(arrivals_map.values()),
                "start_datetime": start_datetime,
                "arrivals_map": arrivals_map,
                "penalties_map": penalties_map,
                "ref_timestamp_seconds": ref_ts,
                "return_depot": return_time,
            })
            
            solution[vehicle_id] = ev_with_dt
            
        return solution
