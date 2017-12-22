#encoding utf-8
from __future__ import division

import numpy as np
from scipy import interpolate
from zigzag import *

MAX_NUMBER = 1000000
MIN_NUM = 0

__MY_DEBUG__ = True
MATCHES = []
ALL = []
MATCH_THRSH = .15

ZIGZAG_THRSH = 0.001

#-------------------- Predefined Patterns ----------------
PATTERN_TOUJIANDING = [ 0.,  1.,  0.,  10.,  0.,  1.,  0.]
PATTERN_TOUJIANDI   = [ 0., -1.,  0., -2.,  0., -1.,  0.]
PATTERN_SHUANGDING  = [ 0.,  1.,  0.,  1.,  0.]
PATTERN_SHUANGDI    = [ 0., -1.,  0., -1.,  0.]
PATTERN_SSSJ        = [-3.,  0., -2.,  0., -1.,  0.]
PATTERN_XJSJ        = [ 3.,  0.,  2.,  0.,  1.,  0.]
PATTERN_DCSJ        = [ 5., -4.,  3., -2.,  1.,  0.]

#-------------------- Predefined Functors ----------------

def abs_d_functor(p1, p2):
    return abs(p1-p2)

def echo_preprocess_functor(seq):
    return seq

def zigzag_preprocess_functor(seq):
    pivots = peak_valley_pivots(seq, ZIGZAG_THRSH, -ZIGZAG_THRSH)
    X = np.arange(0, len(seq))
    X_pivots = X[pivots != 0]
    Y_pivots = seq[X_pivots]
    f = interpolate.interp1d(X_pivots, Y_pivots)
    return f(X)

def none_penalty_functor(seq, pat):
    return 0

def order_penalty_functor(seq, pat):
    def _my_pivots(p):
        assert len(p) >= 2
        result = []
        def _append(ele):
            if not result or result[-1] != ele:
                result.append(ele)

        for i in range(len(p)-1):
            if p[i] < p[i+1]:
                _append(-1)
            elif p[i] > p[i+1]:
                _append(1)
        result.append(-result[-1])
        return result
    try:
        pivots1 = _my_pivots(np.array(seq))
        pivots2 = _my_pivots(np.array(pat))
    except Exception as e:
        print str(e)
        return np.nan
    cmp_result = filter(lambda x:x!=0, pivots1) == filter(lambda x:x!=0, pivots2)
    if cmp_result:
        return 1
    return np.nan

#------------------- Calculate distance ------------------
def _distance(sequence, pattern, d_functor=abs_d_functor, penalty_functor=none_penalty_functor):
    m = len(sequence)
    n = len(pattern)
    D_table = np.ones((m, n)) * MAX_NUMBER

    def get_D(i, j):
        if i > m-1 or j > n-1:
            raise RuntimeError('Index error')
        if i == -1 or j == -1:
            return MAX_NUMBER
        else:
            return D_table[i][j]

    for sij in range(m + n -1):
        for i in range(sij + 1):
            j = sij - i
            if i > m - 1 or j > n-1:
                continue
            point_i = sequence[i]
            point_j = pattern[j]
            if i == 0 and j == 0:
                D_table[0][0] = d_functor(point_i, point_j)
            else:
                D_table[i][j] = min(get_D(i-1, j), get_D(i, j-1), get_D(i-1, j-1)) \
                                + d_functor(point_i, point_j)

    return D_table[m-1][n-1] * penalty_functor(sequence, pattern)


