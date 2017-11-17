# encoding: utf-8

import json
from Queue import Queue, Empty
from threading import Thread
import threading
from datetime import datetime,timedelta
import time
import copy
import pprint

from oandapyV20 import API
from oandapyV20.exceptions import V20Error, StreamTerminated
from oandapyV20.endpoints.pricing import PricingStream
from requests.exceptions import ConnectionError

# 状态机基类, 抽象类
class State(object):

    def new_state(self, new_state_class):
        self.__class__ = new_state_class
        #调用new_state的OnEnterState, 顺序不能变
        self.onEnterState()
    def onEnterState(self):
        raise NotImplementedError


# Oanda接口定义
class OandaApi(State):
    """"""
    DEBUG = False
    def onEnterState(self):
        #print 'OANDA API INSTANCE CREATED'
        pass
    #----------------------------------------------------------------------
    def __init__(self, spi):
        """Constructor"""
        self.active = False
        self.started = False
        # Inject spi object
        if spi:
            self.spi = spi
        else:
            self.spi = OandaSpi(self)
        self.token = ''
        self.accountId = ''
        self.v20_api = None
        self.reqQueue = Queue()     # 请求队列
        self.reqThread = Thread(target=self.processQueue)   # 请求处理线程
        self.streamPricesThread = Thread(target=self.processStreamPrices)   # 实时行情线程
        self.streamEventsThread = Thread(target=self.processStreamEvents)   # 实时事件线程（成交等）
        self.subscribed_symbols = []

        self.new_state(self.__class__)
    #----------------------------------------------------------------------
    def init(self, settingName, token, accountId):
        """初始化接口"""
        self.token = token
        self.accountId = accountId
        self.v20_api = API(access_token=token,
                            environment=settingName,
                            request_params={})

        self.active = True
        self.reqThread.start()
        # Original State ----> InitedState
        
        self.new_state(InitedState)
    #----------------------------------------------------------------------
    def isNormalState(self):
        return self.__class__ == NormalState
    #----------------------------------------------------------------------
    def subscribe(self, symbols_list):
        """订阅行情"""
        for item in symbols_list:
            if item not in self.subscribed_symbols:
                self.subscribed_symbols.append(item)
        #print 'subscribe:', self.subscribed_symbols
        
    #----------------------------------------------------------------------
    def sendRequest(self, req, callback):
        req_in_queue = {'req':req, 'callback':callback}
        self.reqQueue.put(req_in_queue)
    #----------------------------------------------------------------------
    def processQueue(self):
        """处理请求队列中的请求"""
        while self.active:
            try:
                req = self.reqQueue.get(block=True, timeout=1)  # 获取请求的阻塞为一秒
                callback = req['callback']
                reqID = req['reqID']

                r, error = self.sendRequest(req)
                rc = copy.copy(r)

                if r:
                    try:
                        data = rc.json()
                                                
                        if self.DEBUG:
                            print callback.__name__                        
                        callback(data, reqID)    
                    except Exception, e:
                        if self.spi:                  
                            self.spi.onError(str(e), reqID)                      
                else:
                    if self.spi:                
                        self.spi.onError(error, reqID)
            except Empty:
                pass
        print 'Thread Exit'

    #----------------------------------------------------------------------
    def processStreamPrices(self):
        """获取价格推送"""
        # 未订阅
        symbols = self.subscribed_symbols
        if not symbols:
            #print 'exit price stream thread'
            return
        
        req = PricingStream(accountID=self.accountId,
                            params={'instruments':','.join(symbols)})

        resp = self.v20_api.request(req)
        
        if resp:
            try:
                for line in resp:
                    if line:
                        if self.DEBUG:
                            print self.onPrice.__name__
                        if line['type'] == 'PRICE':
                            if self.spi:
                                self.spi.onPrice(line)
                        else:
                            if self.spi:
                                self.spi.onHeartbeat(line)
                    if not self.active or not self.started:
                        break
            except V20Error as e:
                self.new_state(BrokenState)
                if self.spi:
                    self.spi.onError(e, -1)
                #print 'exit price stream thread'
                return
            except ConnectionError as e:
                self.new_state(BrokenState)
                if self.spi:
                    self.spi.onError(e, -1)
                #print 'exit price stream thread'
                return
            except StreamTerminated as e:
                self.new_state(BrokenState)
                if self.spi:
                    self.spi.onError(e, -1)
                #print 'exit price stream thread'
                return
            except Exception as e:
                self.new_state(BrokenState)
                if self.spi:
                    self.spi.onError(e, -1)
                #print 'exit price stream thread'
                return
        else:
            if self.spi:
                self.spi.onError(error, -1)
        #print 'exit price stream thread'
    #----------------------------------------------------------------------
    def processQueue(self):
        """处理请求队列中的请求"""
        pass

    #----------------------------------------------------------------------
    def processStreamEvents(self):
        """获取事件推送"""
        #print 'exit events stream thread'
        pass

    #----------------------------------------------------------------------
    def start(self):
        """启动接口"""
        pass
    #----------------------------------------------------------------------
    def stop(self):
        """停止Stream线程"""
        pass
    #----------------------------------------------------------------------
    def exit(self):
        """退出接口"""
        pass
    #----------------------------------------------------------------------
    def qryInstruments(self):
        """查询所有合约"""
        pass
    #----------------------------------------------------------------------
    def qryOrders(self):
        """查询委托"""
        pass
    #----------------------------------------------------------------------
    def qryTrades(self):
        """查询成交"""
        pass    
    #----------------------------------------------------------------------
    def getInstruments(self, params):
        """查询可交易的合约列表"""
        pass
    #----------------------------------------------------------------------
    def getPrices(self, params):
        """查询价格"""
        pass
    #----------------------------------------------------------------------
    def getPriceHisory(self, params):
        """查询历史价格数据"""
        pass
    #----------------------------------------------------------------------
    def getAccounts(self):
        """查询用户的所有账户"""
        pass

    #----------------------------------------------------------------------
    def getAccountInfo(self):
        """查询账户数据"""
        pass
    #----------------------------------------------------------------------
    def getOrders(self, params):
        """查询所有委托"""
        pass

    #----------------------------------------------------------------------
    def sendOrder(self, params):
        """发送委托"""
        pass
    #----------------------------------------------------------------------
    def getOrderInfo(self, optional):
        """查询委托信息"""
        pass
    #----------------------------------------------------------------------
    def modifyOrder(self, params, optional):
        """修改委托"""
        pass
    #----------------------------------------------------------------------
    def getTrades(self, params):
        """查询所有仓位"""
        pass
    #----------------------------------------------------------------------
    def cancelOrder(self, optional):
        """查询委托信息"""
        pass
    
    #----------------------------------------------------------------------
    def getTradeInfo(self, optional):
        """查询仓位信息"""
        pass
    #----------------------------------------------------------------------
    def modifyTrade(self, params, optional):
        """修改仓位"""
        pass
    #----------------------------------------------------------------------
    def closeTrade(self, optional):
        """平仓"""
        pass
    #----------------------------------------------------------------------
    def getPositions(self):
        """查询所有汇总仓位"""
        pass
    #----------------------------------------------------------------------
    def getPositionInfo(self, optional):
        """查询汇总仓位信息"""
        pass
    #----------------------------------------------------------------------
    def closePosition(self, optional):
        """平仓汇总仓位信息"""
        pass
    #----------------------------------------------------------------------
    def getTransactions(self, params):
        """查询所有资金变动"""
        pass
    #----------------------------------------------------------------------
    def getTransactionInfo(self, optional):
        """查询资金变动信息"""
        pass
    #----------------------------------------------------------------------
    def getAccountHistory(self):
        """查询账户资金变动历史"""
        pass
    #----------------------------------------------------------------------
    def getCalendar(self, params):
        """查询日历"""
        pass
    #----------------------------------------------------------------------
    def getPositionRatios(self, params):
        """查询持仓比例"""
        pass
    #----------------------------------------------------------------------
    def getSpreads(self, params):
        """查询所有仓位"""
        pass
    #----------------------------------------------------------------------
    def getCommitments(self, params):
        """查询交易商持仓情况"""
        pass
    #----------------------------------------------------------------------
    def getOrderbook(self, params):
        """查询订单簿"""
        pass


