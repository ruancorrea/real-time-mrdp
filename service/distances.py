import numpy as np
from scipy.spatial.distance import cdist

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
