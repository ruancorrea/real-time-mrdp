
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from typing import List, Dict, Optional

# Imports from your existing service
from service.structures import Vehicle, Delivery, Point
from service.system import System
from service.config import SimulationConfig, ClusteringAlgorithm, RoutingAlgorithm, HybridAlgorithm
from service.enums import VehicleStatus

# --- Pydantic Models for API requests ---
from pydantic import BaseModel, Field

class PointModel(BaseModel):
    lng: float
    lat: float

class DriverModel(BaseModel):
    id: int
    capacity: int

class OrderModel(BaseModel):
    id: str
    point: PointModel
    size: int
    # Timestamps will be handled by the server
    preparation_minutes: int = Field(alias="preparation")
    deadline_minutes: int = Field(alias="time")


class SystemConfigModel(BaseModel):
    clustering_algo: Optional[ClusteringAlgorithm] = None
    routing_algo: Optional[RoutingAlgorithm] = None
    hybrid_algo: Optional[HybridAlgorithm] = None
    depot_origin: PointModel
    start_time: datetime
    end_time: datetime

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Dynamic Route Planner API",
    description="API for managing and interacting with the dynamic routing system.",
)

manager = ConnectionManager()
routing_lock = asyncio.Lock()
initialization_lock = asyncio.Lock()

# --- Global State Management ---
# This will hold the single, stateful instance of our routing system
system: Optional[System] = None
# Temporary storage for drivers before the system is initialized
drivers: List[Vehicle] = []


@app.get("/")
def read_root():
    return {"message": "Welcome to the Dynamic Route Planner API"}


# --- WebSocket Endpoint ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    print(f"Client '{client_id}' connected.")
    try:
        while True:
            # Keep the connection alive, can be extended to receive client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        print(f"Client '{client_id}' disconnected.")

# --- HTTP Endpoints ---

@app.post("/drivers", status_code=201, summary="Register a new driver/vehicle")
async def add_driver(driver_model: DriverModel):
    """
    Adds a new driver (vehicle) to the list of available drivers.
    This should be done before starting the system.
    """
    async with initialization_lock:
        if system:
            raise HTTPException(status_code=409, detail="Cannot add drivers after the system has been initialized.")
        
        # Avoid duplicate driver IDs
        if any(d.id == driver_model.id for d in drivers):
            raise HTTPException(status_code=409, detail=f"Driver with ID {driver_model.id} already exists.")
            
        vehicle = Vehicle(id=driver_model.id, capacity=driver_model.capacity)
        drivers.append(vehicle)
        return {"message": f"Driver {driver_model.id} registered successfully.", "driver": driver_model}


@app.get("/drivers", response_model=List[DriverModel], summary="List all registered drivers")
def get_drivers():
    """
    Returns a list of all drivers that have been registered.
    """
    if system:
        # If system is running, the authoritative list is in system.vehicles
        return list(system.vehicles.values())
    
    # Otherwise, return the list of drivers pending initialization
    return drivers


@app.post("/start_system", status_code=200, summary="Initialize the routing system")
async def start_system(config_model: SystemConfigModel):
    """
    Initializes and starts the main routing system with a given configuration.
    This can only be done once.
    """
    global system
    async with initialization_lock:
        if system:
            raise HTTPException(status_code=409, detail="System has already been initialized.")
        if not drivers:
            raise HTTPException(status_code=400, detail="Cannot start system without any registered drivers.")

        # Validate that a valid combination of algorithms is provided
        is_hybrid = config_model.hybrid_algo is not None
        is_two_step = config_model.clustering_algo is not None and config_model.routing_algo is not None
        
        if not is_hybrid and not is_two_step:
            raise HTTPException(
                status_code=400, 
                detail="Invalid algorithm configuration. "
                    "Provide either a 'hybrid_algo' or both 'clustering_algo' and 'routing_algo'."
            )

        # Create the config and system objects
        sim_config = SimulationConfig(
            clustering_algo=config_model.clustering_algo,
            routing_algo=config_model.routing_algo,
            hybrid_algo=config_model.hybrid_algo,
        )
        
        depot_origin = Point(lng=config_model.depot_origin.lng, lat=config_model.depot_origin.lat)

        system = System(
            config=sim_config,
            vehicles=drivers,
            depot_origin=depot_origin
        )
        
        # The original drivers list is now stored in the system; clear the global list
        drivers.clear()
        
        # Set the simulation time, ensuring it is an aware datetime in UTC
        raw_time = config_model.start_time
        if raw_time.tzinfo is not None:
            # If already aware, convert to UTC
            system.simulation_time = raw_time.astimezone(timezone.utc)
        else:
            # If naive, assume it's UTC and make it aware
            system.simulation_time = raw_time.replace(tzinfo=timezone.utc)
    
    return {"message": "System initialized successfully.", "config": config_model.dict()}


