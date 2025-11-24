# brkga_routing_with_datetimes.py
import random
import math
import numpy as np
from copy import deepcopy
from service.distances import get_distance_matrix, get_time_matrix
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

from service.helpers import (
    datetimes_map_to_minutes,
    minutes_to_datetime,
    evaluate_sequence
)

# ---------------------------
# Helpers para datetimes
# ---------------------------
DEFAULT_TZ_NAME = "America/Sao_Paulo"  # ajuste se quiser outra timezone

def to_timestamp_seconds(dt, assume_tz_name=DEFAULT_TZ_NAME):
    """Converte datetime -> timestamp (float seconds since epoch).
       Se dt.tzinfo é None (naive), assume assume_tz_name zona e converte para UTC timestamp.
       Retorna float segundos.
    """
    if dt is None:
        raise ValueError("datetime é None")
    if dt.tzinfo is not None:
        return dt.timestamp()
    # naive datetime: assume local zone provided
    if ZoneInfo is None:
        # fallback: assume naive datetimes are UTC (safer que crash)
        # mas preferível instalar Python >=3.9 ou usar pytz
        return dt.replace(tzinfo=timezone.utc).timestamp()
    else:
        local_tz = ZoneInfo(assume_tz_name)
        dt_loc = dt.replace(tzinfo=local_tz)
        return dt_loc.timestamp()

# ---------------------------
# Funções de avaliação (em minutos)
# ---------------------------
def compute_penalty_from_arrival(arrival, T, min=5.0, penalty_per_min=100):
    lateness = max(0.0, arrival - T)
    if lateness <= 0:
        return 0
    blocks = math.ceil(lateness / min)
    return int(blocks * penalty_per_min)

# ---------------------------
# Decodificador e LS (mesma lógica do exemplo)
# ---------------------------
def decode_keys_to_sequence(keys, node_ids):
    pairs = list(zip(keys, node_ids))
    pairs.sort(key=lambda x: x[0])
    seq = [p[1] for p in pairs]
    return seq

def two_opt(seq, evaluate_func):
    best_seq = seq
    best_eval = evaluate_func(seq)
    improved = True
    while improved:
        improved = False
        n = len(best_seq)
        for i in range(0, n-2):
            for j in range(i+2, n):
                if i==0 and j==n-1:
                    continue
                new_seq = best_seq[:i+1] + list(reversed(best_seq[i+1:j+1])) + best_seq[j+1:]
                new_eval = evaluate_func(new_seq)
                if (new_eval["total_penalty"] < best_eval["total_penalty"]) or \
                   (new_eval["total_penalty"] == best_eval["total_penalty"] and new_eval["total_route_time"] < best_eval["total_route_time"]):
                    best_seq = new_seq
                    best_eval = new_eval
                    improved = True
                    break
            if improved:
                break
    return best_seq, best_eval

def relocate(seq, evaluate_func):
    best_seq = seq
    best_eval = evaluate_func(seq)
    n = len(seq)
    improved = True
    while improved:
        improved = False
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                new_seq = best_seq.copy()
                node = new_seq.pop(i)
                new_seq.insert(j, node)
                new_eval = evaluate_func(new_seq)
                if (new_eval["total_penalty"] < best_eval["total_penalty"]) or \
                   (new_eval["total_penalty"] == best_eval["total_penalty"] and new_eval["total_route_time"] < best_eval["total_route_time"]):
                    best_seq = new_seq
                    best_eval = new_eval
                    improved = True
                    break
            if improved:
                break
    return best_seq, best_eval

def or_opt(seq, k, evaluate_func):
    n = len(seq)
    best_seq = seq
    best_eval = evaluate_func(seq)
    improved = True
    while improved:
        improved = False
        for block_size in range(1, k+1):
            for i in range(0, n - block_size + 1):
                block = best_seq[i:i+block_size]
                remainder = best_seq[:i] + best_seq[i+block_size:]
                for j in range(len(remainder)+1):
                    if j == i:
                        continue
                    new_seq = remainder[:j] + block + remainder[j:]
                    new_eval = evaluate_func(new_seq)
                    if (new_eval["total_penalty"] < best_eval["total_penalty"]) or \
                       (new_eval["total_penalty"] == best_eval["total_penalty"] and new_eval["total_route_time"] < best_eval["total_route_time"]):
                        best_seq = new_seq
                        best_eval = new_eval
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
    return best_seq, best_eval

