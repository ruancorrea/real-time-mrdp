from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Any

from service.structures import Delivery, CVRPInstance

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

def get_data_base(data_base: str | datetime, tzinfo: Any = None) -> datetime:
    OPTIONS = ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S']

    if isinstance(data_base, str):
        for p in OPTIONS:
          try:
            data_base = datetime.strptime(data_base, p)
            if tzinfo:
                data_base = data_base.replace(tzinfo=tzinfo)
            break
          except:
            pass
    return data_base

def process_deliveries(delivery: Delivery, data_base: datetime):
    timestamp_dt = data_base + timedelta(minutes=delivery.timestamp)
    new_delivery = Delivery(
        id=delivery.id,
        point=delivery.point,
        size=delivery.size,
        preparation=delivery.preparation,
        time=delivery.time,
        timestamp=delivery.timestamp,
        timestamp_dt=timestamp_dt,
    )

    return new_delivery

def process_instances(
    instances: list,
    data_base: str = '01/01/2025',
    hours: int =18,
    minutes: int =0,
    tzinfo: Any = None,
  ) -> list:
    days = []
    data_base = f'{data_base} {hours}:{str(minutes).zfill(2)}:00'
    data_base = get_data_base(data_base, tzinfo)
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

def get_initial_time(data_base: str = '01/01/2025', hours: int =18, minutes: int =0, tzinfo: Any = None):

    data_base = f'{data_base} {hours}:{str(minutes).zfill(2)}:00'
    data_base = get_data_base(data_base, tzinfo)
    return data_base