#--------------------------------------------------------------------------
class InitedState(OandaApi):
    def onEnterState(self):
        #print 'OANDA API ENTER INITED STATE'
        self.start()

    def init(self, settingName, token, accountId):
        """初始化接口"""
        #print 'OandaApi already inited.'
    #----------------------------------------------------------------------
    def start(self):
        """启动接口"""
        self.streamPricesThread = Thread(target=self.processStreamPrices)   # 实时行情线程
        self.streamEventsThread = Thread(target=self.processStreamEvents)   # 实时事件线程（成交等）
        self.streamEventsThread.start()
        self.streamPricesThread.start()
        self.started = True
        self.new_state(NormalState)

    
#--------------------------------------------------------------------------
class NormalState(OandaApi):
    def onEnterState(self):
        #print 'OANDA API ENTER NORMAL STATE'
        pass
    #----------------------------------------------------------------------
    def init(self, settingName, token, accountId):
        pass
    #----------------------------------------------------------------------
    def stop(self):
        """停止Stream线程"""
        self.started = False
        self.streamEventsThread.join()
        self.streamPricesThread.join()
        self.streamEventsThread = None
        self.streamEventsThread = None
        self.new_state(InitedState)
    #----------------------------------------------------------------------
    def exit(self):
        """退出接口"""
        self.new_state(EndState)
        pass

    #----------------------------------------------------------------------
    def qryInstruments(self):
        """查询所有合约"""
        pass
    #----------------------------------------------------------------------
    def qryOrders(self):
        """查询委托"""
        pass
    #----------------------------------------------------------------------
    def qryTrades(self):
        """查询成交"""
        pass    
    #----------------------------------------------------------------------
    def getInstruments(self, params):
        """查询可交易的合约列表"""
        pass

    #----------------------------------------------------------------------
    def getPrices(self, params):
        """查询价格"""
        pass
    #----------------------------------------------------------------------
    def getPriceHisory(self, params):
        """查询历史价格数据"""
        pass
    #----------------------------------------------------------------------
    def getAccounts(self):
        """查询用户的所有账户"""
        pass
    #----------------------------------------------------------------------
    def getAccountInfo(self):
        """查询账户数据"""
        pass
    #----------------------------------------------------------------------
    def getOrders(self, params):
        """查询所有委托"""
        pass
    #----------------------------------------------------------------------
    def sendOrder(self, params):
        """发送委托"""
        pass
    #----------------------------------------------------------------------
    def getOrderInfo(self, optional):
        """查询委托信息"""
        pass
    #----------------------------------------------------------------------
    def modifyOrder(self, params, optional):
        """修改委托"""
        pass
    #----------------------------------------------------------------------
    def getTrades(self, params):
        """查询所有仓位"""
        pass
    #----------------------------------------------------------------------
    def cancelOrder(self, optional):
        """查询委托信息"""
        pass
    
    #----------------------------------------------------------------------
    def getTradeInfo(self, optional):
        """查询仓位信息"""
        pass
    #----------------------------------------------------------------------
    def modifyTrade(self, params, optional):
        """修改仓位"""
        pass
    #----------------------------------------------------------------------
    def closeTrade(self, optional):
        """平仓"""
        pass
    #----------------------------------------------------------------------
    def getPositions(self):
        """查询所有汇总仓位"""
        pass
    #----------------------------------------------------------------------
    def getPositionInfo(self, optional):
        """查询汇总仓位信息"""
        pass
    #----------------------------------------------------------------------
    def closePosition(self, optional):
        """平仓汇总仓位信息"""
        pass
    #----------------------------------------------------------------------
    def getTransactions(self, params):
        """查询所有资金变动"""
        pass
    #----------------------------------------------------------------------
    def getTransactionInfo(self, optional):
        """查询资金变动信息"""
        pass
    #----------------------------------------------------------------------
    def getAccountHistory(self):
        """查询账户资金变动历史"""
        pass
    #----------------------------------------------------------------------
    def getCalendar(self, params):
        """查询日历"""
        pass
    #----------------------------------------------------------------------
    def getPositionRatios(self, params):
        """查询持仓比例"""
        pass
    #----------------------------------------------------------------------
    def getSpreads(self, params):
        """查询所有仓位"""
        pass
    #----------------------------------------------------------------------
    def getCommitments(self, params):
        """查询交易商持仓情况"""
        pass
    #----------------------------------------------------------------------
    def getOrderbook(self, params):
        """查询订单簿"""
        pass


