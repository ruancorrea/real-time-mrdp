from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

from service.structures import Delivery, CVRPInstance, Event
from service.system import System
import numpy as np
import time
import threading


def loadingData(pathTrain):
  train_path = Path(pathTrain)
  train_path_dir = train_path if train_path.is_dir() else train_path.parent
  train_files = (
      [train_path] if train_path.is_file() else list(train_path.iterdir())
  )


  train_instances = [CVRPInstance.from_file(f) for f in train_files[:240]]

  return train_instances

def loadingPoints(instances):
  points = [
            [d.point.lng, d.point.lat]
            for instance in instances
            for d in instance.deliveries
        ]

  return points

def get_instances(path):
    paths = ["/al-0", "/al-1", "/al-2"]
    origins = []
    points = []
    instances = []
    for p in paths:
      path_config = path + p
      print(path)
      train_instances = loadingData(path_config)
      instances.append(train_instances[0])
      origins.append(train_instances[0].origin)
      #points.extend(loadingPoints(train_instances))
    #points = np.array(points)

    return instances

def get_data_base(data_base: str | datetime) -> datetime:
    OPTIONS = ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S']

    if isinstance(data_base, str):
        for p in OPTIONS:
          try:
            data_base = datetime.strptime(data_base, p)
            break
          except:
            pass
    return data_base

def process_deliveries(delivery: Delivery, data_base: datetime):

    timestamp_dt = data_base + timedelta(minutes=delivery.timestamp)
    time_dt = timestamp_dt + timedelta(minutes=delivery.time)
    preparation_dt = timestamp_dt + timedelta(minutes=delivery.preparation)
    new_delivery = Delivery(
        id=delivery.id,
        point=delivery.point,
        size=delivery.size,
        preparation=delivery.preparation,
        time=delivery.time,
        timestamp=delivery.timestamp,
        timestamp_dt=timestamp_dt,
        preparation_dt=preparation_dt,
        time_dt=time_dt
    )

    return new_delivery

def process_instances(
    instances: list,
    data_base: str = '01/01/2025',
    hours: int =18,
    minutes: int =0
  ) -> list:
    days = []
    data_base = f'{data_base} {hours}:{str(minutes).zfill(2)}:00'
    data_base = get_data_base(data_base)
    print(data_base)
    for i in instances:
        deliveries = [process_deliveries(d, data_base) for d in i.deliveries]
        deliveries = sorted(deliveries, key=lambda x: x.timestamp_dt)
        days.append(deliveries)

    return days

def get_delivery_for_time(deliveries: list):
    delivery_for_time = defaultdict(list)

    for d in deliveries:
        delivery_for_time[d.timestamp_dt].append(d)

    return delivery_for_time

def get_initial_time(data_base: str = '01/01/2025', hours: int =18, minutes: int =0):

    data_base = f'{data_base} {hours}:{str(minutes).zfill(2)}:00'
    data_base = get_data_base(data_base)
    return data_base

def update_time():
    global CURRENT_TIME
    CURRENT_TIME += timedelta(minutes=1)
    return CURRENT_TIME

if __name__ == "__main__":
    path_eval = './data/dev'
    path_train = './data/train'

    instances = get_instances(path_eval)
    data_base: str = '01/01/2025'
    hours: int = 18
    minutes: int = 0
    all_deliveries_by_time = process_instances(instances[:1], data_base, hours, minutes)
    origin = np.array([-35.739118, -9.618276])
    system = System()

    simulation_start_time = get_initial_time(data_base, hours, minutes)
    simulation_end_time = simulation_start_time + timedelta(hours=2)
    simulation_time = simulation_start_time

    print(f"Iniciando simulação de {simulation_start_time} até {simulation_end_time}")
    delivery_for_time = get_delivery_for_time(all_deliveries_by_time[0])

    while simulation_time <= simulation_end_time:
        print(f"\n** Avançando relógio para: {simulation_time.strftime('%Y-%m-%d %H:%M')} **")

        # 1. Verificação de novos pedidos (eventos externos)
        if simulation_time in delivery_for_time:
            print(f"Novos pedidos chegaram às {simulation_time.strftime('%H:%M')}")
            for id, delivery_data in enumerate(delivery_for_time[simulation_time]):
                new_event = Event(
                    id=delivery_data.id, # Usar um ID único
                    timestamp_dt=delivery_data.timestamp_dt,
                    delivery=delivery_data,
                    state='CREATED'
                )
                system.add_event(new_event)

        # 2. Processar eventos que estão na fila e já venceram
        system.process_events_due_at(simulation_time)

        # 3. Avançar o relógio da simulação
        simulation_time += timedelta(minutes=1)

        # Opcional: para desacelerar a saída no console e poder ler
        # Remova ou comente esta linha para a simulação rodar na velocidade máxima
        time.sleep(1)

    print("Simulação concluída.")


'''
STATES
C: created
R: ready
D: deadline
'''
