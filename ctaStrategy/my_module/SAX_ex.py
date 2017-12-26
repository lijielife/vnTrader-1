from __future__ import division
from saxpy.saxpy import SAX
import numpy as np
from collections import Counter

class SAX_ex(object):
    def __init__(self, word_size=8, alphabet_size=7, epsilon=1e-6):
        self.sax = SAX(word_size, alphabet_size, epsilon)
        self.m = alphabet_size

    def to_letter_rep(self, x):
        return self.sax.to_letter_rep(x)

    def sliding_window(self, x, numSubsequences, overlappingFraction):
        return self.sax.sliding_window(x, numSubsequences, overlappingFraction)

    def batch_compare(self, xStrings, refString):
        return self.sax.batch_compare(xStrings, refString)

    def euclidean_distance(self, sA, sB):
        return self.sax.compare_strings(sA, sB)

    def stats_distance(self, vA, vB):
        cos_vAB = np.dot(vA, vB)/(np.linalg.norm(vA)*np.linalg.norm(vB))
        return 1 - cos_vAB
    
    def to_stats_vector(self, s):
        #----------- return value-----------
        vector = np.ones(self.m + 12) * np.nan
        #----------- 1. symbol freq --------
        pos = 0
        cnt = Counter(s)
        sum_ = len(s)
        freq_dict = {k:v/sum_ for k,v in dict(cnt).items()}
        
        for i in range(self.m):
            vector[pos + i] = freq_dict.get(chr(97 + i), 0)
        #----------- 2. difference ---------
        pos += self.m
        ascii_list = [ord(x) for x in list(s)]
        diff_list = np.diff(ascii_list)
        cnt = Counter(diff_list)
        cnt_equ = sum(map(lambda x:cnt[x], filter(lambda x: x==0, cnt)))
        cnt_up = sum(map(lambda x:cnt[x], filter(lambda x: x>0, cnt)))
        cnt_down = sum(map(lambda x:cnt[x], filter(lambda x: x<0, cnt)))
        vector[pos] = cnt_equ / (sum_ - 1)
        vector[pos + 1] = cnt_up / (sum_ - 1)
        vector[pos + 2] = cnt_down / (sum_ - 1)
        assert cnt_equ + cnt_up + cnt_down == sum_ - 1
        #------------ 3. peak valley --------
        pos = pos + 3
        
        print diff_list
        return vector

    def comprehensive_distance(self, sA, sB, w_e=.5, w_s=.5):
        vA = self.to_stats_vector(sA)
        vB = self.to_stats_vector(sB)
        e_d = self.euclidean_distance(sA, sB)
        s_d = self.stats_distance(vA, vB)
        return w_e * e_d + w_s * s_d


if __name__ == '__main__':
    sax = SAX_ex()
    v = sax.to_stats_vector('abccdaa')
    print v