#--------------------------------------------------------------------------
class BrokenState(OandaApi):
    max_trial = 50
    current_trial = 0
    last_time = None
    def onEnterState(self):
        print 'OANDA API ENTER BROKEN STATE'
        if self.last_time and (datetime.now() - self.last_time) >= timedelta(seconds=60):
            # 超过60秒重设计数
            self.current_trial = 0
        self.last_time = datetime.now()
        if self.current_trial < self.max_trial:
            print 'Try reconnecting... #', self.current_trial
            self.current_trial = self.current_trial + 1
            time.sleep(1)
            self.stop()
        else:
            print 'Max reconnection trial number exceeded. Close API...'
            self.exit()

    #----------------------------------------------------------------------
    def stop(self):
        """停止Stream线程"""
        self.started = False
        #self.streamEventsThread.join()
        #self.streamPricesThread.join()
        self.streamEventsThread = None
        self.streamEventsThread = None
        self.new_state(InitedState)
    #----------------------------------------------------------------------
    def exit(self):
        """退出接口"""
        self.new_state(EndState)
        pass
   


#--------------------------------------------------------------------------
class EndState(OandaApi):
    def onEnterState(self):
        #print 'OANDA API ENDSTATE'
        self.started = False
        self.active = False
        #self.reqThread.join()
        #self.streamEventsThread.join()
        #self.streamPricesThread.join()
        self.streamEventsThread = None
        self.streamEventsThread = None
        self.spi = None
        print u"OANDA API 退出"
        pass


