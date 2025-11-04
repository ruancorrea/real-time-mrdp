from service.clustering.ckmeans import capacitated_kmeans
from datetime import datetime, timedelta
from service.structures import Event
from collections import defaultdict
import numpy as np
import math
import time
import heapq

class System:
    def __init__(self):
        self.event_queue: list = []
        self.deliveries: defaultdict = defaultdict(list)

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

    def run(self, now_func: None):

        if now_func is None:
            now_func = datetime.utcnow

        while True:
            events_process = []
            now = now_func()
            while self.events and self.events[0][0] <= now:
                _, id, event = heapq.heappop(self.events)
                events_process.append(event)
                now = now + timedelta(minutes=1)

            #clusters, centers = self.clustering()
            print(f'Processando {len(events_process)} eventos em {now}')
            time.sleep(1.5)

    def notify(self, event: Event):
        print(f'Evento criado', event.delivery.id)

    def add_event(self, event: Event):
        '''Adiciona um novo evento à fila de prioridade.'''
        print('- Adicionando evento', event)
        heapq.heappush(self.event_queue, (event.timestamp_dt, event.id, event))
        self.notify(event)

    def process_events_due_at(self, current_time: datetime):
        '''Processa todos os eventos na fila cujo tempo já chegou ou passou.'''
        events_to_process = []
        # Enquanto a fila não estiver vazia E o evento no topo estiver no passado/presente
        while self.event_queue and self.event_queue[0][0] <= current_time:
            # Retira o evento com o menor timestamp
            timestamp, event_id, event = heapq.heappop(self.event_queue)
            events_to_process.append(event)

        if events_to_process:
            print(f'--- [Processando em {current_time.strftime('%H:%M')}] ---')
            print(f'  Encontrados {len(events_to_process)} eventos para processar:')
            for event in events_to_process:
                print(f'    -> Processando Evento: Pedido {event.delivery.id} criado às {event.timestamp_dt.strftime('%H:%M')}')
            # Aqui entraria a lógica de roteamento (clustering, atribuição, etc.)
            print('----------------------------------')