@app.post("/orders", status_code=202, summary="Submit a new order")
async def submit_order(order_model: OrderModel):
    """
    Accepts a new order and adds it to the system for processing.
    """
    if not system:
        raise HTTPException(status_code=400, detail="System has not been initialized. Please start the system first.")

    # Create the Delivery object from the API model
    # The system's current time is used as the creation timestamp
    delivery = Delivery(
        id=order_model.id,
        point=Point(lng=order_model.point.lng, lat=order_model.point.lat),
        size=order_model.size,
        timestamp=int(system.simulation_time.timestamp()),
        preparation=order_model.preparation_minutes,
        time=order_model.deadline_minutes,
    )
    
    await asyncio.to_thread(system.add_new_delivery, delivery)
    
    # Broadcast the new order event to all clients
    await manager.broadcast({
        "type": "new_delivery",
        "timestamp": datetime.now().isoformat(),
        "data": delivery.to_dict()
    })
    
    print(f"Order {order_model.id} accepted. Triggering automatic route update.")
    await update_routes()

    return {"message": f"Order {order_model.id} accepted and route update triggered."}


@app.post("/update_routes", summary="Trigger route optimization and broadcast updates")
async def update_routes():
    if not system:
        raise HTTPException(status_code=400, detail="System has not been initialized.")

    # Use a lock to prevent race conditions from concurrent route updates
    async with routing_lock:
        # Run the core logic that generates new routes in a separate thread
        dispatched_events = await asyncio.to_thread(system.routing_decision_logic)

        # Broadcast individual dispatch events
        for event in dispatched_events:
            await manager.broadcast({
                "type": "driver_dispatched",
                "timestamp": datetime.now().isoformat(),
                "data": event
            })

        # Extract the current state of all vehicles/routes for a full update
        routes_update = []
        for vehicle in system.vehicles.values():
            routes_update.append({
                "vehicle_id": vehicle.id,
                "status": vehicle.status.value,
                "current_route": [
                    system.active_deliveries[delivery_id].to_dict()
                    for delivery_id in vehicle.current_route
                    if delivery_id in system.active_deliveries
                ],
                "route_end_time": vehicle.route_end_time.isoformat() if vehicle.route_end_time else None,
            })
            
        # Broadcast the full system state update
        await manager.broadcast({
            "type": "full_routes_update",
            "timestamp": datetime.now().isoformat(),
            "data": routes_update
        })
    
    return {"message": "Route optimization triggered and updates broadcasted."}


@app.post("/advance_time", summary="Advance the system's internal clock")
async def advance_time(minutes: int = 1):
    """
    Advances the simulation clock by a specified number of minutes
    and processes all events that are due by the new time.
    """
    if not system:
        raise HTTPException(status_code=400, detail="System has not been initialized.")

    from datetime import timedelta

    if minutes <= 0:
        return {
            "message": "Time not advanced. Minutes must be a positive integer.",
            "new_time": system.simulation_time.isoformat(),
            "events_processed": 0
        }
    
    new_time = system.simulation_time + timedelta(minutes=minutes)
    
    # Advance time in a single step
    system.simulation_time = new_time
    
    # Process all events that are now due in a non-blocking way
    processed_events = await asyncio.to_thread(system.process_events_due)

    # Broadcast all events that were processed during the time advance
    for event in processed_events:
        event["timestamp"] = datetime.now().isoformat()
        await manager.broadcast(event)

    return {
        "message": f"System time advanced by {minutes} minutes.",
        "new_time": system.simulation_time.isoformat(),
        "events_processed": len(processed_events)
    }