# ---------------------------
# BRKGA principal (usa P_min e T_min)
# ---------------------------
def brkga_for_routing_with_depot(node_ids, travel_time,
                                 P_dt_map, T_dt_map,
                                 service_times=None, depot_index=None,
                                 assume_tz_name=DEFAULT_TZ_NAME,
                                 pop_size=60, elite_frac=0.2, mutant_frac=0.1, bias=0.7,
                                 max_gens=200, no_improve_limit=40):
    # convert datetimes to minutes
    P_min, T_min, ref_ts = datetimes_map_to_minutes(P_dt_map, T_dt_map, assume_tz_name=assume_tz_name)
    n = len(node_ids)
    def eval_keys(keys):
        seq = decode_keys_to_sequence(keys, node_ids)
        return evaluate_sequence(seq, travel_time, P_min, T_min, service_times, depot_index)
    # init population
    pop = [[random.random() for _ in range(n)] for _ in range(pop_size)]
    def fitness_of(keys):
        ev = eval_keys(keys)
        return ev["total_penalty"], ev["total_route_time"], ev
    pop.sort(key=lambda k: fitness_of(k)[:2])
    best_keys = pop[0]
    best_eval = fitness_of(best_keys)[2]
    elite_size = max(1, int(pop_size * elite_frac))
    mutant_size = max(1, int(pop_size * mutant_frac))
    no_improve = 0
    for gen in range(max_gens):
        pop_sorted = sorted(pop, key=lambda k: fitness_of(k)[:2])
        elites = pop_sorted[:elite_size]
        non_elites = pop_sorted[elite_size:]
        nxt = []
        nxt.extend(elites)
        while len(nxt) < pop_size - mutant_size:
            parent_e = random.choice(elites)
            parent_o = random.choice(non_elites) if non_elites else [random.random() for _ in range(n)]
            child = []
            for i in range(n):
                if random.random() < bias:
                    child.append(parent_e[i])
                else:
                    child.append(parent_o[i])
            nxt.append(child)
        for _ in range(mutant_size):
            nxt.append([random.random() for _ in range(n)])
        pop = nxt
        pop.sort(key=lambda k: fitness_of(k)[:2])
        current_best_keys = pop[0]
        current_best_eval = fitness_of(current_best_keys)[2]
        if (current_best_eval["total_penalty"] < best_eval["total_penalty"]) or \
           (current_best_eval["total_penalty"] == best_eval["total_penalty"] and current_best_eval["total_route_time"] < best_eval["total_route_time"]):
            best_keys = current_best_keys
            best_eval = current_best_eval
            no_improve = 0
        else:
            no_improve += 1
        if no_improve >= no_improve_limit:
            break
    best_seq = decode_keys_to_sequence(best_keys, node_ids)
    def eval_seq_wrapper(s):
        return evaluate_sequence(s, travel_time, P_min, T_min, service_times, depot_index)
    seq, ev = two_opt(best_seq, lambda s: eval_seq_wrapper(s))
    seq, ev = or_opt(seq, 3, lambda s: eval_seq_wrapper(s))
    seq, ev = relocate(seq, lambda s: eval_seq_wrapper(s))
    # build datetimes output: arrival datetime per order and start datetime
    arrival_datetimes = [minutes_to_datetime(x, ref_ts, assume_tz_name) for x in ev["arrival_times"]]
    start_datetime = minutes_to_datetime(ev["start_time"], ref_ts, assume_tz_name)
    # map node -> arrival datetime and penalty
    arrivals_map = {node: arrival_datetimes[i] for i, node in enumerate(seq)}
    penalties_map = {node: ev["penalties"][i] for i, node in enumerate(seq)}
    return_time = start_datetime + timedelta(minutes=ev["total_route_time"])

    # return: sequence order, ev (minutes), and ev_dt with datetimes & maps
    ev_with_dt = deepcopy(ev)
    ev_with_dt.update({
        "arrival_datetimes": arrival_datetimes,
        "start_datetime": start_datetime,
        "arrivals_map": arrivals_map,
        "penalties_map": penalties_map,
        "ref_timestamp_seconds": ref_ts,
        "return_depot": return_time,
    })
    return seq, ev, ev_with_dt

