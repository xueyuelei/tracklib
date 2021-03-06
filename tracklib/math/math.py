# -*- coding: utf-8 -*-
'''
REFERENCE:
[1]. R. L. Burden and J. D. Faires, "Numerical Analysis," 9th ed. Boston, MA: Brooks/ Cole, 2011.
'''
from __future__ import division, absolute_import, print_function


__all__ = ['lagrange_interp_poly', 'num_diff', 'num_diff2', 'num_diff_hessian']

import numbers
import numpy as np


def lagrange_interp_poly(x, y=None):
    x = np.array(x, dtype=float)
    if y is not None:
        y = np.array(y, dtype=float)

    N = len(x)

    Li = np.zeros((N, N))
    dLi = None
    d2Li = None
    if N == 1:
        Li = np.eye(N)
    else:
        for cur_order in range(N):
            sel = [i for i in range(N) if i != cur_order]
            num_poly = np.poly(x[sel])

            Li[:, cur_order] = num_poly / np.polyval(num_poly, x[cur_order])

        if N - 1 > 0:
            dLi = np.zeros((N - 1, N))
            for k in range(N):
                dLi[:, k] = np.polyder(Li[:, k])
        if N - 2 > 0:
            d2Li = np.zeros((N - 2, N))
            for k in range(N):
                d2Li[:, k] = np.polyder(dLi[:, k])

    if y is not None:
        Li = Li @ y
        dLi = None if dLi is None else dLi @ y
        d2Li = None if d2Li is None else d2Li @ y

    return Li, dLi, d2Li


# print(lagrange_interp_poly([3]))
# print(lagrange_interp_poly([3], [2]))
# print(lagrange_interp_poly(np.array([2, 5], dtype=float)))
# print(lagrange_interp_poly(np.array([2, 5], dtype=float), np.array([1, 2], dtype=float)))
# print(lagrange_interp_poly([40, 66, 18, 71, 4, 28, 5, 10, 83, 70], [32, 96, 4, 44, 39, 77, 80, 19, 49, 45]))


def num_diff(x, f, f_dim, order=1, epsilon=None):
    '''
    First-order numerical differentiation which can be used
    to calculate the Jacobian matrix.
    '''
    x = np.array(x, dtype=float)
    x_dim = len(x)

    if isinstance(epsilon, numbers.Number):
        epsilon = np.full(x.shape, epsilon, dtype=float)

    # If epsilon is not specified, then use some ad-hoc default value
    if epsilon is None:
        epsilon = np.array([max(eps, np.sqrt(np.finfo(eps).eps)) for eps in 1e-5 * np.abs(x)], dtype=float)
    else:
        epsilon = np.array([max(eps, np.sqrt(np.finfo(eps).eps)) for eps in epsilon], dtype=float)

    # 2*order+1 points fomula, error term is O(eps^(2*order))
    if order == 1:
        a, d = [1], 2
    elif order == 2:
        a, d = [8, -1], 12
    elif order == 3:
        a, d = [45, -9, 1], 60
    elif order == 4:
        a, d = [672, -168, 32, -3], 840
    elif order == 5:
        a, d = [2100, -600, 150, -25, 2], 2520
    elif order == 6:
        a, d = [23760, -7425, 2200, -495, 72, -5], 27720
    elif order == 7:
        a, d = [315315, -105105, 35035, -9555, 1911, -245, 15], 360360
    elif order == 8:
        a, d = [640640, -224224, 81536, -25480, 6272, -1120, 128, -7], 720720
    else:
        _, a, _ = lagrange_interp_poly(list(range(-order, order + 1)))
        a = (-a[-1, order - 1::-1]).tolist()
        d = 1

    p = len(a)
    J = np.zeros((f_dim, x_dim))
    for cur_el in range(x_dim):  # epsilon has same length as x
        eps = epsilon[cur_el]
        for cur_p in range(p):
            xp = x.copy()
            xp[cur_el] += (cur_p + 1) * eps  # partial derivation
            fxp = f(xp)
            J[:, cur_el] += a[cur_p] * fxp

            xp = x.copy()
            xp[cur_el] -= (cur_p + 1) * eps
            fxp = f(xp)
            J[:, cur_el] -= a[cur_p] * fxp
        J[:, cur_el] /= d * eps
    return J


# f = lambda x: np.array([np.log(x[0]), np.sin(x[0])], dtype=float)
# x = [0.25]
# print(num_diff(x, f, 2))
# print(num_diff(x, f, 2, order=9))

