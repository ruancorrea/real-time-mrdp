from sklearn.cluster import KMeans
from service.distances import euclidean_matrix
import numpy as np
import pulp

def capacitated_assignment_mip(dist_mat, weights, C):
    m, k = dist_mat.shape
    prob = pulp.LpProblem("cap_assign", pulp.LpMinimize)

    x = {}
    for i in range(m):
        for j in range(k):
            x[(i,j)] = pulp.LpVariable(f"x_{i}_{j}", cat="Binary")

    # Objective
    prob += pulp.lpSum(dist_mat[i,j] * x[(i,j)] for i in range(m) for j in range(k))

    # Each point assigned to exactly one cluster
    for i in range(m):
        prob += pulp.lpSum(x[(i,j)] for j in range(k)) == 1

    # Capacity constraints
    for j in range(k):
        prob += pulp.lpSum(weights[i] * x[(i,j)] for i in range(m)) <= C

    pulp.PULP_CBC_CMD(msg=False).solve(prob)

    assign = np.zeros(m, dtype=int)
    for i in range(m):
        for j in range(k):
            val = pulp.value(x[(i,j)])
            if val is not None and val > 0.5:
                assign[i] = j
                break
    return assign

def adjust_capacity_v1(weights, n_clusters, current_capacity):
    total_weight = weights.sum()
    min_required = int(np.ceil(total_weight / n_clusters))
    if min_required > current_capacity:
        print(f"Ajustando capacidade de {current_capacity} para {min_required} para caber todos os pontos.")
        return min_required
    return current_capacity

def adjust_capacity(current_capacity, beta):
    if current_capacity * beta < current_capacity:
        return current_capacity * beta, beta+0.1
    return current_capacity, beta

def capacitated_kmeans(X, weights, n_clusters, total_capacity, max_iters=20, tol=1e-4, beta=0.7):
    capacity, beta = adjust_capacity(total_capacity, beta)
    km = KMeans(n_clusters=n_clusters, init="k-means++", n_init=10, random_state=0).fit(X)
    centers = km.cluster_centers_

    for iteration in range(max_iters):
        dist = euclidean_matrix(X, centers)
        assign = capacitated_assignment_mip(dist, weights, capacity)

        # atualizar centros
        new_centers = np.zeros_like(centers)
        for j in range(n_clusters):
            idx = np.where(assign == j)[0]
            if len(idx) == 0:
                new_centers[j] = X[np.argmax(dist.sum(axis=1))]
            else:
                w = weights[idx]
                new_centers[j] = np.average(X[idx], axis=0, weights=w)

        shift = np.linalg.norm(new_centers - centers)
        centers = new_centers
        if shift < tol:
            break

    # última atribuição
    final_dist = euclidean_matrix(X, centers)
    final_assign = capacitated_assignment_mip(final_dist, weights, capacity)
    return final_assign, centers