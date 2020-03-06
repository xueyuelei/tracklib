# -*- coding: utf-8 -*-
import numpy as np

__all__ = ['newton_sys']


def newton_sys(T, dim, axis):
    '''
    return:
     F, L, H
    '''
    assert (0 < dim and dim <= 3)
    assert (0 < axis and axis <= 3)

    items = [1, T, T**2 / 2]

    F = np.zeros((0, dim * axis))
    L = np.zeros((0, axis))
    H = np.zeros((axis, 0))

    tmp = items.copy()
    for i in range(dim):
        F_rows = np.concatenate(list(map(np.diag, map(lambda x: [x] * axis, tmp[:dim]))), axis=1)
        F = np.append(F, F_rows, axis=0)
        L_rows = np.diag([items[-1 - i]] * axis)
        L = np.append(L, L_rows, axis=0)
        H_cols = np.eye(axis) if i == 0 else np.zeros((axis, axis))
        H = np.append(H, H_cols, axis=1)

        tmp[-1] = 0
        # right cyclically shift one element
        tmp = tmp[-1:] + tmp[:-1]

    return F, L, H