# f = lambda x: np.array(
#     [np.log(x[0]) + np.sin(x[0]),
#      np.log(x[1]) + np.sin(x[1])], dtype=float)
# x = [1.0, 2.0]
# print(num_diff(x, f, 2))
# print(num_diff(x, f, 2, order=9))
# x = np.array([1.0, 2.0], dtype=float)
# print(num_diff(x, f, 2))
# print(num_diff(x, f, 2, order=9))


def num_diff2(x, f, f_dim, order=1, epsilon=None):
    '''
    Second-order numerical differentiation
    '''
    x = np.array(x, dtype=float)
    x_dim = len(x)

    if isinstance(epsilon, numbers.Number):
        epsilon = np.full(x.shape, epsilon, dtype=float)

    # If epsilon is not specified, then use some ad-hoc default value
    if epsilon is None:
        epsilon = np.array([max(eps, np.sqrt(np.finfo(eps).eps)) for eps in 1e-5 * np.abs(x)], dtype=float)
    else:
        epsilon = np.array([max(eps, np.sqrt(np.finfo(eps).eps)) for eps in epsilon], dtype=float)

    # 2*N+1 points fomula, error term is O(eps^(2*N))
    if order == 1:
        a = [1, -2, 1]
    elif order == 2:
        a = [-1 / 12, 4 / 3, -5 / 2, 4 / 3, -1 / 12]
    elif order == 3:
        a = [1 / 90, -3 / 20, 3 / 2, -49 / 18, 3 / 2, -3 / 20, 1 / 90]
    else:
        _, _, a = lagrange_interp_poly(list(range(-order, order + 1)))
        a = a[-1, :].tolist()

    J2 = np.zeros((f_dim, x_dim))

    p = len(a)
    for cur_el in range(x_dim):  # epsilon has same length as x
        eps = epsilon[cur_el]
        for cur_p in range(p):
            xp = x.copy()
            xp[cur_el] += (cur_p - order) * eps
            fxp = f(xp)
            J2[:, cur_el] += a[cur_p] * fxp
        J2[:, cur_el] /= (eps**2)
    return J2


# f = lambda x: np.array([np.log(x[0]), np.sin(x[1])], dtype=float)
# x = [0.25, 2]
# print(num_diff2(x, f, 2))
# print(num_diff2(x, f, 2, order=5))
# x = np.array(x, dtype=float)
# print(num_diff2(x, f, 2))
# print(num_diff2(x, f, 2, order=5))

# f = lambda x: np.log(x)
# x = [1.0]
# print(num_diff2(x, f, 1))


def num_diff_hessian(x, f, f_dim, epsilon=None):
    '''
    Second-order partial derivation used to calculate Hessian matrix
    '''
    x = np.array(x, dtype=float)
    x_dim = len(x)

    if isinstance(epsilon, numbers.Number):
        epsilon = np.full(x.shape, epsilon, dtype=float)

    # If epsilon is not specified, then use some ad-hoc default value
    if epsilon is None:
        epsilon = np.array([max(eps, np.sqrt(np.finfo(eps).eps)) for eps in 1e-5 * np.abs(x)], dtype=float)
    else:
        epsilon = np.array([max(eps, np.sqrt(np.finfo(eps).eps)) for eps in epsilon], dtype=float)

    hess = np.zeros((x_dim, x_dim, f_dim))
    e1 = np.zeros(x_dim)
    e2 = np.zeros(x_dim)
    for i in range(x_dim):
        e1[i] = 1
        h = epsilon[i] * e1
        e1[i] = 0
        for j in range(x_dim):
            e2[j] = 1
            k = epsilon[j] * e2
            e2[j] = 0
            f1 = f(x + h + k)
            f2 = f(x - h - k)
            f3 = f(x - h + k)
            f4 = f(x + h - k)
            # central difference
            hess[i, j, :] = (f1 + f2 - f3 - f4) / (4 * h[i] * k[j])
            hess[j, i, :] = hess[i, j, :]
    return hess


# f = lambda x: np.array([x[1] * np.log(x[0]), x[1] * np.sin(x[0])], dtype=float)
# x = [0.25, 1]
# print(num_diff_hessian(x, f, 2)[:, :, 0])
# print(num_diff_hessian(x, f, 2)[:, :, 1])
# x = np.array([0.25, 1])
# print(num_diff_hessian(x, f, 2)[:, :, 0])
# print(num_diff_hessian(x, f, 2)[:, :, 1])
