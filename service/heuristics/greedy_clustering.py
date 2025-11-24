from collections import defaultdict
from typing import List, Dict
import numpy as np

from service.structures import Delivery, Vehicle
from service.distances import euclidean_matrix

def sequential_assignment_heuristic(
    deliveries: List[Delivery],
    vehicles: List[Vehicle],
    depot_origin: np.array
) -> Dict[int, List[Delivery]]:
    """
    Implementa uma heurística de atribuição sequencial (gulosa) para clusterizar entregas.

    A lógica é a seguinte:
    1. Ordena as entregas pela distância decrescente em relação ao depósito.
    2. Itera sobre cada entrega ordenada.
    3. Atribui a entrega ao primeiro veículo na lista que tem capacidade restante suficiente.
    4. Se nenhuma entrega puder ser atribuída, ela é ignorada nesta rodada.

    Retorna um dicionário mapeando o ID do veículo para a lista de entregas atribuídas.
    """
    if not deliveries or not vehicles:
        return {}

    # Calcula a distância de cada entrega ao depósito
    delivery_points = np.array([[d.point.lat, d.point.lng] for d in deliveries])
    distances_to_depot = euclidean_matrix(delivery_points, np.array([depot_origin]))[:, 0]

    # Ordena as entregas pela distância decrescente do depósito
    sorted_deliveries = sorted(zip(deliveries, distances_to_depot), key=lambda x: x[1], reverse=True)

    # Inicializa o controle de capacidade e o resultado
    remaining_capacities = {v.id: v.capacity for v in vehicles}
    assignments = defaultdict(list)

    for delivery, _ in sorted_deliveries:
        for vehicle in vehicles:
            if remaining_capacities[vehicle.id] >= delivery.size:
                assignments[vehicle.id].append(delivery)
                remaining_capacities[vehicle.id] -= delivery.size
                break  # Passa para a próxima entrega

    return dict(assignments)