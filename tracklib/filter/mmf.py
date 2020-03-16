# -*- coding: utf-8 -*-

import numpy as np
import scipy.linalg as lg
from .kfbase import KFBase
from .kf import KFilter
from .ekf import EKFilter_1st, EKFilter_2ed
from ..utils import col

__all__ = ['MMFilter']


class MMFilter(KFBase):
    '''
    Hybird multiple model filter
    '''
    def __init__(self):
        super().__init__()
        self._model = {}
        self._weight_state = None
        self._maxprob_state = None
        self._model_n = 0

    def __str__(self):
        msg = 'Multiple model filter:\n{\n  '
        if self._model_n < 10:
            sub = ['{}: model: {}, probability: {}'.format(i, self._model[i][0], self._model[i][1]) for i in range(self._model_n)]
            sub = '\n  '.join(sub)
            # [i for i in range(self._model_n)]
        else:
            sub = ['{}: model: {}, probability: {}'.format(i, self._model[i][0], self._model[i][1]) for i in range(3)]
            sub.append('...')
            sub.extend(['{}: model: {}, probability: {}'.format(i, self._model[i][0], self._model[i][1]) for i in range(self._model_n - 3, self._model_n)])
            sub = '\n  '.join(sub)
        msg += sub
        msg += '\n}'
        return msg

    def __repr__(self):
        return self.__str__()

    def __iter__(self):
        return iter(self._model.values())

    def __getitem__(self, n):
        return self._model[n]

    def init(self, state=None, cov=None):
        '''
        Initial filter

        Parameters
        ----------
        state : ndarray or list or None
            Initial prior state estimate
        cov : ndarray or list or None
            Initial error convariance matrix

        Note : if state or cov is None, the model has been initialized outside 

        Returns
        -------
            None
        '''
        if state is None and cov is None:
            pass
        else:
            if isinstance(state, np.ndarray) and isinstance(cov, np.ndarray):
                for i in range(self._model_n):
                    self._model[i][0].init(state, cov)
            elif isinstance(state, list) and isinstance(cov, list):
                for i in range(self._model_n):
                    if state[i] is None or cov[i] is None:
                        continue
                    self._model[i][0].init(state[i], cov[i])
            else:
                raise ValueError('state and cov must be a ndarray, list or None')
        self._len = 0
        self._stage = 0
        self._init = True

    def add_model(self, model, prob):
        '''
        Add new model

        Parameters
        ----------
        model : KFilter or EKFilter
            standard Kalman filter or extended Kalman filter
        probability : float
            model prior probability

        Returns
        -------
            None
        '''
        if isinstance(model, (KFilter, EKFilter_1st, EKFilter_2ed)):
            self._model[self._model_n] = [model, prob]
            self._model_n += 1

    def predict(self, u=None):
        assert (self._stage == 0)
        if self._init == False:
            raise RuntimeError('The filter must be initialized with init() before use')

        for i in range(self._model_n):
            self._model[i][0].predict(u)
        self._stage = 1

    def update(self, z):
        assert (self._stage == 1)
        if self._init == False:
            raise RuntimeError('The filter must be initialized with init() before use')

        pdf = []
        for i in range(self._model_n):
            self._model[i][0].update(z)
            r = self._model[i][0].innov
            S = self._model[i][0].innov_cov
            pdf.append((np.exp(-r.T @ lg.inv(S) @ r / 2) /
                        np.sqrt(lg.det(2 * np.pi * S))).item())

        # total probability
        total = 0
        for i in range(self._model_n):
            total += pdf[i] * self._model[i][1]
        # update all models' posterior probability
        for i in range(self._model_n):
            self._model[i][1] = pdf[i] * self._model[i][1] / total 

        prob = [self._model[i][1] for i in range(self._model_n)]
        # weighted state estimate
        states = np.array([self._model[i][0].post_state.reshape(-1) for i in range(self._model_n)]).T
        self._weight_state = col(np.dot(states, prob))
        # max probability model state estimate
        max_index = np.argmax(prob)
        self._maxprob_state = self._model[max_index][0].post_state

        self._len += 1
        self._stage = 0

    def step(self, z, u=None):
        assert (self._stage == 0)

        self.predict(u)
        self.update(z)
        
    @property
    def weight_state(self):
        return self._weight_state

    @property
    def maxprob_state(self):
        return self._maxprob_state

    @property
    def prob(self):
        return [self._model[i][1] for i in range(self._model_n)]

    @property
    def prior_state(self):
        return [m.prior_state for m in self._model]

    @property
    def post_state(self):
        return [m.post_state for m in self._model]

    @property
    def prior_cov(self):
        return [m.prior_cov for m in self._model]

    @property
    def post_cov(self):
        return [m.post_cov for m in self._model]

    @property
    def innov(self):
        return [m.innov for m in self._model]

    @property
    def innov_cov(self):
        return [m.innov_cov for m in self._model]

    @property
    def gain(self):
        return [m.gain for m in self._model]
