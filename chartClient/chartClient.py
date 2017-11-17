"""
Demonstrate creation of a custom graphic (a candlestick plot)

"""
import zmq
import pyqtgraph as pg
from pyqtgraph import QtCore, QtGui
from pyqtgraph.ptime import time
import random
from threading import Thread
import json
import cPickle

PORT = '5556'

## Create a subclass of GraphicsObject.
## The only required methods are paint() and boundingRect() 
## (see QGraphicsItem documentation)
class CandlestickItem(pg.GraphicsObject):
    def __init__(self):
        pg.GraphicsObject.__init__(self)
        self.flagHasData = False

    def set_data(self, data):
        self.data = data  ## data must have fields: time, open, close, min, max
        self.flagHasData = True
        self.generatePicture()
        self.informViewBoundsChanged()

    def generatePicture(self):
        ## pre-computing a QPicture object allows paint() to run much more quickly, 
        ## rather than re-drawing the shapes every time.
        global last_pf
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)
        w = 1.0/3 #(self.data[1][0] - self.data[0][0]) / 3. 
        #last_pf = self.data[0][2]
        first = True
        for (t, open, close, min, max, pf) in self.data:
            if open > close:
                #p.setBrush(pg.mkBrush('g'))
                p.setPen(pg.mkPen('g'))
            elif open < close:
                #p.setBrush(pg.mkBrush('r'))
                p.setPen(pg.mkPen('r'))
            else:
                p.setPen(pg.mkPen('w'))
            if min < max:
                p.drawLine(QtCore.QPointF(t, min), QtCore.QPointF(t, max))
            p.drawRect(QtCore.QRectF(t-w, open, w*2, close-open))
            p.setPen(pg.mkPen('y', width=1.5, style=QtCore.Qt.DashLine))
            if not first:
                p.drawLine(QtCore.QPointF(t-1, last_pf), QtCore.QPointF(t, pf))
            first = False
            last_pf = pf
        p.end()

    def paint(self, p, *args):
        if self.flagHasData:
            p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        ## boundingRect _must_ indicate the entire area that will be drawn on
        ## or else we will get artifacts and possibly crashing.
        ## (in this case, QPicture does all the work of computing the bouning rect for us)
        return QtCore.QRectF(self.picture.boundingRect())

app = QtGui.QApplication([])

data = [] ## fields are (time, open, close, min, max).

last_pf = 0.0
item = CandlestickItem()
item.set_data(data)
t = 0

plt = pg.plot()
plt.addItem(item)
plt.setWindowTitle('pyqtgraph example: customGraphicsItem')
plt.setFixedSize(1200, 600)
bar = None
pf = None

def update():
    global item, data, t, bar, pf
    if bar and pf:
        t += 1
        new_bar = [t, bar['open'], bar['close'], bar['low'], bar['high'], pf]
        data.append(new_bar)
        data = data[-300:]
        item.set_data(data)
        bar, pf = None, None
    app.processEvents()  ## force complete redraw for every plot

class ChartClient(object):
    def __init__(self):
        self.zmq_context = zmq.Context()
        self.socket = self.zmq_context.socket(zmq.SUB)
        self.socket.connect('tcp://localhost:%s' %PORT)
        self.socket.setsockopt(zmq.SUBSCRIBE,'')
        self.thread = Thread(target=self.run)
        self.active = True
        self.thread.start()
    
    def run(self):
        global bar, pf
        while self.active:
            try:
                msg = self.socket.recv_string()
                msg_parsed = json.loads(msg)
                charts = cPickle.loads(str(msg_parsed['chart']))
                for chart in charts:
                    if chart['type'] == 'Kline':
                        bar = chart['data']
                    elif chart['type'] == 'PF':
                        pf = chart['data']

            except Exception as e:
                print e

timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(100)

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    import sys
    client = ChartClient()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        #QtGui.QApplication.instance().exec_()
        app.exec_()
    client.active = False
    #client.thread.join()