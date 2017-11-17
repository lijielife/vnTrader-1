import json
import os
from Queue import Queue
from threading import Thread
from eventEngine import *
from language import text
import zmq

PORT = '5556'

class ChartEngine(object):
    def __init__(self, mainEngine, eventEngine):
        self.mainEngine = mainEngine
        self.eventEngine = eventEngine
        
        self.active = True
        self.queue = Queue()
        self.thread = Thread(target=self.run)
        self.zmq_context = zmq.Context()
        self.socket = self.zmq_context.socket(zmq.PUB)
        self.socket.bind('tcp://*:%s' %PORT)
        if self.active:
            self.registerEvent()
            self.start()

    def registerEvent(self):
        self.eventEngine.register(EVENT_CHART_DATA, self.processChartDataEvent)

    def run(self):
        while self.active:
            try:
                chart_data = self.queue.get(block=True, timeout=1)
                self.socket.send_string(chart_data)
            except Exception as e:
                pass

    def start(self):
        self.active = True
        self.thread.start()

    def stop(self):
        if self.active:
            self.active = False
            self.thread.join()

    def processChartDataEvent(self, event):
        log = event.dict_['data']
        self.queue.put(str(log))
        # zmq send to nodejs (publish mode)