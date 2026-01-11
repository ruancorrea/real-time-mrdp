import csv
import time
from datetime import timedelta
from collections import defaultdict

from service.system import System
import numpy as np
import instances as Instances
from service.structures import Vehicle
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from service.config import SimulationConfig, ClusteringAlgorithm, RoutingAlgorithm, HybridAlgorithm

SIMULATION_TZ_NAME = "America/Sao_Paulo"
if ZoneInfo:
    SIMULATION_TZ = ZoneInfo(SIMULATION_TZ_NAME)
else:
    from datetime import timezone
    SIMULATION_TZ = timezone.utc
    print("Aviso: zoneinfo não encontrado. Usando UTC como fuso horário.")

def run_test(instance_number, strategy_name, config):
    path_eval = './data/dev'
    data_base: str = '01/01/2025'
    hours: int = 18
    minutes: int = 0
    
    instances_data = Instances.get_instances(path_eval, number_instance=instance_number)
    all_deliveries_by_time = Instances.process_instances(instances_data[:1], data_base, hours, minutes, tzinfo=SIMULATION_TZ)
    origin = np.array([-35.739118, -9.618276])

    simulation_start_time = Instances.get_initial_time(data_base, hours, minutes, tzinfo=SIMULATION_TZ)
    simulation_end_time = simulation_start_time + timedelta(hours=9)

    vehicles = [
        Vehicle(id=1, capacity=50),
        Vehicle(id=2, capacity=50),
        Vehicle(id=2, capacity=50),
        Vehicle(id=2, capacity=50),
    ]

    incoming_deliveries_schedule = defaultdict(list)
    for delivery in all_deliveries_by_time[0]:
       if delivery.timestamp_dt > simulation_end_time:
            break
       incoming_deliveries_schedule[delivery.timestamp_dt].append(delivery)

    system = System(
        vehicles=vehicles,
        depot_origin=origin,
        config=config
    )
    
    start_time = time.time()
    final_monitor_results = system.run_simulation(simulation_start_time, simulation_end_time + timedelta(hours=5), incoming_deliveries_schedule)
    end_time = time.time()
    
    execution_time = end_time - start_time
    avg_penalty = final_monitor_results.get_average_penalty_per_delivery()
    
    print(f"Instance: {instance_number}, Strategy: {strategy_name}, Avg Penalty: {avg_penalty:.2f}, Execution Time: {execution_time:.2f}s")
    
    return {
        'instance': instance_number,
        'strategy': strategy_name,
        'avg_penalty': f"{avg_penalty:.2f}",
        'execution_time': f"{execution_time:.4f}"
    }

if __name__ == "__main__":
    strategies_to_test = {
        "greedy_clustering+greedy_routing": SimulationConfig(
            clustering_algo=ClusteringAlgorithm.GREEDY,
            routing_algo=RoutingAlgorithm.GREEDY
        ),
        "greedy_clustering+brkga": SimulationConfig(
            clustering_algo=ClusteringAlgorithm.GREEDY,
            routing_algo=RoutingAlgorithm.BRKGA
        ),
        "ckmeans+greedy_routing": SimulationConfig(
            clustering_algo=ClusteringAlgorithm.CKMEANS,
            routing_algo=RoutingAlgorithm.GREEDY
        ),
        "ckmeans+brkga": SimulationConfig(
            clustering_algo=ClusteringAlgorithm.CKMEANS,
            routing_algo=RoutingAlgorithm.BRKGA
        ),
        "brkga_hybrid": SimulationConfig(hybrid_algo=HybridAlgorithm.BRKGA_HYBRID),
        "greedy_hybrid": SimulationConfig(hybrid_algo=HybridAlgorithm.GREEDY_INSERTION),
    }

    all_results = []
    for i in range(7):  # For each instance from 0 to 6
        for strategy_name, config in strategies_to_test.items():
            result = run_test(i, strategy_name, config)
            all_results.append(result)

    with open('results_test.csv', 'w', newline='') as csvfile:
        fieldnames = ['instance', 'strategy', 'avg_penalty', 'execution_time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    print("\nTestes concluídos. Resultados salvos em results_test.csv")
