from typing import List, Dict, Any
import numpy as np
from datetime import timedelta

from service.structures import Delivery
from service.distances import get_distance_matrix, get_time_matrix
from service.helpers import (
    evaluate_sequence,
    minutes_to_datetime,
    datetimes_map_to_minutes
)

def cheapest_insertion_heuristic(
    deliveries: List[Delivery],
    depot_origin: np.array,
    avg_speed_kmh: int
) -> Dict[str, Any]:
    """
    Implementa a heurística de Inserção Mais Barata para criar uma rota para um veículo.

    A lógica é a seguinte:
    1.  Cria uma matriz de tempo de viagem entre o depósito e todas as entregas.
    2.  Inicializa a rota com a entrega mais próxima do depósito (Depósito -> Entrega -> Depósito).
    3.  Iterativamente, para cada entrega ainda não roteirizada:
        a. Encontra a posição na rota atual onde a inserção dessa entrega causa o menor aumento de tempo.
        b. O custo de inserção de um ponto 'k' entre 'i' e 'j' é: tempo(i, k) + tempo(k, j) - tempo(i, j).
    4.  Adiciona a entrega que tem o menor custo de inserção em sua melhor posição.
    5.  Repete até que todas as entregas estejam na rota.
    6.  Calcula os tempos de chegada, penalidades e outros detalhes para retornar um dicionário compatível com o sistema.

    Retorna um dicionário com os detalhes da rota.
    """
    if not deliveries:
        return {}

    # PADRÃO BRKGA: O depósito é o índice 0. As entregas são 1, 2, ..., n.
    # O node_map do System é {0: entrega_A, 1: entrega_B}.
    # Nosso node_map interno precisa ser {1: entrega_A, 2: entrega_B} para mapear para a matriz de tempo.
    node_map = {i: d for i, d in enumerate(deliveries)}
    num_deliveries = len(deliveries)
    depot_idx = 0

    # Monta os pontos e calcula as matrizes de distância e tempo
    # Depósito no índice 0, entregas nos índices 1 em diante.
    all_points = np.array(
        [depot_origin.tolist()] + [[d.point.lat, d.point.lng] for d in deliveries]
    )
    dist_matrix = get_distance_matrix(all_points)
    time_matrix = get_time_matrix(dist_matrix, avg_speed_kmh)

    # --- Lógica da Inserção Mais Barata ---

    # 1. Encontra a entrega mais próxima do depósito para iniciar a rota
    # Na matriz, as entregas estão nos índices 1 em diante.
    times_from_depot = time_matrix[depot_idx][1:]
    first_node_idx_in_deliveries = np.argmin(times_from_depot) # Este é o índice 0, 1, 2... da lista original

    # 2. Inicializa a rota e a lista de não visitados
    # A rota deve conter os índices da lista original de entregas (0 a n-1)
    current_route = [first_node_idx_in_deliveries]
    unvisited_nodes = list(range(num_deliveries))
    unvisited_nodes.remove(first_node_idx_in_deliveries)

    # 3. Loop principal de inserção
    while unvisited_nodes:
        best_insertion_cost = float('inf')
        best_node_to_insert = -1
        best_position = -1

        # Para cada nó não visitado, encontre o melhor lugar para inseri-lo
        for node_to_insert in unvisited_nodes:
            # node_to_insert é o índice 0..n-1. Na matriz de tempo, seu índice é node_to_insert + 1.
            matrix_idx_to_insert = node_to_insert + 1

            # Estende a rota com o depósito no início e no fim para cálculo
            # Os índices na rota precisam ser convertidos para índices da matriz (+1)
            tour_with_depot_matrix_indices = [depot_idx] + [node + 1 for node in current_route] + [depot_idx]

            for i in range(len(tour_with_depot_matrix_indices) - 1):
                u = tour_with_depot_matrix_indices[i]
                v = tour_with_depot_matrix_indices[i+1]

                # Custo de inserção: tempo(u, k) + tempo(k, v) - tempo(u, v)
                cost = time_matrix[u][matrix_idx_to_insert] + time_matrix[matrix_idx_to_insert][v] - time_matrix[u][v]

                if cost < best_insertion_cost:
                    best_insertion_cost = cost
                    best_node_to_insert = node_to_insert
                    best_position = i + 1 # Posição na rota *sem* o depósito

        # Insere o melhor nó na melhor posição
        current_route.insert(best_position, best_node_to_insert)
        unvisited_nodes.remove(best_node_to_insert)

    # --- Formatação da Saída para o Sistema ---

    try:
        # Prepara os dados para a função de avaliação (a mesma usada pelo BRKGA)
        # P_min e T_min devem ser indexados por 0..n-1, que é o que o node_map faz.
        P_dt_map = {i: d.preparation_dt for i, d in node_map.items()}
        T_dt_map = {i: d.time_dt for i, d in node_map.items()}
        P_min, T_min, ref_ts = datetimes_map_to_minutes(P_dt_map, T_dt_map)

        # A função evaluate_sequence espera que os índices da rota (current_route)
        # correspondam aos índices de P_min e T_min (0..n-1).
        # No entanto, ela usa o depot_index para acessar a time_matrix, que agora está correta.
        eval_result = evaluate_sequence(current_route, time_matrix, P_min, T_min, depot_index=depot_idx)

        # Converte os tempos em minutos de volta para datetimes
        start_datetime = minutes_to_datetime(eval_result["start_time"], ref_ts)
        return_datetime = start_datetime + timedelta(minutes=eval_result["total_route_time"])
        arrival_datetimes = [minutes_to_datetime(t, ref_ts) for t in eval_result["arrival_times"]]
        arrivals_map = {node: arrival_datetimes[i] for i, node in enumerate(current_route)}

        # Monta o dicionário de retorno final
        route_details = {
            "sequence": current_route,
            "total_penalty": eval_result["total_penalty"],
            "total_route_time": eval_result["total_route_time"],
            "start_datetime": start_datetime,
            "return_depot": return_datetime,
            "arrivals_map": arrivals_map,
        }
        return route_details
    except Exception as e:
        print(f"  -> ERRO na heurística de inserção: Não foi possível gerar rota. Detalhes: {e}")
        return {}