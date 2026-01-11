from typing import List, Dict, Any
import numpy as np
import random
from copy import deepcopy
from datetime import timedelta

from service.structures import Delivery, Vehicle, Point
from service.distances import get_distance_matrix, get_time_matrix
from service.helpers import datetimes_map_to_minutes, evaluate_sequence, minutes_to_datetime

def decode_chromosome_to_solution(
    chromosome: List[float],
    deliveries: List[Delivery],
    vehicles: List[Vehicle],
    depot_origin: np.array,
    avg_speed_kmh: int
) -> Dict[str, Any]:
    """
    Decodes a chromosome by sorting deliveries based on gene values and then
    greedily inserting them into the best possible route position across all vehicles.
    """
    num_deliveries = len(deliveries)
    
    # Sort deliveries based on chromosome priority values
    indexed_deliveries = list(enumerate(deliveries))
    sorted_indexed_deliveries = sorted(indexed_deliveries, key=lambda x: chromosome[x[0]])
    
    # Prepare data for evaluation
    delivery_map = {d.id: d for d in deliveries}
    id_to_idx = {d.id: i + 1 for i, d in enumerate(deliveries)}
    time_matrix = get_time_matrix(get_distance_matrix(np.array([depot_origin.tolist()] + [[d.point.lng, d.point.lat] for d in deliveries])), avg_speed_kmh)
    p_dt_map = {id_to_idx[d.id]: d.preparation_dt for d in deliveries}
    t_dt_map = {id_to_idx[d.id]: d.time_dt for d in deliveries}
    p_min, t_min, _ = datetimes_map_to_minutes(p_dt_map, t_dt_map)
    
    routes = {v.id: [] for v in vehicles}
    route_costs = {v.id: 0 for v in vehicles}
    remaining_capacities = {v.id: v.capacity for v in vehicles}
    unassigned_penalty = 0
    
    for _, delivery in sorted_indexed_deliveries:
        best_insertion = {
            "vehicle_id": None,
            "position": -1,
            "cost_increase": float('inf'),
        }
        delivery_idx = id_to_idx[delivery.id]

        # Find the best insertion place across all vehicles and all route positions
        for vehicle in vehicles:
            if remaining_capacities[vehicle.id] < delivery.size:
                continue

            current_route_ids = routes[vehicle.id]
            current_route_indices = [id_to_idx[d_id] for d_id in current_route_ids]
            original_cost = route_costs[vehicle.id]

            for i in range(len(current_route_indices) + 1):
                temp_route = current_route_indices[:i] + [delivery_idx] + current_route_indices[i:]
                eval_res = evaluate_sequence(temp_route, time_matrix, p_min, t_min, depot_index=0)
                new_cost = eval_res["total_penalty"] * 1000 + eval_res["total_route_time"]
                cost_increase = new_cost - original_cost

                if cost_increase < best_insertion["cost_increase"]:
                    best_insertion["vehicle_id"] = vehicle.id
                    best_insertion["position"] = i
                    best_insertion["cost_increase"] = cost_increase
        
        # Perform the insertion
        if best_insertion["vehicle_id"]:
            v_id = best_insertion["vehicle_id"]
            pos = best_insertion["position"]
            routes[v_id].insert(pos, delivery.id)
            remaining_capacities[v_id] -= delivery.size

            # Recalculate and store the new cost for the updated route
            updated_route_indices = [id_to_idx[d_id] for d_id in routes[v_id]]
            final_eval = evaluate_sequence(updated_route_indices, time_matrix, p_min, t_min, depot_index=0)
            route_costs[v_id] = final_eval["total_penalty"] * 1000 + final_eval["total_route_time"]
        else:
            unassigned_penalty += 100000  # Penalize unassigned deliveries

    # Calculate final fitness
    total_penalty = unassigned_penalty
    total_route_time = 0
    for vehicle_id, route_ids in routes.items():
        if route_ids:
            route_indices = [id_to_idx[d_id] for d_id in route_ids]
            final_eval = evaluate_sequence(route_indices, time_matrix, p_min, t_min, depot_index=0)
            total_penalty += final_eval["total_penalty"]
            total_route_time += final_eval["total_route_time"]
    
    return {"total_penalty": total_penalty, "total_route_time": total_route_time, "routes": routes}


