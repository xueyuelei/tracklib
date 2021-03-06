# -*- coding: utf-8 -*-
'''
Extended Kalman filter

REFERENCE:
[1]. D. Simon, "Optimal State Estimation: Kalman, H Infinity, and Nonlinear Approaches," John Wiley and Sons, Inc., 2006.
'''
from __future__ import division, absolute_import, print_function


__all__ = ['EKFilterAN', 'EKFilterNAN']

import numpy as np
import scipy.linalg as lg
from functools import partial
from .base import FilterBase
from tracklib.math import num_diff, num_diff_hessian


class EKFilterAN(FilterBase):
    '''
    Additive extended Kalman filter, see[1]

    system model:
    x_k = f_k-1(x_k-1, u_k-1) + L_k-1*w_k-1
    z_k = h_k(x_k) + M_k*v_k
    E(w_k*w_j') = Q_k*δ_kj
    E(v_k*v_j') = R_k*δ_kj

    w_k, v_k, x_0 are uncorrelated to each other
    '''
    def __init__(self,
                 f,
                 L,
                 h,
                 M,
                 Q,
                 R,
                 xdim,
                 zdim,
                 fjac=None,
                 hjac=None,
                 fhes=None,
                 hhes=None,
                 order=1,
                 it=0):
        super().__init__()

        self._f = lambda x, u: f(x, u)
        self._L = L.copy()
        self._h = lambda x: h(x)
        self._M = M.copy()
        self._Q = Q.copy()
        self._R = R.copy()
        self._xdim = xdim
        self._zdim = zdim
        if fjac is None:
            def fjac(x, u):
                F = num_diff(x, partial(self._f, u=u), self._xdim)
                return F
        self._fjac = fjac
        if hjac is None:
            def hjac(x):
                H = num_diff(x, partial(self._h), self._zdim)
                return H
        self._hjac = hjac
        if fhes is None:
            def fhes(x, u):
                FH = num_diff_hessian(x, partial(self._f, u=u), self._xdim)
                return FH
        self._fhes = fhes
        if hhes is None:
            def hhes(x):
                HH = num_diff_hessian(x, self._h, self._zdim)
                return HH
        self._hhes = hhes
        if order == 1 or order == 2:
            self._order = order
        else:
            raise ValueError('order must be 1 or 2')
        self._it = it

    def __str__(self):
        msg = '%s-order additive noise extended Kalman filter' % ('First' if self._order == 1 else 'Second')
        return msg

    def init(self, state, cov):
        self._state = state.copy()
        self._cov = cov.copy()
        self._init = True

    def reset(self, state, cov):
        self._state = state.copy()
        self._cov = cov.copy()

    def predict(self, u=None, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        if len(kwargs) > 0:
            if 'L' in kwargs: self._L[:] = kwargs['L']
            if 'Q' in kwargs: self._Q[:] = kwargs['Q']

        post_state, post_cov = self.state, self._cov

        F = self._fjac(post_state, u)
        Q_tilde = self._L @ self._Q @ self._L.T

        self._state = self._f(post_state, u)
        self._cov = F @ post_cov @ F.T + Q_tilde
        self._cov = (self._cov + self._cov.T) / 2

        if self._order == 2:
            FH = self._fhes(post_state, u)
            quad = np.array([np.trace(FH[:, :, i] @ post_cov) for i in range(self._xdim)], dtype=float)
            self._state += quad / 2

        return self._state, self._cov

    def correct(self, z, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        if len(kwargs) > 0:
            if 'M' in kwargs: self._M[:] = kwargs['M']
            if 'R' in kwargs: self._R[:] = kwargs['R']

        prior_state, prior_cov = self._state, self._cov

        H = self._hjac(prior_state)
        z_pred = self._h(prior_state)
        if self._order == 2:
            HH = self._hhes(prior_state)
            quad = np.array([np.trace(HH[:, :, i] @ prior_cov) for i in range(self._zdim)], dtype=float)
            z_pred += quad / 2
        innov = z - z_pred
        R_tilde = self._M @ self._R @ self._M.T
        S = H @ prior_cov @ H.T + R_tilde
        S = (S + S.T) / 2
        K = prior_cov @ H.T @ lg.inv(S)

        self._state = prior_state + K @ innov
        self._cov = prior_cov - K @ S @ K.T
        self._cov = (self._cov + self._cov.T) / 2

        for _ in range(self._it):
            H = self._hjac(self._state)
            z_pred = self._h(self._state) + H @ (prior_state - self._state)
            if self._order == 2:
                HH = self._hhes(self._state)
                quad = np.array([np.trace(HH[:, :, i] @ self._cov) for i in range(self._zdim)], dtype=float)
                z_pred += quad / 2
            innov = z - z_pred
            R_tilde = self._M @ self._R @ self._M.T
            S = H @ prior_cov @ H.T + R_tilde
            S = (S + S.T) / 2
            K = prior_cov @ H.T @ lg.inv(S)

            self._state = prior_state + K @ innov
            self._cov = prior_cov - K @ S @ K.T
            self._cov = (self._cov + self._cov.T) / 2

        return self._state, self._cov

    def correct_JPDA(self, zs, probs, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        z_len = len(zs)
        Ms = kwargs['M'] if 'M' in kwargs else [self._M] * z_len
        Rs = kwargs['R'] if 'R' in kwargs else [self._R] * z_len

        prior_state, prior_cov = self._state, self._cov

        H = self._hjac(prior_state)
        z_pred = self._h(prior_state)
        if self._order == 2:
            HH = self._hhes(prior_state)
            quad = np.array([np.trace(HH[:, :, i] @ prior_cov) for i in range(self._zdim)], dtype=float)
            z_pred += quad / 2

        state_item = 0
        cov_item1 = cov_item2 = 0
        for i in range(z_len):
            S = H @ prior_cov @ H.T + Ms[i] @ Rs[i] @ Ms[i].T
            S = (S + S.T) / 2
            K = prior_cov @ H.T @ lg.inv(S)

            innov = zs[i] - z_pred
            incre = np.dot(K, innov)
            state_item += probs[i] * incre
            cov_item1 += probs[i] * (prior_cov - K @ S @ K.T)
            cov_item2 += probs[i] * np.outer(incre, incre)

        self._state = prior_state + state_item
        self._cov = (1 - np.sum(probs)) * prior_cov + cov_item1 + (cov_item2 - np.outer(state_item, state_item))
        self._cov = (self._cov + self._cov.T) / 2

        for _ in range(self._it):
            H = self._hjac(self._state)
            z_pred = self._h(self._state) + H @ (prior_state - self._state)
            if self._order == 2:
                HH = self._hhes(self._state)
                quad = np.array([np.trace(HH[:, :, i] @ self._cov) for i in range(self._zdim)], dtype=float)
                z_pred += quad / 2

            state_item = 0
            cov_item1 = cov_item2 = 0
            for i in range(z_len):
                S = H @ prior_cov @ H.T + Ms[i] @ Rs[i] @ Ms[i].T
                S = (S + S.T) / 2
                K = prior_cov @ H.T @ lg.inv(S)

                innov = zs[i] - z_pred
                incre = np.dot(K, innov)
                state_item += probs[i] * incre
                cov_item1 += probs[i] * (prior_cov - K @ S @ K.T)
                cov_item2 += probs[i] * np.outer(incre, incre)

            self._state = prior_state + state_item
            self._cov = (1 - np.sum(probs)) * prior_cov + cov_item1 + (cov_item2 - np.outer(state_item, state_item))
            self._cov = (self._cov + self._cov.T) / 2

        return self._state, self._cov

    def distance(self, z, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        M = kwargs['M'] if 'M' in kwargs else self._M
        R = kwargs['R'] if 'R' in kwargs else self._R

        H = self._hjac(self._state)
        z_pred = self._h(self._state)
        if self._order == 2:
            HH = self._hhes(self._state)
            quad = np.array([np.trace(HH[:, :, i] @ self._cov) for i in range(self._zdim)], dtype=float)
            z_pred += quad / 2
        innov = z - z_pred
        R_tilde = M @ R @ M.T
        S = H @ self._cov @ H.T + R_tilde
        S = (S + S.T) / 2
        d = innov @ lg.inv(S) @ innov + np.log(lg.det(S))

        return d

    def likelihood(self, z, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        M = kwargs['M'] if 'M' in kwargs else self._M
        R = kwargs['R'] if 'R' in kwargs else self._R

        H = self._hjac(self._state)
        z_pred = self._h(self._state)
        if self._order == 2:
            HH = self._hhes(self._state)
            quad = np.array([np.trace(HH[:, :, i] @ self._cov) for i in range(self._zdim)], dtype=float)
            z_pred += quad / 2
        innov = z - z_pred
        R_tilde = M @ R @ M.T
        S = H @ self._cov @ H.T + R_tilde
        S = (S + S.T) / 2
        pdf = 1 / np.sqrt(lg.det(2 * np.pi * S))
        pdf *= np.exp(-innov @ lg.inv(S) @ innov / 2)

        return max(pdf, np.finfo(pdf).tiny)     # prevent likelihood from being too small


class EKFilterNAN(FilterBase):
    '''
    Nonadditive Extended Kalman filter, see[1]

    system model:
    x_k = f_k-1(x_k-1, u_k-1, w_k-1)
    z_k = h_k(x_k, v_k)
    E(w_k*w_j') = Q_k*δ_kj
    E(v_k*v_j') = R_k*δ_kj

    w_k, v_k, x_0 are uncorrelated to each other
    '''
    def __init__(self,
                 f,
                 h,
                 Q,
                 R,
                 xdim,
                 zdim,
                 fjac=None,
                 hjac=None,
                 fhes=None,
                 hhes=None,
                 order=1,
                 it=0):
        super().__init__()

        self._f = lambda x, u, w: f(x, u, w)
        self._h = lambda x, v: h(x, v)
        self._Q = Q.copy()
        self._R = R.copy()
        self._xdim = xdim
        self._wdim = self._Q.shape[0]
        self._zdim = zdim
        self._vdim = self._R.shape[0]
        if fjac is None:
            def fjac(x, u, w):
                F = num_diff(x, partial(self._f, u=u, w=w), self._xdim)
                L = num_diff(w, partial(self._f, x, u), self._wdim)
                return F, L
        self._fjac = fjac
        if hjac is None:
            def hjac(x, v):
                H = num_diff(x, partial(self._h, v=v), self._zdim)
                M = num_diff(v, partial(self._h, x), self._vdim)
                return H, M
        self._hjac = hjac
        if fhes is None:
            def fhes(x, u, w):
                FH = num_diff_hessian(x, partial(self._f, u=u, w=w), self._xdim)
                return FH
        self._fhes = fhes
        if hhes is None:
            def hhes(x, v):
                HH = num_diff_hessian(x, partial(self._h, v=v), self._zdim)
                return HH
        self._hhes = hhes
        if order == 1 or order == 2:
            self._order = order
        else:
            raise ValueError('order must be 1 or 2')
        self._it = it

    def __str__(self):
        msg = '%s-order nonadditive noise extended Kalman filter' % ('First' if self._order == 1 else 'Second')
        return msg

    def init(self, state, cov):
        self._state = state.copy()
        self._cov = cov.copy()
        self._init = True

    def reset(self, state, cov):
        self._state = state.copy()
        self._cov = cov.copy()

    def predict(self, u=None, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        if 'Q' in kwargs: self._Q[:] = kwargs['Q']

        post_state, post_cov = self.state, self._cov

        F, L = self._fjac(post_state, u, np.zeros(self._wdim))
        Q_tilde = L @ self._Q @ L.T

        self._state = self._f(post_state, u, np.zeros(self._wdim))
        self._cov = F @ post_cov @ F.T + Q_tilde
        self._cov = (self._cov + self._cov.T) / 2

        if self._order == 2:
            FH = self._fhes(post_state, u, np.zeros(self._wdim))
            quad = np.array([np.trace(FH[:, :, i] @ post_cov) for i in range(self._xdim)], dtype=float)
            self._state += quad / 2

        return self._state, self._cov

    def correct(self, z, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        if 'R' in kwargs: self._R[:] = kwargs['R']

        prior_state, prior_cov = self.state, self._cov

        H, M = self._hjac(prior_state, np.zeros(self._vdim))
        z_pred = self._h(prior_state, np.zeros(self._vdim))
        if self._order == 2:
            HH = self._hhes(prior_state, np.zeros(self._vdim))
            quad = np.array([np.trace(HH[:, :, i] @ prior_cov) for i in range(self._zdim)], dtype=float)
            z_pred += quad / 2
        innov = z - z_pred
        R_tilde = M @ self._R @ M.T
        S = H @ prior_cov @ H.T + R_tilde
        S = (S + S.T) / 2
        K = prior_cov @ H.T @ lg.inv(S)

        self._state = prior_state + K @ innov
        self._cov = prior_cov - K @ S @ K.T
        self._cov = (self._cov + self._cov.T) / 2

        for _ in range(self._it):
            H, M = self._hjac(self._state, np.zeros(self._vdim))
            z_pred = self._h(self._state, np.zeros(self._vdim)) + H @ (prior_state - self._state)
            if self._order == 2:
                HH = self._hhes(self._state, np.zeros(self._vdim))
                quad = np.array([np.trace(HH[:, :, i] @ self._cov) for i in range(self._zdim)], dtype=float)
                z_pred += quad / 2
            innov = z - z_pred
            R_tilde = M @ self._R @ M.T
            S = H @ prior_cov @ H.T + R_tilde
            S = (S + S.T) / 2
            K = prior_cov @ H.T @ lg.inv(S)

            self._state = prior_state + K @ innov
            self._cov = prior_cov - K @ S @ K.T
            self._cov = (self._cov + self._cov.T) / 2

        return self._state, self._cov

    def correct_JPDA(self, zs, probs, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        z_len = len(zs)
        Rs = kwargs['R'] if 'R' in kwargs else [self._R] * z_len

        prior_state, prior_cov = self._state, self._cov

        H, M = self._hjac(prior_state, np.zeros(self._vdim))
        z_pred = self._h(prior_state, np.zeros(self._vdim))
        if self._order == 2:    # not suitable for JPDA
            HH = self._hhes(prior_state, np.zeros(self._vdim))
            quad = np.array([np.trace(HH[:, :, i] @ prior_cov) for i in range(self._zdim)], dtype=float)
            z_pred += quad / 2

        state_item = 0
        cov_item1 = cov_item2 = 0
        for i in range(z_len):
            S = H @ prior_cov @ H.T + M @ Rs[i] @ M.T
            S = (S + S.T) / 2
            K = prior_cov @ H.T @ lg.inv(S)

            innov = zs[i] - z_pred
            incre = np.dot(K, innov)
            state_item += probs[i] * incre
            cov_item1 += probs[i] * (prior_cov - K @ S @ K.T)
            cov_item2 += probs[i] * np.outer(incre, incre)

        self._state = prior_state + state_item
        self._cov = (1 - np.sum(probs)) * prior_cov + cov_item1 + (cov_item2 - np.outer(state_item, state_item))
        self._cov = (self._cov + self._cov.T) / 2

        for _ in range(self._it):
            H, M = self._hjac(self._state, np.zeros(self._vdim))
            z_pred = self._h(self._state, np.zeros(self._vdim)) + H @ (prior_state - self._state)
            if self._order == 2:
                HH = self._hhes(self._state, np.zeros(self._vdim))
                quad = np.array([np.trace(HH[:, :, i] @ self._cov) for i in range(self._zdim)], dtype=float)
                z_pred += quad / 2

            state_item = 0
            cov_item1 = cov_item2 = 0
            for i in range(z_len):
                S = H @ prior_cov @ H.T + M @ Rs[i] @ M.T
                S = (S + S.T) / 2
                K = prior_cov @ H.T @ lg.inv(S)

                innov = zs[i] - z_pred
                incre = np.dot(K, innov)
                state_item += probs[i] * incre
                cov_item1 += probs[i] * (prior_cov - K @ S @ K.T)
                cov_item2 += probs[i] * np.outer(incre, incre)

            self._state = prior_state + state_item
            self._cov = (1 - np.sum(probs)) * prior_cov + cov_item1 + (cov_item2 - np.outer(state_item, state_item))
            self._cov = (self._cov + self._cov.T) / 2

        return self._state, self._cov

    def distance(self, z, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        R = kwargs['R'] if 'R' in kwargs else self._R

        H, M = self._hjac(self._state, np.zeros(self._vdim))
        z_pred = self._h(self._state, np.zeros(self._vdim))
        if self._order == 2:
            HH = self._hhes(self._state, np.zeros(self._vdim))
            quad = np.array([np.trace(HH[:, :, i] @ self._cov) for i in range(self._zdim)], dtype=float)
            z_pred += quad / 2
        innov = z - z_pred
        R_tilde = M @ R @ M.T
        S = H @ self._cov @ H.T + R_tilde
        S = (S + S.T) / 2
        d = innov @ lg.inv(S) @ innov + np.log(lg.det(S))

        return d

    def likelihood(self, z, **kwargs):
        if self._init == False:
            raise RuntimeError('filter must be initialized with init() before use')

        R = kwargs['R'] if 'R' in kwargs else self._R

        H, M = self._hjac(self._state, np.zeros(self._vdim))
        z_pred = self._h(self._state, np.zeros(self._vdim))
        if self._order == 2:
            HH = self._hhes(self._state, np.zeros(self._vdim))
            quad = np.array([np.trace(HH[:, :, i] @ self._cov) for i in range(self._zdim)], dtype=float)
            z_pred += quad / 2
        innov = z - z_pred
        R_tilde = M @ R @ M.T
        S = H @ self._cov @ H.T + R_tilde
        S = (S + S.T) / 2
        pdf = 1 / np.sqrt(lg.det(2 * np.pi * S))
        pdf *= np.exp(-innov @ lg.inv(S) @ innov / 2)

        return max(pdf, np.finfo(pdf).tiny)     # prevent likelihood from being too small
