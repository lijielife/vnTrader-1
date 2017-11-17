# encoding: UTF-8
"""定时任务模块"""
from threading import Thread
import threading
from eventEngine import *
import time

class CtaTaskResult(object):
    """Task.taskJob()的返回值， 包含任务名称task_name, 任务数据data"""
    def __init__(self):
        self.task_name = ''
        self.data = {}


class CtaTask(object):
    def __init__(self, strategy, interval=1):
        # 注入strategy实例
        self.strategy = strategy
        self.ctaEngine = strategy.ctaEngine
        self.interval = interval
        # 任务是否在执行
        self.active = False
        # 任务线程
        self._thread = Thread(target=self.__run__)
        # 线程 Event
        self.block_event = threading.Event()

    def start(self):
        """开始执行Task"""
        self.active = True
        self._thread.start()

    def stop(self):
        """停止执行Task"""
        # active设为false结束循环
        self.active = False
        # Event 设为 set, 解除线程阻塞
        self.block_event.set()

    def __run__(self):
        # 任务执行循环
        while(self.active):
            task_ret = {}
            # 执行 taskJob
            task_ret['result'] = self.taskJob()
            task_ret['strategy'] = self.strategy
            # 把任务的返回推送到 vnpy 的事件处理引擎
            event = Event(type_=EVENT_CTA_TASK)
            event.dict_['data'] = task_ret
            self.ctaEngine.eventEngine.put(event)
            # 阻塞线程，timeout秒后自动释放一次， block_event.Set()后永久释放
            self.block_event.wait(timeout=self.interval)
      

    def taskJob(self):
        """任务的具体执行，需要在派生类中实现，注意返回一个CtaTaskResult对象"""
        raise NotImplementedError
        #return CtaTaskResult()