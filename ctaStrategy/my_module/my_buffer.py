#import numpy as np

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
class queue_buffer:
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




if __name__ == '__main__':
    buf = queue_buffer(8)
    for i in range(1000000):
        #print i
        buf.push_back(i)
        #print 'len=%d' %buf.length()
    for item in buf._array:
        print item,
    #print buf.begin(), buf.end()

    #print buf.at(buf.begin()), buf.at(buf.end())
    # print buf.at(2)
    # print buf.at(7)
    # print buf.at(8)