########################################################################

class OandaSpi(object):
    def __init__(self, api):
        self.api = api
    #----------------------------------------------------------------------
    def onError(self, error, reqID):
        """错误信息回调"""
        print error, reqID
    #----------------------------------------------------------------------
    def onGetInstruments(self, data, reqID):
        """回调函数"""
        print 'onGetInstruments',data
        pass
   #----------------------------------------------------------------------
    def onGetPrices(self, data, reqID):
        """回调函数"""
        pass
   #----------------------------------------------------------------------
    def onGetPriceHistory(self, data, reqID):
        """回调函数"""
        pass    
    #----------------------------------------------------------------------
    def onGetAccounts(self, data, reqID):
        """回调函数"""
        pass   
    #----------------------------------------------------------------------
    def onGetAccountInfo(self, data, reqID):
        """回调函数"""
        pass   
    #----------------------------------------------------------------------
    def onGetOrders(self, data, reqID):
        """回调函数"""
        pass     

    #----------------------------------------------------------------------
    def onSendOrder(self, data, reqID):
        """回调函数"""
        pass         
    #----------------------------------------------------------------------
    def onGetOrderInfo(self, data, reqID):
        """回调函数"""
        pass     
    #----------------------------------------------------------------------
    def onModifyOrder(self, data, reqID):
        """回调函数"""
        pass      
    #----------------------------------------------------------------------
    def onCancelOrder(self, data, reqID):
        """回调函数"""
        pass     
    #----------------------------------------------------------------------
    def onGetTrades(self, data, reqID):
        """回调函数"""
        pass     
    #----------------------------------------------------------------------
    def onGetTradeInfo(self, data, reqID):
        """回调函数"""
        pass     
    #----------------------------------------------------------------------
    def onModifyTrade(self, data, reqID):
        """回调函数"""
        pass      
    #----------------------------------------------------------------------
    def onCloseTrade(self, data, reqID):
        """回调函数"""
        pass         

    #----------------------------------------------------------------------
    def onGetPositions(self, data, reqID):
        """回调函数"""
        pass  
    #----------------------------------------------------------------------
    def onGetPositionInfo(self, data, reqID):
        """回调函数"""
        pass         

    #----------------------------------------------------------------------
    def onClosePosition(self, data, reqID):
        """回调函数"""
        pass      
    #----------------------------------------------------------------------
    def onGetTransactions(self, data, reqID):
        """回调函数"""
        pass  
    #----------------------------------------------------------------------
    def onGetTransactionInfo(self, data, reqID):
        """回调函数"""
        pass   
    #----------------------------------------------------------------------
    def onGetAccountHistory(self, data, reqID):
        """回调函数"""
        pass      
    #----------------------------------------------------------------------
    def onGetCalendar(self, data, reqID):
        """回调函数"""
        pass       
    #----------------------------------------------------------------------
    def onGetPositionRatios(self, data, reqID):
        """回调函数"""
        pass  
    #----------------------------------------------------------------------
    def onGetSpreads(self, data, reqID):
        """回调函数"""
        pass       
    #----------------------------------------------------------------------
    def onGetCommitments(self, data, reqID):
        """回调函数"""
        pass       
    #----------------------------------------------------------------------
    def onGetOrderbook(self, data, reqID):
        """回调函数"""
        pass       
        
    
    #----------------------------------------------------------------------
    def onGetAutochartist(self, data, reqID):
        """回调函数"""
        pass   
        
    #----------------------------------------------------------------------
    def onPrice(self, data):
        """行情推送"""
        print data
    
    def onHeartbeat(self, data):
        """心跳推送"""
        pass
    #----------------------------------------------------------------------
    def onEvent(self, data):
        """事件推送（成交等）"""
        print data
    
