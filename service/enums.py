from enum import Enum, auto

class OrderStatus(Enum):
    PENDING = auto()
    READY = auto()
    DISPATCHED = auto()
    DELIVERED = auto()
    CANCELLED = auto()
    #FAILED = auto()

class EventType(Enum):
    ORDER_CREATED = auto()
    ORDER_READY = auto()
    PICKUP_DEADLINE = auto()
    EXPECTED_DELIVERY = auto()
    VEHICLE_RETURN = auto()

class VehicleStatus(Enum):
    IDLE = auto()      # Disponível no depósito
    ON_ROUTE = auto()  # Executando uma rota