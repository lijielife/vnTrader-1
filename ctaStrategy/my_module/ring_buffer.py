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
        if i < self.iter_min() or i > self.iter_max():
            raise IndexError('index not in range %d-%d' %(self.iter_min(), self.iter_max()))
        return self._array[i % self.buffer_size]

    def iter_min(self):
        if self.iter < self.buffer_size:
            return self.iter
        return self.iter-self.buffer_size + 1

    def iter_max(self):
        return self.iter


if __name__ == '__main__':
    buf = ring_buffer(8)
    for i in range(10):
        #print i
        buf.push_back(i)
        print 'len=%d' %buf.length()
    print buf.iter_min(), buf.iter_max()
    print buf.at(2)
    print buf.at(7)
    print buf.at(8)