import numpy as np
from scipy.spatial.distance import cdist
from math import radians, sin, cos, sqrt, atan2
from service.structures import Point

def haversine_distance(p1: Point, p2: Point) -> float:
    """
    Calcula a distância entre dois pontos na Terra (especificados em graus decimais)
    usando a fórmula de Haversine. Retorna a distância em quilômetros.
    """
    R = 6371.0  # Raio da Terra em quilômetros

    lat1, lon1 = radians(p1.lat), radians(p1.lng)
    lat2, lon2 = radians(p2.lat), radians(p2.lng)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance = R * c
    return distance

def euclidean_matrix(X, centers):
    diff = X[:, None, :] - centers[None, :, :]
    return np.linalg.norm(diff, axis=2)

def get_distance_matrix(points: np.ndarray = None, batch: list = None, metric: str='euclidean'):
    '''Calculate Distance Matrix between all points.'''
    if isinstance(points, np.ndarray) is False:
        if not batch:
            raise Exception('Points not found')
        points = np.array([[b.point.lat, b.point.lng] for b in batch])
    if isinstance(points, list):
        points = np.array(points)

    if metric == 'haversine':
        # Implementação manual para evitar o ValueError do cdist em algumas versões do SciPy
        num_points = points.shape[0]
        dist_matrix = np.zeros((num_points, num_points))
        # Criar objetos Point para usar a função haversine_distance
        point_objects = [Point(lat=p[0], lng=p[1]) for p in points]
        
        for i in range(num_points):
            for j in range(i, num_points):
                if i == j:
                    continue
                distance = haversine_distance(point_objects[i], point_objects[j])
                dist_matrix[i, j] = distance
                dist_matrix[j, i] = distance
        return dist_matrix
    
    # Comportamento antigo para outras métricas (ex: euclidean)
    return cdist(points, points, metric=metric) * 100

def get_time_matrix(distance_matrix: np.ndarray = None, average_speed_kmh: int = None):
    '''Calculate Time Matrix between all points.'''
    if isinstance(distance_matrix, np.ndarray) is False:
        raise Exception('Distance Matrix not found')

    if not average_speed_kmh:
        raise Exception('Average Speed not found')

    time_matrix_hours = distance_matrix / average_speed_kmh
    time_matrix_minutes = time_matrix_hours * 60

    return time_matrix_minutes
