from service.clustering.ckmeans import capacitated_kmeans
from service.metaheuristics.brkga import brkga_for_routing_with_depot
from service.distances import get_distance_matrix, get_time_matrix
from datetime import datetime, timedelta
from service.structures import Event
from collections import defaultdict
import numpy as np

import time
import heapq

from typing import Dict
from service.structures import Delivery, Vehicle
from service.enums import OrderStatus, EventType, VehicleStatus
from service.monitor import Monitor
from service.config import (
    SimulationConfig,
    ClusteringAlgorithm,
    RoutingAlgorithm,
    HybridAlgorithm
)
from service.factory import get_strategies

class System:
    def __init__(
        self,
        config: SimulationConfig,
        vehicles: list[Vehicle],
        depot_origin: np.array,
        dispatch_delay_buffer_minutes: int = 5
    ):
        self.simulation_time = None
        self.event_queue: list = []
        self.active_deliveries: Dict[str, Delivery] = {}
        self.vehicles: Dict[int, Vehicle] = {v.id: v for v in vehicles}
        self.depot_origin = depot_origin
        self.avg_speed_kmh = 50
        self.dispatch_delay_buffer = timedelta(minutes=dispatch_delay_buffer_minutes)
        self.monitor = Monitor()
        self.config = config
        self.clustering_strategy, self.routing_strategy, self.hybrid_strategy = get_strategies(config)


    def add_new_delivery(self, delivery: Delivery):
        """
        Adds a new delivery to the system and schedules its corresponding events.
        The routing logic is NOT triggered here.
        """
        self.active_deliveries[delivery.id] = delivery
        print(f'[{delivery.timestamp_dt.strftime("%H:%M")}] New Delivery Received: id={delivery.id}')

        # Schedule events using the _dt fields from the Delivery class
        self._schedule_event(EventType.ORDER_CREATED, delivery.timestamp_dt, delivery.id)
        self._schedule_event(EventType.ORDER_READY, delivery.preparation_dt, delivery.id)
        self._schedule_event(EventType.PICKUP_DEADLINE, delivery.time_dt, delivery.id) # time_dt is the deadline
        self.monitor.total_deliveries_created += 1

    def _schedule_event(self, event_type, timestamp, delivery_id):
        event = Event(event_type, timestamp, delivery_id)
        heapq.heappush(self.event_queue, event)
        return event

    def process_events_due(self):
        processed_events = []
        while self.event_queue and self.event_queue[0].timestamp <= self.simulation_time:
            event = heapq.heappop(self.event_queue)
            if event.event_type == EventType.VEHICLE_RETURN:
                vehicle = self.vehicles.get(event.delivery_id)
                if vehicle:
                    return_event = self._handle_vehicle_return(event, vehicle)
                    processed_events.append(return_event)
                continue # Pula para o próximo evento

            delivery = self.active_deliveries.get(event.delivery_id)

            if not delivery or delivery.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
                continue

            handler = getattr(self, f'_handle_{event.event_type.name.lower()}', None)
            if handler:
                processed_event = handler(event, delivery)
                if processed_event:
                    processed_events.append(processed_event)
        return processed_events

     # --- Handlers de Eventos (usando 'delivery' em vez de 'order') ---

    def _handle_order_created(self, event, delivery):
        print(f'[{self.simulation_time.strftime('%H:%M')}] Evento: Pedido {delivery.id} foi criado.')


    def _handle_order_ready(self, event, delivery):
        print(f'[{self.simulation_time.strftime('%H:%M')}] Evento: Pedido {delivery.id} está pronto (às {delivery.preparation_dt.strftime('%H:%M')})!')
        delivery.status = OrderStatus.READY


    def _handle_pickup_deadline(self, event, delivery):
        '''
        Este handler é acionado quando o tempo máximo de espera de um pedido é atingido.
        Ele não altera o estado do pedido, apenas registra o alerta e atualiza o monitor.
        '''
        # A verificação garante que não estamos alertando sobre um pedido que já está a caminho ou foi entregue.
        if delivery.status not in [OrderStatus.DISPATCHED, OrderStatus.DELIVERED]:
            print(f"[{self.simulation_time.strftime('%H:%M')}] ALERTA DE ATRASO: Prazo do Pedido {delivery.id} ({delivery.time_dt.strftime('%H:%M')}) foi ultrapassado!")
            if not hasattr(delivery, 'is_marked_late'):
                self.monitor.total_deliveries_late += 1
                delivery.is_marked_late = True


    def _handle_vehicle_return(self, event, vehicle):
        print(f"[{self.simulation_time.strftime('%H:%M')}] Evento: Veículo {vehicle.id} retornou ao depósito.")
        vehicle.status = VehicleStatus.IDLE
        vehicle.current_route = []
        vehicle.route_end_time = None
        
        return {
            "type": "driver_returned",
            "data": {
                "vehicle_id": vehicle.id,
                "return_time": self.simulation_time.isoformat()
            }
        }

    def _handle_expected_delivery(self, event, delivery):
        # Removemos a lógica de liberar o veículo daqui, pois agora é um evento separado.
        print(f"[{self.simulation_time.strftime('%H:%M')}] ENTREGA: Pedido {delivery.id} entregue.")
        delivery.status = OrderStatus.DELIVERED
        self.monitor.total_deliveries_completed += 1
        return {
            "type": "delivery_completed",
            "data": {
                "delivery_id": delivery.id,
                "completion_time": self.simulation_time.isoformat(),
                "delivery": delivery.to_dict()
            }
        }


    def _calculate_delayed_dispatch(self, asap_eval_dt: dict, node_map: dict, slack_usage_ratio: float = 0.5):
        '''
        Calcula um novo horário de despacho atrasado (JIT) com base na folga da rota.

        Args:
            asap_eval_dt (dict): O dicionário de resultados do BRKGA com tempos ASAP.
            node_map (dict): Mapeamento de índice de nó para objeto Delivery.

        Returns:
            dict: Um novo dicionário de resultados com todos os tempos ajustados para o futuro.
        '''
        asap_start_time = asap_eval_dt["start_datetime"]
        route_sequence = asap_eval_dt["sequence"] # Supondo que a sequência está no dict

        # Encontrar a folga mínima (slack) na rota inteira
        min_slack = timedelta(days=999) # Começa com um valor muito grande

        for i, node_idx in enumerate(route_sequence):
            delivery = node_map[node_idx]
            deadline = delivery.time_dt

            # Tempo de chegada no modo ASAP
            asap_arrival_time = asap_eval_dt["arrivals_map"][node_idx]

            # A folga para este pedido é a diferença entre o prazo e a chegada
            current_slack = deadline - asap_arrival_time

            if current_slack < min_slack:
                min_slack = current_slack

        # A folga máxima que podemos usar é a menor folga da rota, menos nosso buffer de segurança
        usable_delay = (min_slack - self.dispatch_delay_buffer) * slack_usage_ratio

        # Não podemos ter um atraso negativo
        if usable_delay < timedelta(seconds=0):
            usable_delay = timedelta(seconds=0)

        # Se há um atraso útil, criamos um novo dicionário de resultados com tempos atualizados
        if usable_delay > timedelta(seconds=0):
            print(f"  -> Política JIT: Atrasando a rota em {usable_delay} para aumentar a chance de consolidação.")

            new_eval_dt = asap_eval_dt.copy()
            new_eval_dt["start_datetime"] = asap_start_time + usable_delay
            new_eval_dt["return_depot"] = asap_eval_dt["return_depot"] + usable_delay

            new_arrivals_map = {}
            for node_idx, arrival_dt in asap_eval_dt["arrivals_map"].items():
                new_arrivals_map[node_idx] = arrival_dt + usable_delay
            new_eval_dt["arrivals_map"] = new_arrivals_map

            return new_eval_dt
        else:
            print("-> Política JIT: Nenhuma folga útil encontrada. Despachando ASAP.")
            return asap_eval_dt

    def routing_decision_logic(self):
        '''
        Orquestra a clusterização e roteirização para pedidos prontos.
        Delega a lógica para as estratégias configuradas.
        '''
        # All datetime operations should use timezone-aware objects.
        # If simulation_time is present, it's already aware (from API or dev script).
        # If not, we default to the current time in UTC.
        current_time = self.simulation_time or datetime.now(timezone.utc)

        # 1. GATHER DATA: Coletar pedidos e veículos elegíveis
        eligible_deliveries = [
            d for d in self.active_deliveries.values() 
            if d.status in [OrderStatus.READY, OrderStatus.PENDING]
        ]
        available_vehicles = [v for v in self.vehicles.values() if v.status == VehicleStatus.IDLE]
        dispatched_events = []

        if not eligible_deliveries or not available_vehicles:
            return dispatched_events

        urgent_orders = [
            d for d in eligible_deliveries
            if d.time_dt - current_time < timedelta(minutes=10) # Ex: prazo em menos de 15 min
        ]

        use_jit_policy = True
        if len(eligible_deliveries) > 5 or len(urgent_orders) > 0:
            print(f"[{current_time.strftime('%H:%M')}] MODO DE URGÊNCIA ATIVADO. Despachando ASAP.")
            use_jit_policy = False

        print(f"[{current_time.strftime('%H:%M')}] Lógica de Roteamento: {len(eligible_deliveries)} pedidos prontos e {len(available_vehicles)} veículos disponíveis.")

        asap_routes_details = {}
        deliveries_by_vehicle = {}

        if self.hybrid_strategy:
            # Abordagem Híbrida (Etapa Única)
            asap_routes_details = self.hybrid_strategy.generate_solution(
                eligible_deliveries, available_vehicles, self.depot_origin, self.avg_speed_kmh
            )
            # Para a lógica JIT, precisamos reconstruir o 'deliveries_by_vehicle'
            # a partir dos resultados da rota.
            # (Esta parte pode precisar de ajuste dependendo do retorno do seu algoritmo híbrido)

        elif self.clustering_strategy and self.routing_strategy:
            # Abordagem de Duas Etapas
            # 2. STAGE 1: CLUSTERING
            deliveries_by_vehicle = self.clustering_strategy.cluster(
                eligible_deliveries, available_vehicles, self.depot_origin
            )
            # 3. STAGE 2: ROUTING
            asap_routes_details = self.routing_strategy.generate_routes(
                deliveries_by_vehicle, self.depot_origin, self.avg_speed_kmh
            )

        # 4. PROCESS RESULTS & UPDATE STATE (Permanece no System)
        for vehicle_id, asap_eval_dt in asap_routes_details.items():
            if not asap_eval_dt: continue

            vehicle = self.vehicles[vehicle_id]
            # O mapa de nós e a sequência devem vir do resultado da roteirização
            node_map = asap_eval_dt["node_map"]
            seq = asap_eval_dt["sequence"]

            if use_jit_policy:
                jit_eval_dt = self._calculate_delayed_dispatch(asap_eval_dt, node_map)
            else:
                jit_eval_dt = asap_eval_dt

            # 5. UPDATE STATE: Aplicar os resultados da otimização ao sistema
            #print(f"  -> Rota definida para Veículo {vehicle.id}: Início às {ev_dt['start_datetime'].strftime('%H:%M')}, Retorno às {ev_dt['return_depot'].strftime('%H:%M')}")
            print(f"  -> Rota JIT definida para Veículo {vehicle.id}: Saída às {jit_eval_dt['start_datetime'].strftime('%H:%M')}, Retorno às {jit_eval_dt['return_depot'].strftime('%H:%M')}")

            self.monitor.total_penalty_incurred += jit_eval_dt["total_penalty"]
            self.monitor.total_route_time_minutes += jit_eval_dt["total_route_time"]

            print(f"  -> Rota definida. Penalidade da rota: {jit_eval_dt['total_penalty']}. Tempo da rota: {jit_eval_dt['total_route_time']:.2f} min.")

            # Atualizar o veículo
            vehicle.status = VehicleStatus.ON_ROUTE
            vehicle.route_end_time = jit_eval_dt['return_depot']
            vehicle.current_route = [node_map[node_idx].id for node_idx in seq]
            dispatched_events.append({
                "vehicle_id": vehicle.id,
                "route": [node_map[node_idx].to_dict() for node_idx in seq],
                "dispatch_time": jit_eval_dt['start_datetime'].isoformat(),
                "return_time": jit_eval_dt['return_depot'].isoformat(),
            })

            return_event = Event(EventType.VEHICLE_RETURN, vehicle.route_end_time, vehicle.id)
            heapq.heappush(self.event_queue, return_event)

            print(f"  -> Veículo {vehicle.id} retornará às {vehicle.route_end_time.strftime('%H:%M')}. Evento agendado.")

            # Atualizar cada pedido na rota
            for node_idx in seq:
                delivery = node_map[node_idx]
                expected_delivery_time = jit_eval_dt['arrivals_map'][node_idx]

                delivery.status = OrderStatus.DISPATCHED
                delivery.assigned_vehicle_id = vehicle.id

                self._schedule_event(EventType.EXPECTED_DELIVERY, expected_delivery_time, delivery.id)

                print(f"    - Pedido {delivery.id} despachado. Entrega esperada: {expected_delivery_time.strftime('%H:%M')}")
        return dispatched_events

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