#---------------------------- Api ------------------------
def pattern_match(sequence,
                  pattern,
                  d_functor=abs_d_functor,
                  preprocess_functor=echo_preprocess_functor,
                  penalty_functor = none_penalty_functor,
                  window_size=0):
    sequence = np.array(preprocess_functor(sequence))
    if __MY_DEBUG__:
        global MATCHES
    result = np.ones_like(sequence) * np.nan
    ptn_len = len(pattern)
    seq_len = len(sequence)
    assert ptn_len <= seq_len
    
    if window_size == 0:
        # adaptable window_size
        window_size = ptn_len

    # pattern normalization
    pattern -= pattern[-1]
    pattern /= np.ptp(pattern)

    for pos in range(window_size-1, seq_len):
        # calc distance
        distance = MAX_NUMBER
        seq_seg = np.array(sequence[pos - window_size + 1  :pos + 1])
        # seq_segment normalization
        seq_seg -= seq_seg[-1]
        seq_seg /= np.ptp(seq_seg)
        distance = _distance(seq_seg, pattern, d_functor, penalty_functor) /max(window_size, ptn_len)
        if __MY_DEBUG__:
            if distance < MATCH_THRSH:
                MATCHES.append(seq_seg)
        result[pos] = distance
    
    return result

#-----------------------
def pattern_match_adapt(seq, pattern, d_functor=abs_d_functor):
    global MATCHES, ALL
    pivots = peak_valley_pivots(seq, ZIGZAG_THRSH, -ZIGZAG_THRSH)
    X = np.arange(0, len(seq))
    X_pivots = X[pivots != 0]
    Y_pivots = seq[X_pivots]
    f = interpolate.interp1d(X_pivots, Y_pivots)
    sequence = f(X)

    result = np.ones_like(sequence) * np.nan
    # pattern normalization
    pattern -= pattern[-1]
    pattern /= np.ptp(pattern)

    def transform_pivots(p):
        r = map(lambda x:abs(x), p)
        cnt = 0
        for i in range(len(r)):
            if r[i] != 0:
                cnt += 1
                r[i] = cnt
        return r

    pivots_cumsum = transform_pivots(pivots)
    
    displace = len(pattern)
    delta = 0
    start = 0
    end = pivots_cumsum.index(displace)
    end_next_pivot = end #pivots_cumsum.index(displace)
    while end < len(sequence):
        # match it
        # calc distance
        distance = MAX_NUMBER
        seq_seg = np.array(sequence[start:end+1])
        # seq_segment normalization
        seq_seg -= seq_seg[-1]
        seq_seg /= np.ptp(seq_seg)
        
        distance = _distance(seq_seg, pattern, d_functor, order_penalty_functor) /max(len(seq_seg), len(pattern))
        if __MY_DEBUG__:
            import matplotlib.pyplot as plt
            #plt.plot(x=range(start, end+1), y=seq_seg)
            print 'img/%d.png' %end
            plt.figure(0)
            X = np.arange(start, end+1, 1)
            plt.plot(X, seq_seg)
            plt.title('distance = %f'%distance)
            plt.grid('on')
            plt.savefig('img/%d.png'%end)
            plt.close(0)
        if __MY_DEBUG__:
            if distance < MATCH_THRSH:
                MATCHES.append(seq_seg)
        result[end] = distance
        end += 1
        if end > end_next_pivot:
            delta += 1
            try:
                end_next_pivot =  pivots_cumsum.index(displace + delta)
                start = pivots_cumsum.index(1 + delta)
            except ValueError:
                pass
    return result
            




