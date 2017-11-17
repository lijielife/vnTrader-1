# encoding: utf-8

from datetime import datetime, timedelta
import vtPath
from vtEngine import MainEngine
from ctaBase import *
from ctaStrategy import ctaEngine2
from gateway import GATEWAY_DICT
from vnrpc import RpcServer

from threading import Thread
import threading
import time


# class Task(object):
#     def __init__(self, target_time):
#         # 任务线程
#         self._thread = Thread(target=self.__run__)
#         # 任务执行的时间
#         self.target_time = target_time
#         # 线程 Event
#         self.block_event = threading.Event()
#         self.active = False

#     def __del__(self):
#         self.stop()

#     def start(self):
#         """开始执行Task"""
#         self._thread.start()
#         self.active = True

#     def stop(self):
#         """停止执行Task"""
#         # Event 设为 set, 解除线程阻塞
#         self.active = False
#         self.block_event.set()

#     def __run__(self):
#         # 任务执行
#         now_time = datetime.now()
#         delta = (self.target_time - now_time).seconds
#         print delta
#         # 阻塞线程，timeout秒后自动释放一次， block_event.Set()后永久释放
#         while self.active:
#             self.block_event.wait(timeout=delta)
#             # 执行 taskJob
#             self.taskJob()
#             #执行过一次之后将delta重设
#             self.target_time = self.target_time + timedelta(days=1)
#             delta = (self.target_time - datetime.now()).seconds
        
#     def taskJob(self):
#         """任务的具体执行"""
#         raise NotImplementedError
# #-------------------------------------------------------------------
# class CloseCtpTask(Task):
#     mainEngine = None
#     def __init__(self, time, mainEngine):
#         super(CloseCtpTask, self).__init__(time)
#         self.mainEngine = mainEngine
#     def taskJob(self):
#         print 'close ctp'
#         self.mainEngine.disconnect('CTP')
#         print "CTP closed."

# class ConnectCtpTask(Task):
#     mainEngine = None
#     def __init__(self, time, mainEngine):
#         super(ConnectCtpTask, self).__init__(time)
#         self.mainEngine = mainEngine
#     def taskJob(self):
#         print 'connect ctp'
#         try:
#             self.mainEngine.connect('CTP')
#         except Exception as e:
#             print e
#         else:
#             print 'Reconnect CTP, Done!'




#-------------------------------------------------------------------
class AppServer(RpcServer):
    def __init__(self, repAddress, pubAddress):
        super(AppServer, self).__init__(repAddress, pubAddress)
        self.usePickle()

        # create the app object
        self.app = App()

        # register App class methods as RPC Functions in the server
        self.register(self.app.quit)
        self.register(self.app.initStrategy)
        self.register(self.app.startStrategy)
        self.register(self.app.stopStrategy)
        self.register(self.stopServer)
        self.register(self.app.changeParameters)
        self.register(self.app.loadDrSetting)

        

    def stopServer(self):
        self.stop()

#-------------------------------------------------------------------
class App(object):


    def __init__(self):
        self.mainEngine = MainEngine()
        self.ctaEngine = self.mainEngine.ctaEngine
        self.drEngine = self.mainEngine.drEngine
        self.gatewayConnectedDict = {}
        self.strategyInited = False
        self.strategyStarted = False
        self.mainEngine.writeLog("MainEngine Started.") 
        self.connectGateway('SHZD')
        self.connectGateway('CTP')
        self.connectGateway('OANDA')
        #self.connectGateway('IB')

        # time.sleep(5)
        # self.mainEngine.disconnect('CTP')
        # self.connectGateway('CTP')


        # #定时任务启动
        # #当日20：30
        # target_time = datetime.today().replace(hour=15,minute=00,second=0,microsecond=0)
        # self._closeCtpTask = CloseCtpTask(target_time, self.mainEngine)
        # #一分钟后重连CTP
        # self._connectCtpTask = ConnectCtpTask(target_time + timedelta(minutes=1), self.mainEngine)
        # self._closeCtpTask.start()
        # self._connectCtpTask.start()


    def quit(self):
        try:
            self.mainEngine.exit()
        except Exception, e:
            pass
        else:
            self.mainEngine.writeLog('Quit Successfully, type \'exit\' to stop server') 

    def changeParameters(self, strategyName, para):
        try:
            strategy = self.ctaEngine.strategyDict[strategyName]
            for key in para.keys():
                strategy.__dict__[key] = para[key]
                self.mainEngine.writeLog("Parameter changed: %s = %r" %(key, para[key]))
        except:
            return

    def loadDrSetting(self):
        try:
            self.drEngine.loadSetting()
        except Exception, e:
            print e

    def initStrategy(self):
        if not self.strategyInited:
            try:
                self.ctaEngine.loadSetting()
                for name in self.ctaEngine.strategyDict.keys():
                    self.ctaEngine.initStrategy(name)
            except Exception, e:
                print e
            else:
                self.strategyInited = True

    def startStrategy(self):
        if not self.strategyStarted:
            try:
                for name in self.ctaEngine.strategyDict.keys():
                    self.ctaEngine.startStrategy(name)
            except Exception, e:
                print e
            else:
                self.strategyStarted = True

    def stopStrategy(self):
        if self.strategyStarted:
            try:
                for name in self.ctaEngine.strategyDict.keys():
                    self.ctaEngine.stopStrategy(name)
            except Exception, e:
                print e
            else:
                self.strategyStarted = False

    def connectGateway(self, gateway_name):        
        gateway = GATEWAY_DICT[gateway_name]
        if self.gatewayConnectedDict.has_key(gateway.gatewayName) == False:
            #printLog("Connecting to %s" %gateway_name) 
            try:
                self.mainEngine.connect(gateway.gatewayName)
            except Exception, e:
                print e
            else:
                self.gatewayConnectedDict[gateway.gatewayName] = True
                #printLog("Done!" ) 


#--------------------------------------------------------------

#----------------------------------------------------------------------
def runServer():
    repAddress = 'tcp://*:2017'
    pubAddress = 'tcp://*:0616'
    
    # start server
    server = AppServer(repAddress, pubAddress)
    server.start()

    mainEngine = server.app.mainEngine
    mainEngine.writeLog(u'vn.trader服务器已启动')

    
    
    while True:
        cmd = raw_input()
        if cmd == 'exit':
            server.stop()
            break
    mainEngine.writeLog(u'vn.trader服务器已停止') 

    
if __name__ == '__main__':
    runServer()

