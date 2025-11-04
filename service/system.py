from service.clustering.ckmeans import capacitated_kmeans
from service.metaheuristics.brkga import brkga_for_routing_with_depot
from service.distances import get_distance_matrix, get_time_matrix
from datetime import datetime, timedelta
from service.structures import Event
from collections import defaultdict
import numpy as np
import math
import time
import heapq

from typing import Dict
from service.structures import Delivery, Vehicle
from service.enums import OrderStatus, EventType, VehicleStatus
from service.monitor import Monitor

class System:
    def __init__(self, vehicles: list[Vehicle], depot_origin: np.array):
        self.simulation_time = None
        self.event_queue: list = []
        self.active_deliveries: Dict[str, Delivery] = {}
        self.vehicles: Dict[int, Vehicle] = {v.id: v for v in vehicles}
        self.depot_origin = depot_origin
        self.avg_speed_kmh = 50
        self.monitor = Monitor()

    def add_new_delivery(self, delivery: Delivery):
        '''Adiciona uma nova entrega e seus eventos iniciais ao sistema.'''
        self.active_deliveries[delivery.id] = delivery
        print(f'[{delivery.timestamp_dt.strftime('%H:%M')}] 🍽️ Nova Entrega Recebida: id={delivery.id}')

        # Agenda os eventos usando os campos _dt da classe Delivery
        self._schedule_event(EventType.ORDER_CREATED, delivery.timestamp_dt, delivery.id)
        self._schedule_event(EventType.ORDER_READY, delivery.preparation_dt, delivery.id)
        self._schedule_event(EventType.PICKUP_DEADLINE, delivery.time_dt, delivery.id) # time_dt é o deadline
        self.monitor.total_deliveries_created += 1

    def _schedule_event(self, event_type, timestamp, delivery_id):
        event = Event(event_type, timestamp, delivery_id)
        heapq.heappush(self.event_queue, event)
        return event

    def clustering(self):
        deliveries = [e.delivery for _, _, e in self.events if e.state in ['C', 'R', 'D']]
        points = np.array([[d.point.lng, d.point.lat] for d in deliveries])
        weights = np.array([d.size for d in deliveries])
        total_size = weights.sum()
        vehicle_capacity = 100 * 0.9  # 90% da capacidade do veiculo
        necessary_vehicles = math.ceil(total_size / vehicle_capacity)
        n_clusters = necessary_vehicles
        assign, centers = capacitated_kmeans(points, weights, n_clusters, vehicle_capacity)
        clusters = defaultdict(list)
        for idx, d in enumerate(deliveries):
            clusters[assign[idx]].append(d)
        return clusters, centers

    def add_event(self, event: Event):
        '''Adiciona um novo evento à fila de prioridade.'''
        print('- Adicionando evento', event)
        heapq.heappush(self.event_queue, (event.timestamp_dt, event.id, event))
        self.notify(event)

    def process_events_due(self):
        while self.event_queue and self.event_queue[0].timestamp <= self.simulation_time:
            event = heapq.heappop(self.event_queue)
            if event.event_type == EventType.VEHICLE_RETURN:
                vehicle = self.vehicles.get(event.delivery_id)
                if vehicle:
                    self._handle_vehicle_return(event, vehicle)
                continue # Pula para o próximo evento

            delivery = self.active_deliveries.get(event.delivery_id)

            if not delivery or delivery.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
                continue

            handler = getattr(self, f'_handle_{event.event_type.name.lower()}', None)
            if handler:
                handler(event, delivery)

     # --- Handlers de Eventos (usando 'delivery' em vez de 'order') ---

    def _handle_order_created(self, event, delivery):
        print(f'[{self.simulation_time.strftime('%H:%M')}] ➡️ Evento: Pedido {delivery.id} foi criado.')

    def _handle_order_ready(self, event, delivery):
        print(f'[{self.simulation_time.strftime('%H:%M')}] ✅ Evento: Pedido {delivery.id} está pronto (às {delivery.preparation_dt.strftime('%H:%M')})!')
        delivery.status = OrderStatus.READY


    def _handle_pickup_deadline(self, event, delivery):
        """
        Este handler é acionado quando o tempo máximo de espera de um pedido é atingido.
        Ele não altera o estado do pedido, apenas registra o alerta e atualiza o monitor.
        """
        # A verificação garante que não estamos alertando sobre um pedido que já está a caminho ou foi entregue.
        if delivery.status not in [OrderStatus.DISPATCHED, OrderStatus.DELIVERED]:
            print(f"[{self.simulation_time.strftime('%H:%M')}] ❗ ALERTA DE ATRASO: Prazo do Pedido {delivery.id} ({delivery.time_dt.strftime('%H:%M')}) foi ultrapassado!")
            if not hasattr(delivery, 'is_marked_late'):
                self.monitor.total_deliveries_late += 1
                delivery.is_marked_late = True


    def _handle_vehicle_return(self, event, vehicle):
        print(f"[{self.simulation_time.strftime('%H:%M')}] 🚐 Evento: Veículo {vehicle.id} retornou ao depósito.")
        vehicle.status = VehicleStatus.IDLE
        vehicle.current_route = []
        vehicle.route_end_time = None

    def _handle_expected_delivery(self, event, delivery):
        # Removemos a lógica de liberar o veículo daqui, pois agora é um evento separado.
        print(f"[{self.simulation_time.strftime('%H:%M')}] ✅ ENTREGA: Pedido {delivery.id} entregue.")
        delivery.status = OrderStatus.DELIVERED
        self.monitor.total_deliveries_completed += 1

    def routing_decision_logic(self):
        """
        Orquestra a clusterização e roteirização para pedidos prontos.
        É chamado periodicamente pelo loop de simulação.
        """
        # 1. GATHER DATA: Coletar pedidos e veículos elegíveis
        ready_deliveries = [d for d in self.active_deliveries.values() if d.status == OrderStatus.READY]
        available_vehicles = [v for v in self.vehicles.values() if v.status == VehicleStatus.IDLE]

        if not ready_deliveries or not available_vehicles:
            return # Nada a fazer

        print(f"[{self.simulation_time.strftime('%H:%M')}] 🧠 Lógica de Roteamento: {len(ready_deliveries)} pedidos prontos e {len(available_vehicles)} veículos disponíveis.")

        # 2. PREPARE INPUTS para a otimização
        # Mapeia ID do Delivery para um índice numérico (0, 1, 2...)
        delivery_map = {i: d for i, d in enumerate(ready_deliveries)}
        id_map = {d.id: i for i, d in delivery_map.items()}

        points = np.array([[d.point.lng, d.point.lat] for d in ready_deliveries])

        weights = np.array([d.size for d in ready_deliveries])

        # A capacidade pode ser a média ou um valor fixo
        vehicle_capacity = int(np.mean([v.capacity for v in available_vehicles]))

        # 3. STAGE 1: CLUSTERING (K-Means com Capacidade)
        n_clusters = len(available_vehicles)

        # O K-Means precisa de pelo menos tantos pontos quanto clusters
        if len(ready_deliveries) < n_clusters:
            n_clusters = len(ready_deliveries)

        if n_clusters == 0: return

        assignments, _ = capacitated_kmeans(points, weights, n_clusters, vehicle_capacity)

        # Agrupa os pedidos por cluster
        clusters = defaultdict(list)
        for delivery_idx, cluster_id in enumerate(assignments):
            clusters[cluster_id].append(delivery_map[delivery_idx])

        print(f"  -> Clusterização encontrou {len(clusters)} grupos de entrega.")

        # 4. STAGE 2: ROUTING (BRKGA para cada cluster)
        vehicles_to_dispatch = iter(available_vehicles) # Iterador para pegar veículos

        for cluster_id, deliveries_in_cluster in clusters.items():
            try:
                vehicle = next(vehicles_to_dispatch)
            except StopIteration:
                break # Acabaram os veículos disponíveis

            if not deliveries_in_cluster: continue

            print(f"  -> Roteirizando Cluster {cluster_id} para Veículo {vehicle.id} com {len(deliveries_in_cluster)} pedidos.")

            # Preparar inputs para o BRKGA
            # Mapeia os deliveries do cluster para índices locais (0, 1, ...)
            node_map = {i: d for i, d in enumerate(deliveries_in_cluster)}
            node_ids = list(node_map.keys())

            cluster_points = np.array([self.depot_origin] + [[d.point.lng, d.point.lat] for d in deliveries_in_cluster])
            distance_matrix = get_distance_matrix(cluster_points)
            time_matrix = get_time_matrix(distance_matrix, self.avg_speed_kmh)

            P_dt_map = {i: d.preparation_dt for i, d in node_map.items()}
            T_dt_map = {i: d.time_dt for i, d in node_map.items()}

            # O depósito é o último índice na matriz de tempo
            depot_index = len(deliveries_in_cluster)

            # Chamar o BRKGA
            seq, _, ev_dt = brkga_for_routing_with_depot(
                node_ids=node_ids,
                travel_time=time_matrix,
                P_dt_map=P_dt_map,
                T_dt_map=T_dt_map,
                depot_index=depot_index
            )

            # 5. UPDATE STATE: Aplicar os resultados da otimização ao sistema
            print(f"  -> Rota definida para Veículo {vehicle.id}: Início às {ev_dt['start_datetime'].strftime('%H:%M')}, Retorno às {ev_dt['return_depot'].strftime('%H:%M')}")

            self.monitor.total_penalty_incurred += ev_dt["total_penalty"]
            self.monitor.total_route_time_minutes += ev_dt["total_route_time"]

            print(f"  -> Rota definida. Penalidade da rota: {ev_dt['total_penalty']}. Tempo da rota: {ev_dt['total_route_time']:.2f} min.")

            # Atualizar o veículo
            vehicle.status = VehicleStatus.ON_ROUTE
            vehicle.route_end_time = ev_dt['return_depot']
            vehicle.current_route = [node_map[node_idx].id for node_idx in seq]

            return_event = Event(EventType.VEHICLE_RETURN, vehicle.route_end_time, vehicle.id)
            heapq.heappush(self.event_queue, return_event)

            print(f"  -> Veículo {vehicle.id} retornará às {vehicle.route_end_time.strftime('%H:%M')}. Evento agendado.")

            # Atualizar cada pedido na rota
            for node_idx in seq:
                delivery = node_map[node_idx]
                expected_delivery_time = ev_dt['arrivals_map'][node_idx]

                delivery.status = OrderStatus.DISPATCHED
                delivery.assigned_vehicle_id = vehicle.id

                # A MÁGICA ACONTECE AQUI: Agendamos o evento de entrega para o futuro
                self._schedule_event(EventType.EXPECTED_DELIVERY, expected_delivery_time, delivery.id)

                print(f"    - Pedido {delivery.id} despachado. Entrega esperada: {expected_delivery_time.strftime('%H:%M')}")

    def run_simulation(self, start_time, end_time, incoming_deliveries_schedule):
        self.simulation_time = start_time
        print(f'--- Iniciando Simulação em {start_time} ---')

        while self.simulation_time <= end_time:
            print(f'\n--- Relógio: {self.simulation_time.strftime('%Y-%m-%d %H:%M')} ---')
            if self.simulation_time in incoming_deliveries_schedule:
                for delivery in incoming_deliveries_schedule[self.simulation_time]:
                    self.add_new_delivery(delivery)
            if self.simulation_time.minute % 30 == 0: # A cada 30 minutos
                self.monitor.display()
            self.process_events_due()
            self.routing_decision_logic()

            # --- LOGS DE DEBURAÇÃO ---
            ready_count = sum(1 for d in self.active_deliveries.values() if d.status == OrderStatus.READY)
            dispatched_count = sum(1 for d in self.active_deliveries.values() if d.status == OrderStatus.DISPATCHED)
            idle_vehicles = sum(1 for v in self.vehicles.values() if v.status == VehicleStatus.IDLE)

            print(f"[{self.simulation_time.strftime('%H:%M')}] Status: "
                f"Ready={ready_count}, Dispatched={dispatched_count}, "
                f"Idle Vehicles={idle_vehicles}")

            self.simulation_time += timedelta(minutes=1)
        print('\n--- Simulação Concluída ---')
        self.monitor.display()

        return self.monitor