# --------------------test cases--------------------------
if __name__ == "__main__":

    #--------------------test case 1---------------------
    print 'test case 1...'
        
    sequence_1 = [1., 4., 4., 8., 3., 2., 7., 9., 8., 3., 1.]
    sequence_2 = [2., 3., 9., 6., 2., 2., 5., 8., 9., 4., 3.]
    assert _distance(sequence_1, sequence_2, penalty_functor=order_penalty_functor)==14
    print 'pass!'
    

    #--------------------test case 2---------------------
    print 'test case 2...'
    import matplotlib.pyplot as plt

    l =[25860.,  25855.,  25820.,  25840.,  25840.,  25805.,  25810.,  25760.,  25765.,
        25770.,  25790.,  25790.,  25765.,  25780.,  25790.,  25825.,  25835.,  25825.,
        25830.,  25830.,  25845.,  25820.,  25825.,  25750.,  25770.,  25755.,  25695.,
        25670.,  25680.,  25700.,  25705.,  25710.,  25695.,  25690.,  25675.,  25690.,
        25700.,  25705.,  25735.,  25740.,  25750.,  25730.,  25720.,  25730.,  25720.,
        25720.,  25685.,  25700.,  25690.,  25690.,  25685.,  25680.,  25670.,  25680.,
        25685.,  25695.,  25690.,  25705.,  25705.,  25700.,  25680.,  25690.,  25685.,
        25705.,  25715.,  25730.,  25730.,  25715.,  25700.,  25715.,  25720.,  25730.,
        25735.,  25730.,  25725.,  25720.,  25720.,  25725.,  25695.,  25685.,  25675.,
        25680.,  25680.,  25700.,  25720.,  25730.,  25710.,  25735.,  25735.,  25775.,
        25760.,  25755.,  25735.,  25740.,  25710.,  25675.,  25650.,  25670.,  25640.,
        25625.,  25640.,  25655.,  25645.,  25645.,  25640.,  25630.,  25580.,  25530.,
        25520.,  25510.,  25535.,  25480.,  25480.,  25500.,  25460.,  25510.,  25495.,
        25525.,  25500.,  25470.,  25510.,  25540.,  25590.,  25560.,  25560.,  25575.,
        25550.,  25545.,  25545.,  25525.,  25515.,  25515.,  25490.,  25515.,  25540.,
        25510.,  25495.,  25520.,  25490.,  25535.,  25540.,  25540.,  25530.,  25510.,
        25535.,  25545.,  25535.,  25535.,  25560.,  25555.,  25530.,  25540.,  25525.,
        25540.,  25540.,  25550.,  25550.,  25555.,  25545.,  25545.,  25565.,  25575.,
        25600.,  25570.,  25580.,  25570.,  25550.,  25570.,  25555.,  25544.,  25545.,
        25540.,  25535.,  25515.,  25525.,  25535.,  25550.,  25540.,  25530.,  25540.,
        25545.,  25535.,  25520.,  25490.,  25505.,  25525.,  25500.,  25500.,  25500.,
        25480.,  25475.,  25445.,  25460.,  25465.,  25470.,  25500.,  25505.,  25520.,
        25525.,  25525.,  25545.,  25530.,  25505.,  25475.,  25415.,  25450.,  25460.,
        25435.,  25465.,  25440.,  25465.,  25455.,  25445.,  25435.,  25450.,  25470.,
        25435.,  25425.,  25435.,  25440.,  25425.,  25435.,  25450.,  25455.,  25450.,
        25450.,  25465.,  25445.,  25435.,  25440.,  25425.,  25430.,  25410.,  25400.,
        25400.,  25420.,  25400.,  25420.,  25430.,  25435.,  25445.,  25425.,  25420.,
        25415.,  25420.,  25440.,  25415.,  25415.,  25315.,  25330.,  25375.,  25360.,
        25360.,  25370.,  25410.,  25425.,  25425.,  25460.,  25465.,  25460.,  25460.,
        25510.,  25510.,  25465.,  25465.,  25470.,  25495.,  25495.,  25475.,  25465.,
        25470.,  25485.,  25485.,  25485.,  25485.,  25480.,  25475.,  25490.,  25480.,
        25495.,  25485.,  25510.,  25505.,  25505.,  25530.,  25500.,  25500.,  25480.,
        25490.,  25490.,  25460.,  25460.,  25455.,  25455.,  25450.,  25435.,  25445.,
        25450.,  25455.,  25450.]

    S = np.array(l)
    #printprint len(l)
    #p = np.array([-1., 1., -1., 1., -1.])
    p = np.array(PATTERN_TOUJIANDING)
    #result =  pattern_match(S, p, preprocess_functor=zigzag_preprocess_functor, penalty_functor=order_penalty_functor,window_size=0)
    result = pattern_match_adapt(S, p)
  
    plt.figure()
    fig1 = plt.subplot(311)
    fig1.plot(S, 'k')
    series = map(lambda x:x, zigzag_preprocess_functor(S))
    fig1.plot(series, 'r')

    fig2 = plt.subplot(312)
    fig2.plot(result)

    fig3 = plt.subplot(313)
    for seg in MATCHES:
        fig3.plot(seg)
    plt.show()