def apply(data: list, origin: np.array, average_speed_kmh: int=50):
    #points = np.array([[b.point.lat, b.point.lng] for b in data])
    points = [[b.point.lat, b.point.lng] for b in data]
    points = np.array([origin] + points)
    weights = np.array([b.size for b in data])
    #preparations = np.array([b.preparation_dt for b in data])
    preparations = {idx: b.preparation_dt for idx, b in enumerate(data)}
    #times = np.array([b.time_dt for b in data])
    times = {idx: b.time_dt for idx, b in enumerate(data)}
    distance_matrix = get_distance_matrix(points)
    travel_time = get_time_matrix(distance_matrix, average_speed_kmh=average_speed_kmh)
    n_orders = len(data) 
    depot_index = len(data)
    service_times = {i: 2 for i in range(n_orders)}
    node_ids = list(range(n_orders))
    print(origin, len(data), len(points))
    seq, ev_min, ev_dt = brkga_for_routing_with_depot(node_ids, travel_time, preparations, times,
                                                      service_times=service_times,
                                                      depot_index=depot_index,
                                                      assume_tz_name=DEFAULT_TZ_NAME,
                                                      pop_size=50, max_gens=200)
    print("Sequence order (visit order):", seq)
    print("Start datetime (route):", ev_dt["start_datetime"])
    print("Total penalty:", ev_min["total_penalty"])
    print("Total route time (min):", ev_min["total_route_time"])
    print("Expected delivery times per node (datetime):")
    for node in seq:
        print(f"  Node {node}: arrival={ev_dt['arrivals_map'][node]}, penalty={ev_dt['penalties_map'][node]}")


# ---------------------------
# Exemplo de uso com datetimes
# ---------------------------
if __name__ == "__main__":
    # exemplo com 5 pedidos + depot (depot index 5)
    from datetime import datetime, timedelta
    if ZoneInfo:
        tz = ZoneInfo(DEFAULT_TZ_NAME)
    else:
        tz = timezone.utc
    base_dt = datetime(2025, 10, 13, 8, 0, tzinfo=tz)
    # pedidos indices 0..4
    P_dt = {
        0: base_dt + timedelta(minutes=10),
        1: base_dt + timedelta(minutes=5),
        2: base_dt + timedelta(minutes=12),
        3: base_dt + timedelta(minutes=8),
        4: base_dt + timedelta(minutes=15),
    }
    T_dt = {
        0: base_dt + timedelta(minutes=40),
        1: base_dt + timedelta(minutes=25),
        2: base_dt + timedelta(minutes=30),
        3: base_dt + timedelta(minutes=20),
        4: base_dt + timedelta(minutes=50),
    }
    # travel_time matrix must include depot row/col.
    # let's make nodes 0..4 as orders, index 5 is depot
    n_orders = 5
    depot_index = 5
    total_nodes = n_orders + 1
    rng = np.random.RandomState(2)
    mat = rng.randint(2, 15, size=(total_nodes, total_nodes)).astype(float)
    for i in range(total_nodes):
        mat[i,i] = 0
        for j in range(i+1, total_nodes):
            mat[j,i] = mat[i,j]
    travel_time = mat.tolist()
    service_times = {i: 2 for i in range(n_orders)}
    node_ids = list(range(n_orders))  # only orders
    seq, ev_min, ev_dt = brkga_for_routing_with_depot(node_ids, travel_time, P_dt, T_dt,
                                                     service_times=service_times,
                                                     depot_index=depot_index,
                                                     assume_tz_name=DEFAULT_TZ_NAME,
                                                     pop_size=60, max_gens=200)
    print("Sequence order (visit order):", seq)
    print("Start datetime (route):", ev_dt["start_datetime"])
    print("Total penalty:", ev_min["total_penalty"])
    print("Total route time (min):", ev_min["total_route_time"])
    print("Return to depot (arrival):", ev_dt["return_depot"])
    print("Expected delivery times per node (datetime):")
    for node in seq:
        print(f"  Node {node}: arrival={ev_dt['arrivals_map'][node]}, penalty={ev_dt['penalties_map'][node]}")
