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
        #self.connectGateway('SHZD')
        # self.connectGateway('CTP')
        #self.connectGateway('OANDA')


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
    repAddress = 'tcp://*:2017'   # port
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

