# encoding: UTF-8


from __future__ import division

import shelve
import json
import cPickle
import os
import traceback
from collections import OrderedDict
from datetime import datetime, timedelta,time

from ctaBase import *
from strategy import STRATEGY_CLASS
from eventEngine import *
from vtConstant import *
from vtGateway import VtSubscribeReq, VtOrderReq, VtCancelOrderReq, VtLogData, VtBalanceData
from vtFunction import todayDate


import numpy as np
import pandas as pd
from pandas import Series, DataFrame
from business_calendar import Calendar

#############################################
class CtaEngine2(object):
    """CTA Strategy Engine for Single-Strategy-Multi-Symbol use"""
    settingFileName = 'CTA_setting2.json'
    path = os.path.abspath(os.path.dirname(__file__))
    settingFileName = os.path.join(path, settingFileName)

    #-------------------------------------------------------------
    def __init__(self, mainEngine, eventEngine):
        """Constructor"""
        self.mainEngine = mainEngine
        self.eventEngine = eventEngine
        
       
        # 当前日期
        self.today = todayDate()
        
        # 保存策略实例的字典
        # key为策略名称，value为策略实例，注意策略名称不允许重复
        self.strategyDict = {}
        
        # 保存vtSymbol和策略实例映射的字典（用于推送tick数据）
        # 由于可能多个strategy交易同一个vtSymbol，因此key为vtSymbol
        # value为包含所有相关strategy对象的list
        self.tickStrategyDict = {}
        
        
        # 保存vtOrderID和strategy对象映射的字典（用于推送order和trade数据）
        # key为vtOrderID，value为strategy对象
        self.orderStrategyDict = {}     

        # 保存vtOrderID和在order上关联的信息 （发单时任意填写的信息，用于保存到数据库，方便分析）
        self.orderAppendInfoDict = {}

        #保存gatewayName和strategy对象映射的字典，用于推送balance数据
        self.gatewayNameStrategyDict = {}

        #保存task和strategy对象映射的字典，用于推送task数据
        self.taskStrategyDict = {}
        
        # 本地停止单编号计数
        self.stopOrderCount = 0
        # stopOrderID = STOPORDERPREFIX + str(stopOrderCount)
        
        # 本地停止单字典
        # key为stopOrderID，value为stopOrder对象
        self.stopOrderDict = {}             # 停止单撤销后不会从本字典中删除
        self.workingStopOrderDict = {}      # 停止单撤销后会从本字典中删除
        
        # 预埋单集合
        self.parkedOrderSet = set()
        self.workingParkedOrderSet = set()
        # key为parkedOrderID, value为vtOrderID
        self.parkedOrderMap = {}

        # 持仓缓存字典
        # key为vtSymbol，value为PositionBuffer对象
        self.posBufferDict = {}
        
        # 成交号集合，用来过滤已经收到过的成交推送
        self.tradeSet = set()
        
        # 引擎类型为实盘
        self.engineType = ENGINETYPE_TRADING
        
        # 注册事件监听
        self.registerEvent()

    #-------------------------------------------------------------
    def getPosition(self, vtSymbol):
        """返回longToday, longYd, shortToday, shortYd"""
        posBuffer = self.posBufferDict.get(vtSymbol, None)
        if not posBuffer:
            pmEngine = self.mainEngine.pmEngine
            pos = pmEngine.qryPosition(vtSymbol)
            posBuffer = PositionBuffer()
            posBuffer.vtSymbol = vtSymbol
            posBuffer.longYd = pos['longYd']
            posBuffer.longToday = pos['longToday']
            posBuffer.longPosition = posBuffer.longYd + posBuffer.longToday
            posBuffer.shortYd = pos['shortYd']
            posBuffer.shortToday = pos['shortToday']
            posBuffer.shortPosition = posBuffer.shortYd + posBuffer.shortToday
            self.posBufferDict[vtSymbol] = posBuffer

        return [posBuffer.longToday, posBuffer.longYd, posBuffer.shortToday, posBuffer.shortYd]

    #-------------------------------------------------------------
    def sendOrder2(self, vtSymbol, orderType, price, volume, strategy, priceType, kwargs):
        contract = self.mainEngine.getContract(vtSymbol)
        req = VtOrderReq()
        req.symbol = contract.symbol
        req.exchange = contract.exchange
        req.price = self.roundToPriceTick(contract.priceTick, price)
        req.volume = volume
        req.productClass = strategy.productClass
        req.currency = strategy.currency        
        req.priceType = priceType

        #CTA OrderType Map
        if orderType == CTAORDER_BUY:
            req.direction = DIRECTION_LONG
            req.offset = OFFSET_OPEN
        elif orderType == CTAORDER_SELL:
            req.direction = DIRECTION_SHORT
            req.offset = OFFSET_CLOSE
        elif orderType == CTAORDER_SHORT:
            req.direction = DIRECTION_SHORT
            req.offset = OFFSET_OPEN
        elif orderType == CTAORDER_COVER:
            req.direction = DIRECTION_LONG
            req.offset = OFFSET_CLOSE

        if contract.exchange == EXCHANGE_SHFE:
            posBuffer = self.posBufferDict.get(vtSymbol, None)
            if not posBuffer:
                posBuffer = PositionBuffer()
                posBuffer.vtSymbol = vtSymbol
                self.posBufferDict[vtSymbol] = posBuffer
                posBuffer.longToday, posBuffer.longYd, posBuffer.shortToday, posBuffer.shortYd = self.getPosition(vtSymbol)

            if req.direction == DIRECTION_LONG:
                print 'long'
                if posBuffer.shortYd >= req.volume:
                    print 'close shortYd'
                    req.offset = OFFSET_CLOSE
                else:
                    print 'open today'
                    req.offset = OFFSET_OPEN
            else:
                print 'short'
                if posBuffer.longYd >= req.volume:
                    print 'close longYd'
                    req.offset = OFFSET_CLOSE
                else:
                    print 'open today'
                    req.offset = OFFSET_OPEN

        vtOrderID = self.mainEngine.sendOrder(req, contract.gatewayName)
        self.orderStrategyDict[vtOrderID] = strategy
        if 'append_info' in kwargs:
            print kwargs['append_info']
            self.orderAppendInfoDict[vtOrderID] = kwargs['append_info']
        self.writeCtaLog(u'策略%s发送委托, %s, %s, %s@%s' %(strategy.name, vtSymbol, req.direction, volume, price))
        return vtOrderID

    #-------------------------------------------------------------
    def sendOrder(self, vtSymbol, orderType, price, volume, strategy, priceType, parked, alt, kwargs):
        """send order"""
        if alt:
            return self.sendOrder2(vtSymbol, orderType, price, volume, strategy, priceType, kwargs)
        contract = self.mainEngine.getContract(vtSymbol)
        
        req = VtOrderReq()
        req.symbol = contract.symbol
        req.exchange = contract.exchange
        req.price = self.roundToPriceTick(contract.priceTick, price)
        req.volume = volume
        
        req.productClass = strategy.productClass
        req.currency = strategy.currency        
        
        
        req.priceType = priceType
        
        # CTA委托类型映射
        if orderType == CTAORDER_BUY:
            req.direction = DIRECTION_LONG
            req.offset = OFFSET_OPEN
            
        elif orderType == CTAORDER_SELL:
            req.direction = DIRECTION_SHORT
            
            # 只有上期所才要考虑平今平昨
            if contract.exchange != EXCHANGE_SHFE:
                req.offset = OFFSET_CLOSE
            else:
                # 获取持仓缓存数据
                posBuffer = self.posBufferDict.get(vtSymbol, None)

                # 如果获取持仓缓存失败，则默认平昨
                if not posBuffer:
                    req.offset = OFFSET_CLOSE
                # 否则如果有多头今仓，则使用平今
                elif posBuffer.longToday:
                    print 'close today'
                    req.offset= OFFSET_CLOSETODAY
                # 其他情况使用平昨
                else:
                    print 'close yesterday'
                    req.offset = OFFSET_CLOSE
                
        elif orderType == CTAORDER_SHORT:
            req.direction = DIRECTION_SHORT
            req.offset = OFFSET_OPEN
            
        elif orderType == CTAORDER_COVER:
            req.direction = DIRECTION_LONG
            
            # 只有上期所才要考虑平今平昨
            if contract.exchange != EXCHANGE_SHFE:
                req.offset = OFFSET_CLOSE
            else:
                # 获取持仓缓存数据
                posBuffer = self.posBufferDict.get(vtSymbol, None)

                # 如果获取持仓缓存失败，则默认平昨
                if not posBuffer:
                    req.offset = OFFSET_CLOSE
                # 否则如果有空头今仓，则使用平今
                elif posBuffer.shortToday:
                    print 'close today'
                    req.offset= OFFSET_CLOSETODAY
                # 其他情况使用平昨
                else:
                    print 'close yesterday'
                    req.offset = OFFSET_CLOSE
        if not parked:
            vtOrderID = self.mainEngine.sendOrder(req, contract.gatewayName)
            self.orderStrategyDict[vtOrderID] = strategy
            if 'append_info' in kwargs:
                self.orderAppendInfoDict[vtOrderID] = kwargs['append_info']
        else:
            vtOrderID = self.mainEngine.sendParkedOrder(req, contract.gatewayName)
            po = ParkedOrder()
            po.vtSymbol = vtSymbol
            po.orderType = orderType
            po.price = self.roundToPriceTick(contract.priceTick, price)
            po.volume = volume
            po.strategy = strategy
            po.localOrderID = vtOrderID

            if orderType == CTAORDER_BUY:
                po.direction = DIRECTION_LONG
                po.offset = OFFSET_OPEN
            elif orderType == CTAORDER_SELL:
                po.direction = DIRECTION_SHORT
                po.offset = OFFSET_CLOSE
            elif orderType == CTAORDER_SHORT:
                po.direction = DIRECTION_SHORT
                po.offset = OFFSET_OPEN
            elif orderType == CTAORDER_COVER:
                po.direction = DIRECTION_LONG
                po.offset = OFFSET_CLOSE           
            self.parkedOrderSet.add(po)
            self.workingParkedOrderSet.add(po)

        self.writeCtaLog(u'策略%s发送委托, %s, %s, %s@%s' %(strategy.name, vtSymbol, req.direction, volume, price))
        return vtOrderID

    #-------------------------------------------------------------
    def qryOrder(self, vtOrderID):
        gatewayName = vtOrderID.split('.')[0]
        self.mainEngine.qryOrder(vtOrderID, gatewayName)
        
    #-------------------------------------------------------------
    def cancelOrder(self, vtOrderID):
        order = self.mainEngine.getOrder(vtOrderID)
        if order:
            # check if order still valid, only if valid, cancel order command will be sent
            orderFinished = (order.status==STATUS_ALLTRADED or order.status==STATUS_CANCELLED)
            if not orderFinished:
                req = VtCancelOrderReq()
                req.symbol = order.symbol
                req.exchange = order.exchange
                req.frontID = order.frontID
                req.sessionID = order.sessionID
                req.orderID = order.orderID
                self.mainEngine.cancelOrder(req, order.gatewayName)

    #-------------------------------------------------------------
    def sendStopOrder(self, vtSymbol, orderType, price, volume, strategy):
        self.stopOrderCount += 1
        stopOrderID = STOPORDERPREFIX + str(self.stopOrderCount)

        so = StopOrder()
        so.vtSymbol = vtSymbol
        so.orderType = orderType
        so.price = price
        so.volume = volume
        so.strategy = strategy
        so.stopOrderID = stopOrderID
        so.status = STOPORDER_WAITING

        if orderType == CTAORDER_BUY:
            so.direction = DIRECTION_LONG
            so.offset = OFFSET_OPEN
        elif orderType == CTAORDER_SELL:
            so.direction = DIRECTION_SHORT
            so.offset = OFFSET_CLOSE
        elif orderType == CTAORDER_SHORT:
            so.direction = DIRECTION_SHORT
            so.offset = OFFSET_OPEN
        elif orderType == CTAORDER_COVER:
            so.direction = DIRECTION_LONG
            so.offset = OFFSET_CLOSE           
        
        # 保存stopOrder对象到字典中
        self.stopOrderDict[stopOrderID] = so
        self.workingStopOrderDict[stopOrderID] = so
        
        return stopOrderID

    #------------------------------------------------------
    def cancelStopOrder(self, stopOrderID):
        """撤销停止单"""
        # 检查停止单是否存在
        if stopOrderID in self.workingStopOrderDict:
            so = self.workingStopOrderDict[stopOrderID]
            so.status = STOPORDER_CANCELLED
            del self.workingStopOrderDict[stopOrderID]

    #------------------------------------------------------
    def processStopOrder(self, tick):
        """ stop order trigger check upon market data arrival """
        vtSymbol = tick.vtSymbol

        # check whether symbol is bound to a strategy
        if vtSymbol in self.tickStrategyDict:
            # iterate all pending stop orders, check whether they will be triggered
            for so in self.workingStopOrderDict.values():
                if so.vtSymbol == vtSymbol:
                    longTriggered = so.direction == DIRECTION_LONG and tick.lastPrice >= so.price
                    shortTriggered = so.direction == DIRECTION_SHORT and tick.lastPrice <= so.price

                    if longTriggered or shortTriggered:
                        if so.direction ==  DIRECTION_LONG:
                            price = tick.upperLimit
                        else:
                            price = tick.lowerLimit
                        
                        so.status = STOPORDER_TRIGGERED
                        self.sendOrder(so.vtSymbol, so.orderType, price, so.volume, so.strategy)
                        del self.workingStopOrderDict[so.stopOrderID]
                        ############## more process the other symbols in the basket #############

    #--------------------------------------------------------------
    def processTickEvent(self, event):
        """ Tick Event Router """

        # fetch tick data from event
        tick = event.dict_['data']

        # process pending stop orders
        self.processStopOrder(tick)

        # push tick to corresponding strategy instance
        if tick.vtSymbol in self.tickStrategyDict:
            # data transforming
            ctaTick = CtaTickData()
            d = ctaTick.__dict__
            for key in d.keys():
                if key != 'datetime':
                    d[key] = tick.__getattribute__(key)
            # 添加datetime字段
            try:
                ctaTick.datetime = datetime.strptime(' '.join([tick.date, tick.time]), '%Y%m%d %H:%M:%S.%f')
            except ValueError:
                try:
                    ctaTick.datetime = datetime.strptime(' '.join([tick.date, tick.time]), '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    ctaTick.datetime = datetime.strptime(tick.time, '%Y-%m-%dT%H:%M:%S.%f')
           

            # 逐个推送到策略实例中
            l = self.tickStrategyDict[tick.vtSymbol]
            for strategy in l:
                self.callStrategyFunc(strategy, strategy.onTick, ctaTick)

    #-----------------------------------------------------------------
    def processOrderEvent(self, event):
        """ Order Event """
        order = event.dict_['data']
        order.localtime = datetime.now()
        # import pprint
        # pprint.pprint(order.__dict__)
        if order.vtOrderID in self.orderStrategyDict:
            strategy = self.orderStrategyDict[order.vtOrderID]
            self.callStrategyFunc(strategy, strategy.onOrder, order)
        ###########################################################
        # 处理预埋单触发的情况
        elif order.exchange == EXCHANGE_SHFE and order.sessionID == 0 and order.frontID == 0:
            #print 'ctaEngine: processOrderEvent'
            # 把ParkedOrder加入orderStrategyDict
            #print 'workingParkedOrderSet: ', self.workingParkedOrderSet
            #print 'parkedOrderMap:', self.parkedOrderMap
            for po in self.workingParkedOrderSet:
                if order.vtOrderID not in self.parkedOrderMap:
                    # 尚未匹配， 则与parkedOrder匹配
                    # import pprint
                    # pprint.pprint(order.__dict__)
                    # pprint.pprint(po.__dict__)
                    if po.vtSymbol == order.vtSymbol and po.direction == order.direction and po.offset == order.offset and po.price == order.price and po.volume == order.totalVolume:
                        # vtSymbol, orderType, price, volume均匹配
                        print 'match:', order.vtOrderID, po.strategy.name
                        self.parkedOrderMap[order.vtOrderID] = po
                        self.workingParkedOrderSet.remove(po)
                        order.isParkedTriggered = True
                        order.localOrderID = po.localOrderID
                        self.orderStrategyDict[order.vtOrderID] = po.strategy
                        self.callStrategyFunc(po.strategy, po.strategy.onOrder, order)
                        break
        ############################################################


    #------------------------------------------------------------------
    def processTradeEvent(self, event):
        """ Trade Event """
        trade = event.dict_['data']

        if trade.vtTradeID in self.tradeSet:
            return
        self.tradeSet.add(trade.vtTradeID)

        # push trade data to the strategy
        if trade.vtOrderID in self.orderStrategyDict:
            strategy = self.orderStrategyDict[trade.vtOrderID]

            # calculate strategy position
            if trade.direction == DIRECTION_LONG:
                strategy.pos[trade.vtSymbol] += trade.volume
            else:
                strategy.pos[trade.vtSymbol] -= trade.volume
            self.callStrategyFunc(strategy, strategy.__onTrade__, trade)

        # 更新持仓缓存数据
        if trade.vtSymbol in self.tickStrategyDict:
            posBuffer = self.posBufferDict.get(trade.vtSymbol, None)
            
            if not posBuffer:
                posBuffer = PositionBuffer()
                posBuffer.vtSymbol = trade.vtSymbol
                self.posBufferDict[trade.vtSymbol] = posBuffer
            posBuffer.updateTradeData(trade)

    #-----------------------------------------------------------------
    def processBalanceEvent(self, event):
        balance = event.dict_['data']

        # 逐个推送到策略实例中
        l = self.gatewayNameStrategyDict[balance.gatewayName]
        for strategy in l:
            self.callStrategyFunc(strategy, strategy.onBalance, balance)

    #-----------------------------------------------------------------
    def processPositionEvent(self, event):
        """处理持仓推送"""
        
        pos = event.dict_['data']
        # 更新持仓缓存数据
        if pos.vtSymbol in self.tickStrategyDict:
            posBuffer = self.posBufferDict.get(pos.vtSymbol, None)
            if not posBuffer:
                posBuffer = PositionBuffer()
                posBuffer.vtSymbol = pos.vtSymbol
                self.posBufferDict[pos.vtSymbol] = posBuffer
            posBuffer.updatePositionData(pos)

    #-----------------------------------------------------------------
    def processTaskEvent(self, event):
        task_ret = event.dict_['data']
        strategy = task_ret['strategy']
        task_result = task_ret['result']
        self.callStrategyFunc(strategy, strategy.onTask, task_result)


    #------------------------------------------------------------------
    def registerEvent(self):
        self.eventEngine.register(EVENT_TICK, self.processTickEvent)
        self.eventEngine.register(EVENT_ORDER, self.processOrderEvent)
        self.eventEngine.register(EVENT_TRADE, self.processTradeEvent)  
        self.eventEngine.register(EVENT_BALANCE, self.processBalanceEvent)
        self.eventEngine.register(EVENT_POSITION, self.processPositionEvent)
        self.eventEngine.register(EVENT_CTA_TASK, self.processTaskEvent)

    #----------------------------------------------------------------------
    def insertData(self, dbName, collectionName, data):
        """插入数据到数据库（这里的data可以是CtaTickData或者CtaBarData）"""
        try:
            self.mainEngine.dbInsert(dbName, collectionName, data)
        except:
            pass

    #----------------------------------------------------------------------
    def loadBar(self, dbName, collectionName, days):
        # fetch Bar data from MongoDB
        startDate = self.today - timedelta(days)

        d = {'datetime':{'$gte':startDate}}
        barData = self.mainEngine.dbQuery(dbName, collectionName, d)

        l = []
        for d in barData:
            bar = CtaBarData()
            bar.__dict__ = d
            l.append(bar)
        return l

    #-------------------------------------------------------------------------
    def loadTick(self, dbName, collectionName, days):
        """从数据库中读取Tick数据，startDate是datetime对象"""
        startDate = self.today - timedelta(days)
        d = {'datetime':{'$gte':startDate}}
        tickData = self.mainEngine.dbQuery(dbName, collectionName, d)
        
        l = []
        for d in tickData:
            tick = CtaTickData()
            tick.__dict__ = d
            l.append(tick)
        return l    

    #-------------------------------------------------------------------------
    def loadTickToDataFrame(self, dbName, collectionName, start_time, end_time, where=''):
        """从数据库中读取Tick数据，起始日期为当日前days个工作日"""
       
        l = []
        time = start_time
        window_length = 3
        while time <= end_time:
            q = { 'datetime':{'$gte':time, '$lt':min(end_time, time + timedelta(hours = window_length))} }
            tickData = self.mainEngine.dbQuery(dbName, collectionName, q, where)
            time = time + timedelta(hours = window_length)
            
            for d in tickData:
                tick={}
                tick['datetime'] = d['datetime']
                tick['lastPrice'] = d['lastPrice'] 
                l.append(tick)
            tickData = []

        return DataFrame(l)


    #--------------------------------------------------------------------------
    def writeCtaLog(self, content):
        log = VtLogData()
        log.logContent = content
        event = Event(type_=EVENT_CTA_LOG)
        event.dict_['data'] = log
        self.eventEngine.put(event)

    #--------------------------------------------------------------------------
    def writeWebLog(self, content, strategyName):
        event = Event(type_=EVENT_WEB_LOG)
        d = {}
        d['msg'] = content
        d['strategy'] = strategyName 

        event.dict_['data'] = json.dumps(d)
        self.eventEngine.put(event)

    #--------------------------------------------------------------------------
    def sendChartData(self, content, strategyName):
        event = Event(type_=EVENT_CHART_DATA)
        d = {}
        d['chart'] = content
        d['strategy'] = strategyName

        event.dict_['data'] = json.dumps(d)
        self.eventEngine.put(event)
        
    #--------------------------------------------------------------------------
    def loadStrategy(self, setting): 
        """载入策略"""

        try:
            name = setting['name']
            className = setting['className']
        except Exception, e:
            self.writeCtaLog(u'载入策略出错：%s' %e)
            return
        
        # 获取策略类
        strategyClass2 = STRATEGY_CLASS.get(className, None)
        if not strategyClass2:
            self.writeCtaLog(u'找不到策略类：%s' %className)
            return
        
        # 防止策略重名
        if name in self.strategyDict:
            self.writeCtaLog(u'策略实例重名：%s' %name)
        else:
            # 创建策略实例
            strategy = strategyClass2(self, setting)  
            self.strategyDict[name] = strategy

            # Tick map
            for vtSymbol in strategy.vtSymbols:
                if vtSymbol in self.tickStrategyDict:
                    l = self.tickStrategyDict[vtSymbol]
                else:
                    l = []
                    self.tickStrategyDict[vtSymbol] = l
                l.append(strategy)
                # subscribe
                contract = self.mainEngine.getContract(vtSymbol)
                if contract and not self.getExchange(vtSymbol) in ['SMART','NYMEX','GLOBEX','IDEALPRO','HKEX','HKFE']:
                    req = VtSubscribeReq()
                    req.symbol = contract.symbol
                    req.exchange = contract.exchange
                    req.currency = strategy.currency
                    req.productClass = strategy.productClass
                    self.mainEngine.subscribe(req, contract.gatewayName)
                else:
                    self.writeCtaLog(u'%s的交易合约%s无法找到' %(name, vtSymbol))
                        
            # gatewayNameStrategyMap
            for vtSymbol in strategy.vtSymbols:
                contract = self.mainEngine.getContract(vtSymbol)
                if contract and not self.getExchange in ['SMART','NYMEX','GLOBEX','IDEALPRO','HKEX','HKFE']:
                    gatewayName = contract.gatewayName
                    if gatewayName in self.gatewayNameStrategyDict:
                        l = self.gatewayNameStrategyDict[gatewayName]
                    else:
                        l = []
                        self.gatewayNameStrategyDict[gatewayName] = l
                    l.append(strategy)
            
    #----------------------------------------------------------
    def getExchange(self, vtSymbol):
        """从vtSymbol分解获得交易所信息"""
        str_parts = vtSymbol.split('.')
        if len(str_parts) <= 1:
            return ''
        else:
            return str_parts[-1]
    #----------------------------------------------------------
    def getContract(self,vtSymbol):
        """获取合约信息"""
        return self.mainEngine.getContract(vtSymbol)
    #----------------------------------------------------------
    def initStrategy(self, name):
        """Initiation"""
        if name in self.strategyDict:
            strategy = self.strategyDict[name]
            # 检查接口连接状态
            for vtSymbol in strategy.vtSymbols:
                contract = self.mainEngine.getContract(vtSymbol)
                if contract:
                    if not self.mainEngine.isGatewayConnected(contract.gatewayName):
                        self.writeCtaLog(u'检查接口连接未通过，策略%s不能启动' %name)
                        return

            if not strategy.inited:
                strategy.inited = True
                self.callStrategyFunc(strategy, strategy.__onInit__)
            else:
                self.writeCtaLog(u'请勿重复初始化策略实例: %s' %name)
        else:
            self.writeCtaLog(u'策略实例不存在: %s' %name)
            
    #-----------------------------------------------------------
    def startStrategy(self, name):
        """启动策略"""
        if name in self.strategyDict:
            strategy = self.strategyDict[name]
            
            if strategy.inited and not strategy.trading:
                strategy.trading = True
                self.callStrategyFunc(strategy, strategy.__onStart__)
        else:
            self.writeCtaLog(u'策略实例不存在：%s' %name)


    #----------------------------------------------------------------------
    def stopStrategy(self, name):
        """停止策略"""
        if name in self.strategyDict:
            strategy = self.strategyDict[name]
            
            if strategy.trading:
                strategy.trading = False
                self.callStrategyFunc(strategy, strategy.__onStop__)
                
                # 对该策略发出的所有限价单进行撤单
                for vtOrderID, s in self.orderStrategyDict.items():
                    if s is strategy:
                        self.cancelOrder(vtOrderID)
                
                # 对该策略发出的所有本地停止单撤单
                for stopOrderID, so in self.workingStopOrderDict.items():
                    if so.strategy is strategy:
                        self.cancelStopOrder(stopOrderID)   
        else:
            self.writeCtaLog(u'策略实例不存在：%s' %name)

    #----------------------------------------------------------------------        
    def saveSetting(self):
        """保存策略配置"""
        with open(self.settingFileName, 'w') as f:
            l = []
            
            for strategy in self.strategyDict.values():
                setting = {}
                for param in strategy.paramList:
                    setting[param] = strategy.__getattribute__(param)
                l.append(setting)
            
            jsonL = json.dumps(l, indent=4)
            f.write(jsonL)
            
    #----------------------------------------------------------------------
    def loadSetting(self):
        """读取策略配置"""
        with open(self.settingFileName) as f:
            l = json.load(f)
            
            for setting in l:
                self.loadStrategy(setting)

    #----------------------------------------------------------------------
    def getStrategyVar(self, name):
        """获取策略当前的变量字典"""
        if name in self.strategyDict:
            strategy = self.strategyDict[name]
            varDict = OrderedDict()
            
            for key in strategy.varList:
                varDict[key] = strategy.__getattribute__(key)
            
            return varDict
        else:
            self.writeCtaLog(u'策略实例不存在：' + name)    
            return None
    
    #----------------------------------------------------------------------
    def getStrategyParam(self, name):
        """获取策略的参数字典"""
        if name in self.strategyDict:
            strategy = self.strategyDict[name]
            paramDict = OrderedDict()
            
            for key in strategy.paramList:  
                paramDict[key] = strategy.__getattribute__(key)
            
            return paramDict
        else:
            self.writeCtaLog(u'策略实例不存在：' + name)    
            return None   
        
    #----------------------------------------------------------------------
    def putStrategyEvent(self, name):
        """触发策略状态变化事件（通常用于通知GUI更新）"""
        event = Event(EVENT_CTA_STRATEGY+name)
        self.eventEngine.put(event)
        
    #----------------------------------------------------------------------
    def callStrategyFunc(self, strategy, func, params=None):
        """调用策略的函数，若触发异常则捕捉"""
        try:
            if params:
                func(params)
            else:
                func()
        except Exception:
            # 停止策略，修改状态为未初始化
            strategy.trading = False
            self.callStrategyFunc(strategy, strategy.__onStop__)
            strategy.inited = False
            
            # 发出日志
            content = '\n'.join([u'策略%s触发异常已停止' %strategy.name,
                                traceback.format_exc()])
            self.writeCtaLog(content)
            
    #----------------------------------------------------------------------
    def savePosition(self):
        """保存所有策略的持仓情况到数据库"""
        for strategy in self.strategyDict.values():
            for vtSymbol in strategy.vtSymbols:
                flt = {'name': strategy.name,
                    'vtSymbol': vtSymbol}
                
                d = {'name': strategy.name,
                    'vtSymbol': vtSymbol,
                    'pos': strategy.pos[vtSymbol]}
                
                self.mainEngine.dbUpdate(POSITION_DB_NAME, strategy.className,
                                        d, flt, True)
            
            content = '策略%s持仓保存成功' %strategy.name
            self.writeCtaLog(content)
    
    #----------------------------------------------------------------------
    def loadPosition(self):
        """从数据库载入策略的持仓情况"""
        for strategy in self.strategyDict.values():
            for vtSymbol in strategy.vtSymbols:
                flt = {'name': strategy.name,
                    'vtSymbol': vtSymbol}
                posData = self.mainEngine.dbQuery(POSITION_DB_NAME, strategy.className, flt)
                
                for d in posData:
                    strategy.pos[vtSymbol] = d['pos']


    #----------------------------------------------------------------------
    def roundToPriceTick(self, priceTick, price):
        """取整价格到合约最小价格变动"""
        if not priceTick:
            return price
        
        newPrice = round(price/priceTick, 0) * priceTick
        return newPrice    


###########################################################################

class PositionBuffer(object):
    """持仓缓存信息（本地维护的持仓数据）"""

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.vtSymbol = EMPTY_STRING
        
        # 多头
        self.longPosition = EMPTY_INT
        self.longToday = EMPTY_INT
        self.longYd = EMPTY_INT
        
        # 空头
        self.shortPosition = EMPTY_INT
        self.shortToday = EMPTY_INT
        self.shortYd = EMPTY_INT
        
    #----------------------------------------------------------------------

    def updatePositionData(self, pos):
        """更新持仓数据"""
        if pos.direction == DIRECTION_LONG:
            self.longPosition = pos.position
            self.longYd = pos.ydPosition
            self.longToday = self.longPosition - self.longYd
        else:
            self.shortPosition = pos.position
            self.shortYd = pos.ydPosition
            self.shortToday = self.shortPosition - self.shortYd

        

    #----------------------------------------------------------------------
    def updateTradeData(self, trade):
        """更新成交数据"""
        
        if trade.direction == DIRECTION_LONG:
            # 多方开仓，则对应多头的持仓和今仓增加
            if trade.offset == OFFSET_OPEN:
                self.longPosition += trade.volume
                self.longToday += trade.volume
            # 多方平今，对应空头的持仓和今仓减少
            elif trade.offset == OFFSET_CLOSETODAY:
                self.shortPosition -= trade.volume
                self.shortToday -= trade.volume
                print 'shortToday --'
            # 多方平昨，对应空头的持仓和昨仓减少
            else:
                self.shortPosition -= trade.volume
                self.shortYd -= trade.volume
        else:
            # 空头和多头相同
            if trade.offset == OFFSET_OPEN:
                self.shortPosition += trade.volume
                self.shortToday += trade.volume
                print 'shortToday ++'
            elif trade.offset == OFFSET_CLOSETODAY:
                self.longPosition -= trade.volume
                self.longToday -= trade.volume
            else:
                self.longPosition -= trade.volume
                self.longYd -= trade.volume