import random
from datetime import datetime
from service.structures import Delivery, Point
from service.system import System
from time import time

# Em um arquivo de serviço real (ex: service.py)

def fetch_new_orders_from_api():
    """
    Função MOCK que simula a busca de novos pedidos em uma API externa.
    Em um sistema real, isso faria uma requisição HTTP a um endpoint.
    """
    # Simula a chance de um novo pedido chegar
    if random.random() < 0.1: # 10% de chance de novo pedido a cada chamada
        now = datetime.now()
        new_delivery = Delivery(
            id=f'LIVE-{int(now.timestamp())}',
            point=Point(-23.5, -46.6), size=1,
            preparation=15, time=20,
            timestamp=int(now.timestamp()),
            timestamp_dt=now
        )
        print(f"***** Novo pedido recebido da API: {new_delivery.id} *****")
        return [new_delivery]
    return []


if __name__ == "__main__":
    print("--- Iniciando Serviço de Despacho em Tempo Real ---")
    system = System()

    # ATENÇÃO: Em produção, o estado (active_deliveries) não pode ficar só em memória.
    # Ele seria carregado de um banco de dados (como Redis ou PostgreSQL) no início
    # e salvo a cada mudança.

    # O loop principal de um serviço em tempo real
    try:
        while True:
            # 1. Definir o "agora" usando o relógio real
            current_real_time = datetime.now()
            system.simulation_time = current_real_time # A classe System usa essa variável

            # 2. Buscar novos pedidos de fontes externas
            new_deliveries = fetch_new_orders_from_api()
            for delivery in new_deliveries:
                system.add_new_delivery(delivery)

            # 3. Processar eventos agendados que já venceram
            # (Ex: um pedido que acabou de ficar 'READY')
            system.process_events_due()

            # 4. Executar a lógica de decisão de roteamento
            # (Ex: encontrar um entregador para um pedido 'READY')
            system.routing_decision_logic()

            # Imprimir o estado atual para depuração
            print(f"[{current_real_time.strftime('%H:%M:%S')}] Checando... "
                  f"{len(system.active_deliveries)} entregas ativas, "
                  f"{len(system.event_queue)} eventos na fila.")

            # 5. Pausar por um curto período antes do próximo ciclo
            time.sleep(5) # O sistema "pensa" a cada 5 segundos

    except KeyboardInterrupt:
        print("\n--- Serviço encerrado pelo usuário ---")