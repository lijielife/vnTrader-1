import numpy as np
import scipy as sp
from copy import copy

np.seterr(over='raise')

EXP_MAX = np.log(np.finfo(np.float64).max)

DIVIDE_MIN = 1.0/np.finfo(np.float64).max

MIN_FLOAT = .05

#cnt = 0
class WonhamFilter(object):
    def __init__(self):
        # Variables
        self.inited = False

    def WF_Init(self, dt, Q, mu, sig):
        self.N_states = len(mu)
        assert Q.shape == (self.N_states, self.N_states)
        self.dt = dt
        self.mu = np.array([mu]).T
        print self.mu
        self.sig = sig
        # Q matrix
        self.Q = Q

        self.inv_sig2 = (1.0/sig)**2
        self.p = np.array([1.0/self.N_states]*self.N_states)
        self.inited = True

    def A(self):
        # diag(f0, f1)
        part1 = np.identity(self.N_states)*self.mu
        part2 = (self.p * self.mu)*np.identity(self.N_states)
        return part1 - part2

    def P_inv(self):
        return (1.0 / self.p) * np.identity(self.N_states)
    
    def Calculate(self, dY):
        #global cnt
        if not self.inited:
            raise RuntimeError('Not inited')
        pt = self.p
        A = self.A()

        drift_coef = np.dot(np.dot(pt, self.Q), self.P_inv()) \
                     - self.inv_sig2 * np.dot(pt, self.mu) * np.diag(A) \
                     - 0.5 * self.inv_sig2 * np.diag(np.dot(A, A))
        diffusion = self.inv_sig2 * np.diag(A)*dY

        dv = drift_coef * self.dt + diffusion

        v = np.log(pt) + dv

        overflow = -1
        max_overflow_num = 0.0
        for i in range(self.N_states):
            if v[i] > EXP_MAX:
                if v[i] > max_overflow_num:
                    overflow = i
                    max_overflow_num = v[i]
                    
                
        if overflow > -1:
            self.p = np.array([MIN_FLOAT] * self.N_states)
            self.p[overflow] = 1.0 - (self.N_states - 1) * MIN_FLOAT
        else:
            p = np.exp(v)
            self.p = p / np.sum(p)
            #one_index = -1
            # for i in range(self.N_states):
            #     if self.p[i] == 1.0:
            #         self.p[i] = 1.0 - (self.N_states - 1) * MIN_FLOAT
            #         one_index = i
            #         for j in range(self.N_states):
            #             if j != one_index:
            #                 self.p[j] = 0.0
            #         break
        
        for i in range(self.N_states):
            if self.p[i] <= DIVIDE_MIN:
                self.p[i] = MIN_FLOAT

        #print cnt, dY, self.p
        #cnt+=1
        return tuple(self.p)

