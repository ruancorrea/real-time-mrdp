from datetime import timedelta
from collections import defaultdict

from service.system import System
import numpy as np
import instances as Instances
from service.structures import Vehicle
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Para Python < 3.9, você pode precisar de um polyfill como 'backports.zoneinfo'
    # ou usar a biblioteca 'pytz'
    ZoneInfo = None
# Importe suas classes System, Vehicle, Delivery...

# Defina o fuso horário que será usado em toda a simulação
# Deve ser o mesmo usado no seu módulo de rotas
SIMULATION_TZ_NAME = "America/Sao_Paulo"
if ZoneInfo:
    SIMULATION_TZ = ZoneInfo(SIMULATION_TZ_NAME)
else:
    # Fallback para UTC se zoneinfo não estiver disponível
    from datetime import timezone
    SIMULATION_TZ = timezone.utc
    print("Aviso: zoneinfo não encontrado. Usando UTC como fuso horário.")

if __name__ == "__main__":
    path_eval = './data/dev'
    path_train = './data/train'
    data_base: str = '01/01/2025'
    hours: int = 18
    minutes: int = 0
    instances = Instances.get_instances(path_eval)
    all_deliveries_by_time = Instances.process_instances(instances[:1], data_base, hours, minutes, tzinfo=SIMULATION_TZ)
    origin = np.array([-35.739118, -9.618276])

    simulation_start_time = Instances.get_initial_time(data_base, hours, minutes, tzinfo=SIMULATION_TZ)
    simulation_end_time = simulation_start_time + timedelta(hours=1)
    simulation_time = simulation_start_time

    print(f"Iniciando simulação de {simulation_start_time} até {simulation_end_time}")
    delivery_for_time = Instances.get_delivery_for_time(all_deliveries_by_time[0])

    vehicles = [
        Vehicle(id=1, capacity=90),
        Vehicle(id=2, capacity=90),
    ]

    incoming_deliveries_schedule = defaultdict(list)

    for delivery in all_deliveries_by_time[0]:
       if delivery.timestamp_dt > simulation_end_time:
            break
       incoming_deliveries_schedule[delivery.timestamp_dt].append(delivery)

    # --- Execução ---
    system = System(vehicles=vehicles, depot_origin=origin)
    # O loop de simulação continua o mesmo! Apenas a fonte dos dados mudou.
    final_monitor_results = system.run_simulation(simulation_start_time, simulation_end_time, incoming_deliveries_schedule)

    print("\n================== RELATÓRIO FINAL DA SIMULAÇÃO ==================")
    # A exibição final já é feita dentro de run_simulation, mas podemos fazer de novo
    # ou usar os dados para gerar gráficos, salvar em um arquivo, etc.
    final_monitor_results.display()

    avg_penalty = final_monitor_results.get_average_penalty_per_delivery()
    print(f"Análise: A penalidade média de {avg_penalty:.2f} por entrega indica o nível de serviço.")
    if avg_penalty > 50:
        print("Sugestão: A penalidade média é alta. Considere adicionar mais veículos ou otimizar os parâmetros.")
    else:
        print("Resultado: O nível de serviço parece aceitável.")
    print("==================================================================")
