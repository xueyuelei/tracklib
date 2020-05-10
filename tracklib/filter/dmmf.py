# -*- coding: utf-8 -*-
'''
Dynamic multiple model filter

REFERENCE:
[1]. Y. Bar-Shalom, X. R. Li, and T. Kirubarajan, "Estimation with Applications to Tracking and Navigation: Theory, Algorithms and Software," New York: Wiley, 2001
'''
from __future__ import division, absolute_import, print_function


__all__ = ['IMMFilter']

import numpy as np
import scipy.linalg as lg
import tracklib.model as model
from .base import FilterBase


class IMMFilter(FilterBase):
    '''
    Interacting multiple model filter
    '''
    def __init__(self, switch_fcn=model.model_switch):
        super().__init__()
        self._switch_fcn = switch_fcn

        self._models = []
        self._model_types = []
        self._probs = None
        self._trans_mat = None
        self._models_n = 0

    def __str__(self):
        msg = 'Interacting multiple model filter:\n{\n  '
        if self._models_n < 10:
            sub = ['{}: model: {}, probability: {}'.format(i, self._models[i], self._probs[i]) for i in range(self._models_n)]
            sub = '\n  '.join(sub)
        else:
            sub = ['{}: model: {}, probability: {}'.format(i, self._models[i], self._probs[i]) for i in range(3)]
            sub.append('...')
            sub.extend(['{}: model: {}, probability: {}'.format(i, self._models[i], self._probs[i]) for i in range(self._models_n - 3, self._models_n)])
            sub = '\n  '.join(sub)
        msg += sub
        msg += '\n}'
        return msg

    def __repr__(self):
        return self.__str__()

    def __iter__(self):
        return ((self._models[i], self._probs[i]) for i in range(self._models_n))

    def __getitem__(self, n):
        if n < 0 or n >= self._models_n:
            raise IndexError('index out of range')
        return self._models[n], self._probs[n]

    def __update(self):
        state_org = [self._models[i].state for i in range(self._models_n)]
        cov_org = [self._models[i].cov for i in range(self._models_n)]
        types = [self._model_types[i] for i in range(self._models_n)]

        xtmp = 0
        for i in range(self._models_n):
            xi = self._switch_fcn(state_org[i], types[i], types[0])
            xtmp += self._probs[i] * xi
        self._state = xtmp

        Ptmp = 0
        for i in range(self._models_n):
            xi = self._switch_fcn(state_org[i], types[i], types[0])
            pi = self._switch_fcn(cov_org[i], types[i], types[0])
            err = xi - xtmp
            Ptmp += self._probs[i] * (pi + np.outer(err, err))
        Ptmp = (Ptmp + Ptmp.T) / 2
        self._cov = Ptmp

    def init(self, state, cov):
        '''
        Initial filter

        Parameters
        ----------
        state : ndarray
            Initial prior state estimate
        cov : ndarray
            Initial error convariance matrix

        Returns
        -------
            None
        '''
        if self._models_n == 0:
            raise RuntimeError('models must be added before calling init')

        for i in range(self._models_n):
            x = self._switch_fcn(state, self._model_types[0], self._model_types[i])
            P = self._switch_fcn(cov, self._model_types[0], self._model_types[i])
            self._models[i].init(x, P)
        self._state = state.copy()
        self._cov = cov.copy()
        self._init = True

    def reset(self, state, cov):
        if self._models_n == 0:
            raise AttributeError("AttributeError: can't set attribute")

        for i in range(self._models_n):
            xi = self._switch_fcn(state, self._model_types[0], self._model_types[i])
            Pi = self._switch_fcn(cov, self._model_types[0], self._model_types[i])
            self._models[i].reset(xi, Pi)

    def add_models(self, models, model_types, probs=None, trans_mat=None):
        '''
        Add new model

        Parameters
        ----------
        models : list, of length N
            the list of Kalman filter
        model_types : list, of length N
            the types corresponding to models
        probs : 1-D array_like, of length N, optional
            model probability
        trans_mat : 2-D array_like, of shape (N, N), optional
            model transition matrix

        Returns
        -------
            None
        '''
        self._models_n = len(models)
        self._models.extend(models)
        self._model_types.extend(model_types)
        if probs is None:
            self._probs = np.full(self._models_n, 1 / self._models_n)
        else:
            self._probs = np.copy(probs)
        if trans_mat is None:
            trans_prob = 0.999
            self._trans_mat = np.zeros((self._models_n, self._models_n))
            self._trans_mat += (1 - trans_prob) / 2
            idx = np.arange(self._models_n)
            self._trans_mat[idx, idx] = trans_prob
        else:
            self._trans_mat = np.copy(trans_mat)

    def predict(self, u=None, **kwargs):
        if self._init == False:
            raise RuntimeError('the filter must be initialized with init() before use')

        # mixing/interaction, the difference from the GPB1 and GPB2 is that merging
        # process (called mixing here) is carried out at the beginning of cycle.
        mixing_probs = self._trans_mat * self._probs
        # prior model probability P(M(k)|Z^(k-1))
        self._probs = np.sum(mixing_probs, axis=1)
        # mixing probability P(M(k-1)|M(k),Z^(k-1))
        mixing_probs /= self._probs.reshape(-1, 1)
        # mixing
        state_org = [self._models[i].state for i in range(self._models_n)]
        cov_org = [self._models[i].cov for i in range(self._models_n)]
        types = [self._model_types[i] for i in range(self._models_n)]

        mixed_state = []
        for i in range(self._models_n):
            xi = 0
            for j in range(self._models_n):
                xj = self._switch_fcn(state_org[j], types[j], types[i])
                xi += mixing_probs[i, j] * xj
            mixed_state.append(xi)
        for i in range(self._models_n):
            Pi = 0
            xi = mixed_state[i]
            for j in range(self._models_n):
                xj = self._switch_fcn(state_org[j], types[j], types[i])
                Pj = self._switch_fcn(cov_org[j], types[j], types[i])
                err = xj - xi
                Pi += mixing_probs[i, j] * (Pj + np.outer(err, err))
            Pi = (Pi + Pi.T) / 2
            self._models[i].reset(xi, Pi)

        for i in range(self._models_n):
            self._models[i].predict(u, **kwargs)
        # update prior state and covariance
        self.__update()

    def correct(self, z, **kwargs):
        if self._init == False:
            raise RuntimeError('the filter must be initialized with init() before use')

        pdf = np.zeros(self._models_n)
        for i in range(self._models_n):
            pdf[i] = self._models[i].likelihood(z, **kwargs)
            self._models[i].correct(z, **kwargs)
        # posterior model probability P(M(k)|Z^k)
        self._probs *= pdf
        self._probs /= np.sum(self._probs)
        # update posterior state and covariance
        self.__update()

    def distance(self, z, **kwargs):
        if self._init == False:
            raise RuntimeError('the filter must be initialized with init() before use')

        d = 0
        for i in range(self._models_n):
            d += self._probs[i] * self._models[i].distance(z, **kwargs)

        return d

    def likelihood(self, z, **kwargs):
        if self._init == False:
            raise RuntimeError('the filter must be initialized with init() before use')

        pdf = 0
        for i in range(self._models_n):
            pdf += self._probs[i] * self._models[i].likelihood(z, **kwargs)

        return pdf

    def models(self):
        return self._models

    def probs(self):
        return self._probs

    def trans_mat(self):
        return self._trans_mat