def apply_hybrid_brkga(
    deliveries: List[Delivery],
    vehicles: List[Vehicle],
    depot_origin: np.array,
    avg_speed_kmh: int,
    pop_size=50, elite_frac=0.3, mutant_frac=0.15, bias=0.7,
    max_gens=70, no_improve_limit=15
) -> Dict[int, Dict[str, Any]]:
    if not deliveries or not vehicles: return {}

    num_deliveries = len(deliveries)
    chromosome_size = num_deliveries  # Chromosome encodes priorities for deliveries
    population = [[random.random() for _ in range(chromosome_size)] for _ in range(pop_size)]
    
    best_fitness_ever = (float('inf'), float('inf'))
    best_chrom_ever = None
    no_improve_count = 0

    for gen in range(max_gens):
        fitness_results = []
        for chrom in population:
            decoded = decode_chromosome_to_solution(chrom, deliveries, vehicles, depot_origin, avg_speed_kmh)
            fitness = (decoded["total_penalty"], decoded["total_route_time"])
            fitness_results.append((fitness, chrom))

        population_sorted = sorted(fitness_results, key=lambda x: x[0])
        
        current_best_fitness, current_best_chrom = population_sorted[0]
        
        if current_best_fitness < best_fitness_ever:
            best_fitness_ever = current_best_fitness
            best_chrom_ever = current_best_chrom
            no_improve_count = 0
            print(f"Gen {gen}: New best -> Penalty: {best_fitness_ever[0]:.2f}, Time: {best_fitness_ever[1]:.2f}")
        else:
            no_improve_count += 1
        
        if no_improve_count >= no_improve_limit:
            print(f"Stopping early at gen {gen} due to no improvement.")
            break

        # Generate new population
        elite_size = max(1, int(pop_size * elite_frac))
        mutant_size = max(1, int(pop_size * mutant_frac))
        
        next_population = [item[1] for item in population_sorted[:elite_size]]
        
        non_elites = [item[1] for item in population_sorted[elite_size:]]
        
        while len(next_population) < pop_size - mutant_size:
            parent_e = random.choice(next_population) # Crossover from the new elite pool
            parent_o = random.choice(non_elites)
            child = [p_e if random.random() < bias else p_o for p_e, p_o in zip(parent_e, parent_o)]
            next_population.append(child)
            
        while len(next_population) < pop_size:
            next_population.append([random.random() for _ in range(chromosome_size)])
        
        population = next_population

    if best_chrom_ever is None: return {}
        
    return format_final_solution(best_chrom_ever, deliveries, vehicles, depot_origin, avg_speed_kmh)


def format_final_solution(
    chromosome: List[float],
    deliveries: List[Delivery],
    vehicles: List[Vehicle],
    depot_origin: np.array,
    avg_speed_kmh: int
) -> Dict[int, Dict[str, Any]]:
    # Re-run decode on the best chromosome to get the final routes
    decoded = decode_chromosome_to_solution(chromosome, deliveries, vehicles, depot_origin, avg_speed_kmh)
    routes = decoded.get("routes", {})

    solution = {}
    delivery_map = {d.id: d for d in deliveries}
    id_to_idx = {d.id: i + 1 for i, d in enumerate(deliveries)}
    idx_to_id = {i + 1: d.id for i, d in enumerate(deliveries)}
    
    # Create node_map
    node_map = {idx: delivery_map[d_id] for idx, d_id in idx_to_id.items()}
    depot_point = Point(lng=depot_origin[0], lat=depot_origin[1])
    # Create a dummy Delivery object for the depot
    depot_dummy = Delivery(
        id='depot',
        point=depot_point,
        size=0,
        preparation=0,
        time=0,
        timestamp=0
    )
    node_map[0] = depot_dummy
    
    all_points = np.array([depot_origin.tolist()] + [[d.point.lng, d.point.lat] for d in deliveries])
    time_matrix = get_time_matrix(get_distance_matrix(all_points), avg_speed_kmh)
    p_dt_map = {id_to_idx[d.id]: d.preparation_dt for d in deliveries}
    t_dt_map = {id_to_idx[d.id]: d.time_dt for d in deliveries}
    p_min, t_min, ref_ts = datetimes_map_to_minutes(p_dt_map, t_dt_map)
    
    for v in vehicles:
        route_ids = routes.get(v.id)
        if not route_ids: continue

        route_indices = [id_to_idx[d_id] for d_id in route_ids]
        final_eval = evaluate_sequence(route_indices, time_matrix, p_min, t_min, depot_index=0)
        
        arrival_datetimes = [minutes_to_datetime(t, ref_ts) for t in final_eval["arrival_times"]]
        start_datetime = minutes_to_datetime(final_eval["start_time"], ref_ts)
        arrivals_map = {node_idx: arrival_datetimes[i] for i, node_idx in enumerate(route_indices)}
        penalties_map = {node_idx: final_eval["penalties"][i] for i, node_idx in enumerate(route_indices)}
        return_time = start_datetime + timedelta(minutes=final_eval["total_route_time"])

        vehicle_solution = deepcopy(final_eval)
        vehicle_solution.update({
            "sequence": route_indices,
            "deliveries": [delivery_map[d_id] for d_id in route_ids],
            "arrival_datetimes": arrival_datetimes,
            "start_datetime": start_datetime,
            "arrivals_map": arrivals_map,
            "penalties_map": penalties_map,
            "ref_timestamp_seconds": ref_ts,
            "return_depot": return_time,
            "node_map": node_map,
        })
        solution[v.id] = vehicle_solution
        
    print("DEBUG: Final solution from format_final_solution:", solution)
    return solution