from dataclasses import dataclass, asdict, field
from typing import (
    List,
    Union,
    Optional,
)
from dacite import from_dict
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from service.enums import OrderStatus, EventType, VehicleStatus

class JSONDataclassMixin:
    '''Mixin for adding JSON file capabilities to Python dataclasses.'''

    @classmethod
    def from_file(cls, path: Union[Path, str]) -> '''JSONDataclassMixin''':
        '''Load dataclass instance from provided file path.'''

        with open(path) as f:
            data = json.load(f)

        return from_dict(cls, data)

    def to_file(self, path: Union[Path, str]) -> None:
        '''Save dataclass instance to provided file path.'''

        with open(path, 'w') as f:
            json.dump(asdict(self), f)

        return


@dataclass(unsafe_hash=True)
class Point:
    '''Point in earth. Assumes a geodesical projection.'''

    lng: float
    '''Longitude (x axis).'''

    lat: float
    '''Latitude (y axis).'''


@dataclass(unsafe_hash=True)
class Delivery:
    '''A delivery request.'''

    id: str
    point: Point
    size: int
    preparation: int
    time: int
    timestamp: int

    timestamp_dt: Optional[datetime] = None
    preparation_dt: Optional[datetime] = None
    time_dt: Optional[datetime] = None

    status: OrderStatus = field(default=OrderStatus.PENDING, compare=False, hash=False)
    dispatch_event_id: Optional[int] = field(default=None, compare=False, hash=False)
    assigned_vehicle_id: Optional[int] = field(default=None, compare=False, hash=False)

    def __post_init__(self):
        '''Calcula os campos datetime se eles não forem fornecidos.'''
        if self.timestamp_dt is None and self.timestamp is not None:
            # Create a UTC-aware datetime from the Unix timestamp
            self.timestamp_dt = datetime.fromtimestamp(self.timestamp, tz=timezone.utc)

        # Lógica crucial: calcular os datetimes a partir das durações
        if self.timestamp_dt and self.preparation_dt is None:
            self.preparation_dt = self.timestamp_dt + timedelta(minutes=self.preparation)

        if self.preparation_dt and self.time_dt is None:
            # 'time' representa o tempo limite APÓS o pedido ficar pronto
            self.time_dt = self.preparation_dt + timedelta(minutes=self.time)

    def to_dict(self):
        """Converts the delivery object to a dictionary, handling datetimes."""
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat() if value else None
            elif isinstance(value, Point):
                data[key] = asdict(value)
            elif isinstance(value, OrderStatus):
                data[key] = value.value
        return data

@dataclass
class CVRPInstance(JSONDataclassMixin):
    name: str
    '''Unique name of this instance.'''

    region: str
    '''Region name.'''

    origin: Point
    '''Location of the origin hub.'''

    vehicle_capacity: int
    '''Maximum sum of sizes per vehicle allowed in the solution.'''

    deliveries: List[Delivery]
    '''List of deliveries to be solved.'''


@dataclass
class CVRPSolutionVehicle:

    origin: Point
    '''Location of the origin hub.'''

    deliveries: List[Delivery]
    '''Ordered list of deliveries from the vehicle.'''

    @property
    def circuit(self) -> List[Point]:
        return (
            [self.origin] + [d.point for d in self.deliveries]
        )

    @property
    def occupation(self) -> int:
        return sum([d.size for d in self.deliveries])


@dataclass
class CVRPSolution(JSONDataclassMixin):
    name: str
    vehicles: List[CVRPSolutionVehicle]

    @property
    def deliveries(self):
        return [d for v in self.vehicles for d in v.deliveries]


@dataclass
class Vehicle:
    id: int
    capacity: int
    status: VehicleStatus = VehicleStatus.IDLE
    current_route: list = field(default_factory=list) # Lista de IDs de Delivery
    route_end_time: Optional[datetime] = None # Quando o veículo volta a ficar IDLE

_event_counter = 0
def get_next_event_id():
    global _event_counter; _event_counter += 1; return _event_counter

class Event:
    def __init__(self, event_type: EventType, timestamp: datetime, delivery_id: str):
        self.id = get_next_event_id()
        self.event_type = event_type
        self.timestamp = timestamp
        self.delivery_id = delivery_id
    def __lt__(self, other): return self.timestamp < other.timestamp
    def __repr__(self): return f"Event(id={self.id}, type={self.event_type.name}, delivery_id={self.delivery_id}, time={self.timestamp.strftime('%H:%M')})"