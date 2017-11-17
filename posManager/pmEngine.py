# encoding: UTF-8

'''
本文件中实现了下单以及成交数据记录引擎，用于记录汇总下单以及成交数据到数据库。
提供按策略计算持仓和资金的函数接口
'''

import json
import os
from copy import copy
from collections import OrderedDict
from datetime import datetime, timedelta
from Queue import Queue
from threading import Thread

from eventEngine import *
from vtGateway import VtLogData
from pmBase import *
from vtFunction import todayDate
from vtConstant import *

#######################################################################################
class PmEngine(object):
    """本地仓位管理引擎"""

    settingFileName = 'PM_setting.json'
    path = os.path.abspath(os.path.dirname(__file__))
    settingFileName = os.path.join(path, settingFileName)

    #-------------------------------------------------------
    def __init__(self, mainEngine, eventEngine):
        self.mainEngine = mainEngine
        self.ctaEngine = mainEngine.ctaEngine
        self.eventEngine = eventEngine

        # 当前日期
        self.today = todayDate()

        # Order 对象字典
        self.orderDict = {}

        # Trade 对象字典
        self.tradeDict = {}

        # 复制执行数据库插入的单独线程相关
        self.active = False                     #工作状态
        self.queue = Queue()                    #队列
        self.thread = Thread(target=self.run)   #线程

        # 载入设置
        self.loadSetting()

        # vtSymbol_pmColletionName_map
        self.vtSymbol_pmColletionName_map = {}



    #-------------------------------------------------------
    def loadSetting(self):
        """载入设置"""
        with open(self.settingFileName) as f:
            pmSetting = json.load(f)

            # 如果working设置为False则不启动持仓管理功能
            working = pmSetting['working']
            if not working:
                return

            # 启动数据插入线程
            self.start()
            self.mainEngine.writeLog(u'委托/成交记录入库功能已开启') 
            # 注册事件监听
            self.registerEvent()

    #-----------------------------------------------------
    def getCollectionName(self, vtSymbol):
        if vtSymbol in self.vtSymbol_pmColletionName_map:
            return self.vtSymbol_pmColletionName_map[vtSymbol]
        gateway = self.mainEngine.getGateway(vtSymbol)
        gatewayName = gateway.gatewayName
        gatewaySetting = gateway.getGatewaySetting()
        userID = gatewaySetting.get('userID')
        if not userID:
            userID = gatewaySetting.get('userId')
        collectionName = '%s-%s'%(gatewayName, userID)
        self.vtSymbol_pmColletionName_map[vtSymbol] = collectionName
        return collectionName

    #------------------------------------------------------
    def processOrderEvent(self, event):
        """处理委托推送"""
        order = event.dict_['data']
        strategy = self.ctaEngine.orderStrategyDict.get(order.vtOrderID, None)
        append_info = self.ctaEngine.orderAppendInfoDict.get(order.vtOrderID, None)
        if strategy:
            order.strategy = strategy.name
            order.info = append_info
        order.localtime = datetime.now()
        self.insertData(ORDER_DB_RAW_NAME, self.getCollectionName(order.vtSymbol), order)

        order = copy(order)
        order._id = order.vtOrderID
        # CTP
        if order.gatewayName == 'CTP':
            order._id = '.'.join([order._id, str(order.frontID), str(order.sessionID)])
        # 更新Order数据
        self.insertData(ORDER_DB_NAME, self.getCollectionName(order.vtSymbol), order)

    #------------------------------------------------------
    def processTradeEvent(self, event):
        """处理成交推送"""
        trade = event.dict_['data']
        strategy = self.ctaEngine.orderStrategyDict.get(trade.vtOrderID, None)
        append_info = self.ctaEngine.orderAppendInfoDict.get(trade.vtOrderID, None)
        if strategy:
            trade.strategy = strategy.name
            trade.info = append_info
        trade.localtime = datetime.now()
        self.insertData(TRADE_DB_RAW_NAME, self.getCollectionName(trade.vtSymbol), trade)
        trade = copy(trade)
        # 更新Trade数据
        trade._id = {'vtOrderID':trade.vtOrderID, 'vtTradeID':trade.vtTradeID}
        self.insertData(TRADE_DB_NAME, self.getCollectionName(trade.vtSymbol), trade)
        

    #------------------------------------------------------
    def processPositionEvent(self, event):
        pos = event.dict_['data']
        pos._id = {'vtSymbol': pos.vtSymbol, 'direction': pos.direction}
        pos.localtime = datetime.now()
        self.insertData(POS_DB_NAME, self.getCollectionName(pos.vtSymbol), pos)
    #------------------------------------------------------
    def registerEvent(self):
        """注册事件监听"""
        self.eventEngine.register(EVENT_ORDER, self.processOrderEvent)
        self.eventEngine.register(EVENT_TRADE, self.processTradeEvent)
        self.eventEngine.register(EVENT_POSITION, self.processPositionEvent)
        
    #------------------------------------------------------
    def insertData(self, dbName, collectionName, data):
        """插入数据到数据库，可以是order/trade"""
        self.queue.put((dbName, collectionName, data.__dict__))

    #------------------------------------------------------
    def run(self):
        """运行插入线程"""
        while self.active:
            try:
                dbName, collectionName, d = self.queue.get(block=True, timeout=1)
                self.mainEngine.dbInsert(dbName, collectionName, d)
            except Empty:
                pass
    #-------------------------------------------------------
    def start(self):
        """启动"""
        self.active = True
        self.thread.start()

    def stop(self):
        """退出"""
        if self.active:
            self.active = False
            self.thread.join()

    #--------------------------------------------------------
    def qryPosition(self, vtSymbol):
        where = ''
        cursor = self.mainEngine.dbQuery(POS_DB_NAME, 
                                self.getCollectionName(vtSymbol),
                                {'symbol':vtSymbol}, where)
        pos = {'vtSymbol':vtSymbol, 'longYd':0, 'longToday':0, 'shortYd':0, 'shortToday':0}

        for item in cursor:
            if datetime.now() - item['localtime'] > timedelta(seconds=60):
                continue
            if item['direction'] == DIRECTION_LONG:
                pos['longYd'] = item['ydPosition']
                pos['longToday'] = item['position'] - item['ydPosition']
            elif item['direction'] == DIRECTION_SHORT:
                pos['shortYd'] = item['ydPosition']
                pos['shortToday'] = item['position'] - item['ydPosition']
        return pos
