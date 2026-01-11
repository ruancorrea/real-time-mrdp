import math
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

DEFAULT_TZ_NAME = "America/Sao_Paulo"

def to_timestamp_seconds(dt, assume_tz_name=DEFAULT_TZ_NAME):
    if dt is None:
        raise ValueError("datetime é None")
    if dt.tzinfo is not None:
        return dt.timestamp()
    if ZoneInfo is None:
        return dt.replace(tzinfo=timezone.utc).timestamp()
    else:
        local_tz = ZoneInfo(assume_tz_name)
        dt_loc = dt.replace(tzinfo=local_tz)
        return dt_loc.timestamp()

def datetimes_map_to_minutes(P_dt_map, T_dt_map, assume_tz_name=DEFAULT_TZ_NAME):
    """
    Recebe dicionários/arrays-like de datetimes P_dt_map[node] e T_dt_map[node].
    Retorna dois dicionários com valores em minutos (float) relativos a uma referência (min timestamp).
    Também retorna a referência timestamp (segundos) usada.
    """
    # coletar todos os datetimes em timestamps (s)
    all_ts = []
    P_ts = {}
    T_ts = {}
    for k, dt in P_dt_map.items():
        ts = to_timestamp_seconds(dt, assume_tz_name=assume_tz_name)
        P_ts[k] = ts
        all_ts.append(ts)
    for k, dt in T_dt_map.items():
        ts = to_timestamp_seconds(dt, assume_tz_name=assume_tz_name)
        T_ts[k] = ts
        all_ts.append(ts)
    if not all_ts:
        raise ValueError("Nenhum datetime fornecido")
    ref_ts = min(all_ts)  # referência para zero (poderia ser min(P) ou min de todos)
    # converter para minutos relativos à ref_ts
    P_min = {k: (v - ref_ts) / 60.0 for k, v in P_ts.items()}
    T_min = {k: (v - ref_ts) / 60.0 for k, v in T_ts.items()}
    return P_min, T_min, ref_ts

def minutes_to_datetime(minutes, ref_ts, tz_name=DEFAULT_TZ_NAME):
    """
    Converts a time in minutes (relative to a reference timestamp) back to an aware datetime object.
    """
    ts = ref_ts + minutes * 60.0
    # Create an aware datetime in UTC from the timestamp first
    utc_dt = datetime.fromtimestamp(ts, tz=timezone.utc)

    # If zoneinfo is available, convert to the specific local timezone.
    if ZoneInfo:
        try:
            target_tz = ZoneInfo(tz_name)
            return utc_dt.astimezone(target_tz)
        except Exception:
            # Fallback to UTC if tz_name is invalid
            return utc_dt
    
    # Fallback to UTC if zoneinfo is not available (Python < 3.9)
    return utc_dt

def compute_penalty_from_arrival(arrival, T, min_block=5.0, penalty_per_block=100):
    lateness = max(0.0, arrival - T)
    if lateness <= 0:
        return 0
    blocks = math.ceil(lateness / min_block)
    return int(blocks * penalty_per_block)

def evaluate_sequence(seq, travel_time, P_min, T_min, service_times=None, depot_index=None):
    '''
    Avalia uma sequência de entregas (seq) dada uma matriz de tempos de viagem (travel_time),
    tempos de preparação mínimos (P_min) e tempos de entrega desejados (T_min).'''
    if service_times is None:
        service_times = {i: 0.0 for i in seq}
    arrival_times = []      # arrival times (minutes relative)
    penalties = []
    # start = max P of all orders in seq
    start_time = max(P_min[i] for i in seq)
    time = start_time
    # leave depot -> first
    if depot_index is not None:
        time += travel_time[depot_index][seq[0]]
    for idx, node in enumerate(seq):
        if idx > 0:
            prev = seq[idx-1]
            time += travel_time[prev][node]
        arrival = time
        arrival_times.append(arrival)
        pen = compute_penalty_from_arrival(arrival, T_min[node])
        penalties.append(pen)
        time += service_times.get(node, 0.0)
    # after last, return to depot
    if depot_index is not None:
        time += travel_time[seq[-1]][depot_index]
    total_penalty = sum(penalties)
    total_route_time = time - start_time
    return {
        "arrival_times": arrival_times,
        "penalties": penalties,
        "total_penalty": total_penalty,
        "total_route_time": total_route_time,
        "start_time": start_time
    }