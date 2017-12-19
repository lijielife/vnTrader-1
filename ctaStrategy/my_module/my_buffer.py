#import numpy as np
from __future__ import division

class ring_buffer:
    def __init__(self, buffer_size):
        self.iter = -1
        self.buffer_size = buffer_size
        self._array = []
        for i in range(buffer_size):
            self._array.append(None)

    def push_back(self, data):
        self.iter += 1
        #print self.iter % self.buffer_size, data
        self._array[self.iter % self.buffer_size] = data
    
    def length(self):
        if self.iter < self.buffer_size:
            return self.iter
        else:
            return self.buffer_size

    def at(self, i):
        if i < self.begin() or i > self.end():
            raise IndexError('index not in range %d-%d' %(self.begin(), self.end()))
        return self._array[i % self.buffer_size]

    def begin(self):
        if self.iter < self.buffer_size:
            return self.iter
        return self.iter-self.buffer_size + 1

    def end(self):
        return self.iter

    
from collections import deque
class deque_buffer:
    def __init__(self, buffer_size):
        self._full = False
        self.buffer_size = buffer_size
        self._array = deque(maxlen=buffer_size)
    
    def push_back(self, data):
        if self.already_full():
            self._array.popleft()
        self._array.append(data)
    
    def length(self):
        return len(self._array)

    def already_full(self):
        if self.length() == self._array.maxlen:
            self._full = True
        return self._full



import numpy as np
def maxdrawdown(arr):
    arr = np.array(arr)
    tmp = (np.maximum.accumulate(arr) - arr)/np.maximum.accumulate(arr)
    i = np.argmax(tmp)
    if i==0:
        return 0.0
    return tmp[i]

def maxrdrawdown(arr):
    arr = np.array(arr)
    tmp = (arr - np.minimum.accumulate(arr))/np.minimum.accumulate(arr)
    i = np.argmax(tmp)
    if i==0:
        return 0.0
    return tmp[i]


if __name__ == '__main__':
    buf = deque_buffer(8)
    buf.push_back(4)
    buf.push_back(8)
    buf.push_back(7)
    buf.push_back(6)
    buf.push_back(5)
    buf.push_back(1)
    buf.push_back(1)
    buf.push_back(1)


    arr = np.array(buf._array)
    #print arr
    print arr
    print maxdrawdown(buf._array)
    

    l = [ 25860.,  25855.,  25820.,  25840.,  25840.,  25805.,  25810.,  25760.,  25765.,
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

    print maxdrawdown(l)
    
    print maxrdrawdown(l)
    import matplotlib.pyplot as plt
    plt.plot(l)
    plt.show()