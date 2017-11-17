# encoding: UTF-8

'''
vn.oanda的gateway接入

由于OANDA采用的是外汇做市商的交易模式，因此和国内接口方面有若干区别，具体如下：

* 行情数据反映的是OANDA的报价变化，因此只有买卖价，而没有成交价

* OANDA的持仓管理分为单笔成交持仓（Trade数据，国内没有）
  和单一资产汇总持仓（Position数据）
  
* OANDA系统中的所有时间都采用UTC时间（世界协调时，中国是UTC+8）

* 由于采用的是外汇做市商的模式，用户的限价委托当价格被触及时就会立即全部成交，
  不会出现部分成交的情况，因此委托状态只有已报、成交、撤销三种
  
* 外汇市场采用24小时交易，因此OANDA的委托不像国内收盘后自动失效，需要用户指定
  失效时间，本接口中默认设置为24个小时候失效
'''


import os
import json
import datetime
import pprint

from vnoandaV20 import OandaApi,OandaSpi
from vtGateway import *

# 价格类型映射
priceTypeMap = {}
priceTypeMap[PRICETYPE_LIMITPRICE] = 'limit'
priceTypeMap[PRICETYPE_MARKETPRICE] = 'market'
priceTypeMapReverse = {v: k for k, v in priceTypeMap.items()} 

# 方向类型映射
directionMap = {}
directionMap[DIRECTION_LONG] = 'buy'
directionMap[DIRECTION_SHORT] = 'sell'
directionMapReverse = {v: k for k, v in directionMap.items()}


########################################################################
class OandaGateway(VtGateway):
    """OANDA接口"""

    #----------------------------------------------------------------------
    def __init__(self, eventEngine, gatewayName='OANDA'):
        """Constructor"""
        super(OandaGateway, self).__init__(eventEngine, gatewayName)
        
        self.api = Api(self)     
        
        self.qryEnabled = False         # 是否要启动循环查询
        
        self.subscribed_symbols = []
    #----------------------------------------------------------------------
    def connect(self):
        """连接"""
        # 载入json文件
        fileName = self.gatewayName + '_connect.json'
        path = os.path.abspath(os.path.dirname(__file__))
        fileName = os.path.join(path, fileName)
        
        try:
            f = file(fileName)
        except IOError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'读取连接配置出错，请检查'
            self.onLog(log)
            return
        
        # 解析json文件
        setting = json.load(f)
        try:
            token = str(setting['token'])
            accountId = str(setting['accountId'])
            settingName = str(setting['settingName'])
        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'连接配置缺少字段，请检查'
            self.onLog(log)
            return            
        
        # 初始化接口
        self.api.init(settingName, token, accountId)
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = u'接口初始化成功'
        self.onLog(log)

        # 查询信息
        self.api.qryInstruments()
        self.api.qryOrders()
        self.api.qryTrades()
        
        # 初始化并启动查询
        self.initQuery()
    
    def isConnected(self):
        return self.api.isNormalState()
    #----------------------------------------------------------------------
    def subscribe(self, subscribeReq):
        """订阅行情"""
        self.api.subscribe([subscribeReq.symbol])
        # api主动调用stop之后进入InitedState, 之后会自动进入NormalState
        self.api.stop()
        
    #----------------------------------------------------------------------
    def sendOrder(self, orderReq):
        """发单"""
        return self.api.sendOrder_(orderReq)
        
    #----------------------------------------------------------------------
    def cancelOrder(self, cancelOrderReq):
        """撤单"""
        self.api.cancelOrder_(cancelOrderReq)
        
    #----------------------------------------------------------------------
    def qryAccount(self):
        """查询账户资金"""
        self.api.getAccountInfo()
        
    #----------------------------------------------------------------------
    def qryPosition(self):
        """查询持仓"""
        self.api.getPositions()
        
    #----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.api.exit()
        
    #----------------------------------------------------------------------
    def initQuery(self):
        """初始化连续查询"""
        if self.qryEnabled:
            # 需要循环的查询函数列表
            self.qryFunctionList = [self.qryAccount, self.qryPosition]
            
            self.qryCount = 0           # 查询触发倒计时
            self.qryTrigger = 2         # 查询触发点
            self.qryNextFunction = 0    # 上次运行的查询函数索引
            
            self.startQuery()
    
    #----------------------------------------------------------------------
    def query(self, event):
        """注册到事件处理引擎上的查询函数"""
        self.qryCount += 1
        
        if self.qryCount > self.qryTrigger:
            # 清空倒计时
            self.qryCount = 0
            
            # 执行查询函数
            function = self.qryFunctionList[self.qryNextFunction]
            function()
            
            # 计算下次查询函数的索引，如果超过了列表长度，则重新设为0
            self.qryNextFunction += 1
            if self.qryNextFunction == len(self.qryFunctionList):
                self.qryNextFunction = 0
    
    #----------------------------------------------------------------------
    def startQuery(self):
        """启动连续查询"""
        self.eventEngine.register(EVENT_TIMER, self.query)
    
    #----------------------------------------------------------------------
    def setQryEnabled(self, qryEnabled):
        """设置是否要启动循环查询"""
        self.qryEnabled = qryEnabled
########################################################################    

class Api(OandaApi):
    def __init__(self, gateway):
        spi = Spi(self, gateway)
        super(Api, self).__init__(spi)

########################################################################
class Spi(OandaSpi):
    """OANDA的SPI实现"""

    #----------------------------------------------------------------------
    def __init__(self, api, gateway):
        """Constructor"""
        super(Spi, self).__init__(api)
        
        self.gateway = gateway                  # gateway对象
        self.gatewayName = gateway.gatewayName  # gateway对象名称
        
        self.orderDict = {}     # 缓存委托数据
        
    #----------------------------------------------------------------------
    def onError(self, error, reqID):
        """错误信息回调"""
        err = VtErrorData()
        err.gatewayName = self.gatewayName
        err.errorMsg = str(error)
        self.gateway.onError(err)

    #----------------------------------------------------------------------
    def onPrice(self, data):
        """行情推送"""
        
        tick = VtTickData()
        tick.gatewayName = self.gatewayName
        
        tick.symbol = data['instrument']
        tick.exchange = EXCHANGE_OANDA
        tick.vtSymbol = '.'.join([tick.symbol, tick.exchange])   
        
        list_bids = data['bids']
        dict_bid1 = list_bids[0]
        tick.bidPrice1 = float(dict_bid1['price'])
        
        list_asks = data['asks']
        dict_ask1 = list_asks[0]
        tick.askPrice1 = float(dict_ask1['price'])

        tick.time = getTime(data['time'])
        
        # 做市商的TICK数据只有买卖的报价，因此最新价格选用中间价代替
        tick.lastPrice = (tick.bidPrice1 + tick.askPrice1)/2        
        self.gateway.onTick(tick)
        
    
    #----------------------------------------------------------------------
    def writeLog(self, logContent):
        """发出日志"""
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = logContent
        self.gateway.onLog(log)
        
    
#----------------------------------------------------------------------
def getTime(t):
    """把OANDA返回的时间格式转化为简单的时间字符串"""
    return t[:21]
    