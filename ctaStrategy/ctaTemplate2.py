# encoding: UTF-8

'''
本文件包含了CTA引擎中的策略开发用模板，开发策略时需要继承CtaTemplate类。
'''

from ctaBase import *
from vtConstant import *
import json

from ctaTask import CtaTask



########################################################################
class CtaTemplate2(object):
    """CTA策略模板"""
    
    # 策略类的名称和作者
    className = 'CtaTemplate2'
    author = EMPTY_UNICODE
    
    # MongoDB数据库的名称，K线数据库默认为1分钟
    tickDbName = TICK_DB_NAME
    barDbName = MINUTE_DB_NAME
    strategyDbName = STRATEGY_DB_NAME

    # 本地持仓文件名前缀
    posFileNamePrefix = './temp/position'
    
    # 策略的基本参数
    name = EMPTY_UNICODE           # 策略实例名称
    vtSymbols = []                 # 交易的合约vt系统代码    
    productClass = EMPTY_STRING    # 产品类型（只有IB接口需要）
    currency = EMPTY_STRING        # 货币（只有IB接口需要）
    ib_exchange = EMPTY_STRING  
    savePosition = True             # 是否开启持仓记录

    # 策略的基本变量，由引擎管理
    inited = False                 # 是否进行了初始化
    trading = False                # 是否启动交易，由引擎管理
    pos = {}                        # 持仓情况
    
    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbols',
                 'currency',
                 'ib_exchange',
                 'productClass']
    
    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos']

    #任务列表
    _taskList = []          

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        self.ctaEngine = ctaEngine
        # 设置策略的参数
        if setting:
            d = self.__dict__

            for key in self.paramList:
                if key in setting:
                    d[key] = setting[key]
            # 初始化持仓字典
            for s in self.vtSymbols:
                self.pos[s] = 0

        

    #----------------------------------------------------------------------
    def onTask(self, task_result):
        """定时任务（必须由用户继承实现）"""
        raise NotImplementedError

    def addTask(self, task):
        self._taskList.append(task)

    def __startTask__(self):
        for task in self._taskList:
            task.start()        

    def __stopTask__(self):
        for task in self._taskList:
            task.stop()
    #----------------------------------------------------------------------
    def __onInit__(self):
        self.onInit()
        # 其他需要在基类中执行的代码
        if self.savePosition:
            self.__readPositionData__()

    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def __onStart__(self):
        self.onStart()
        # 初始化任务
        self.__startTask__()

    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def __onStop__(self):
        self.onStop()
        self.__stopTask__()

    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        raise NotImplementedError

    #----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        raise NotImplementedError

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        raise NotImplementedError
    #----------------------------------------------------------------------    
    def onBalance(self, balance):
        """下单资金返还推送（必须由用户继承实现）"""
        raise NotImplementedError
    #----------------------------------------------------------------------
    def __onTrade__(self, trade):
        self.onTrade(trade)
        # 更新本地持仓代码
        if self.savePosition:
            self.__writePositionData__()
    
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        raise NotImplementedError
    
    #----------------------------------------------------------------------
    def buy(self, symbol, price, volume, stop=False):
        """买开"""
        return self.sendOrder(symbol, CTAORDER_BUY, price, volume, stop)
    
    #----------------------------------------------------------------------
    def sell(self, symbol, price, volume, stop=False):
        """买平"""
        return self.sendOrder(symbol, CTAORDER_SELL, price, volume, stop)       

    #----------------------------------------------------------------------
    def short(self, symbol, price, volume, stop=False):
        """卖开"""
        return self.sendOrder(symbol, CTAORDER_SHORT, price, volume, stop)          
 
    #----------------------------------------------------------------------
    def cover(self, symbol, price, volume, stop=False):
        """卖平"""
        return self.sendOrder(symbol, CTAORDER_COVER, price, volume, stop)
        
    #----------------------------------------------------------------------
    def sendOrder(self, symbol, orderType, price, volume, stop=False, market=False, fok=False, parked=False, alt=False, **kwargs):
        """发送委托"""
        if self.trading:
            if symbol in self.vtSymbols:
                # 如果stop为True，则意味着发本地停止单
                if stop:
                    vtOrderID = self.ctaEngine.sendStopOrder(symbol, orderType, price, volume, self)
                elif market:
                    vtOrderID = self.ctaEngine.sendOrder(symbol, orderType, 0, volume, self, PRICETYPE_MARKETPRICE, parked, alt, kwargs)
                elif fok:
                    vtOrderID = self.ctaEngine.sendOrder(symbol, orderType, price, volume, self, PRICETYPE_FOK, parked, alt, kwargs)
                else:
                    vtOrderID = self.ctaEngine.sendOrder(symbol, orderType, price, volume, self, PRICETYPE_LIMITPRICE, parked, alt, kwargs) 
                return vtOrderID

        return ''        
        
    #----------------------------------------------------------------------
    def qryOrder(self, vtOrderID):
        """根据订单号查询订单"""
        self.ctaEngine.qryOrder(vtOrderID)
    #----------------------------------------------------------------------
    def cancelOrder(self, vtOrderID):
        """撤单"""
        # 如果发单号为空字符串，则不进行后续操作
        if not vtOrderID:
            return
        
        if STOPORDERPREFIX in vtOrderID:
            self.ctaEngine.cancelStopOrder(vtOrderID)
        else:
            self.ctaEngine.cancelOrder(vtOrderID)
    #----------------------------------------------------------------------
    def getContract(self, vtSymbol):
        return self.ctaEngine.getContract(vtSymbol)

    def getPriceTick(self, vtSymbol):
        contract = self.ctaEngine.getContract(vtSymbol)
        if contract:
            return contract.priceTick
        else:
            print u"合约%s未订阅" %vtSymbol
    #----------------------------------------------------------------------
    def insertTick(self, tick):
        """向数据库中插入tick数据"""
        self.ctaEngine.insertData(self.tickDbName, tick.vtSymbol, tick)
    
    #----------------------------------------------------------------------
    def insertBar(self, bar):
        """向数据库中插入bar数据"""
        self.ctaEngine.insertData(self.barDbName, bar.vtSymbol, bar)
        
    #----------------------------------------------------------------------
    def loadTick(self, vtSymbol, days):
        """读取tick数据"""
        return self.ctaEngine.loadTick(self.tickDbName, vtSymbol, days)
    
    #----------------------------------------------------------------------
    def loadBar(self, vtSymbol, days):
        """读取bar数据"""
        return self.ctaEngine.loadBar(self.barDbName, vtSymbol, days)
    
    #----------------------------------------------------------------------
    def insertStrategyData(self, data):
        """把data记录到Strategy数据库"""
        self.ctaEngine.insertData(self.strategyDbName, self.name, data)

    def writeCtaLog(self, content):
        """记录CTA日志"""
        content = self.name + ':' + content
        self.ctaEngine.writeCtaLog(content)
        
    #----------------------------------------------------------------------
    def putEvent(self):
        """发出策略状态变化事件"""
        self.ctaEngine.putStrategyEvent(self.name)
        
    #----------------------------------------------------------------------
    def getEngineType(self):
        """查询当前运行的环境"""
        return self.ctaEngine.engineType
    
    #-----------------------------------------------------------------------
    def __writePositionData__(self):
        """把策略对应的持仓记录写到文件"""
        posFileName = '.'.join([self.posFileNamePrefix, self.name])
        try:
            with open(posFileName, 'w') as f:
                jsonL = json.dumps(self.pos)
                f.write(jsonL)
        except:
            pass
        
    #-----------------------------------------------------------------------
    def __readPositionData__(self):
        """读取持仓记录文件"""
        self.writeCtaLog(u'载入本地持仓文件.....')
        posFileName = '.'.join([self.posFileNamePrefix, self.name])
        try:
            with open(posFileName, 'r') as f:
                self.pos = json.load(f)
        except:
            self.writeCtaLog("Abort, File doesn't exist.") 
    #-----------------------------------------------------------------------

    def queryLocalPos(self, vtSymbol):
        """读取本策略本地持仓数据"""

        if vtSymbol in self.vtSymbols and vtSymbol in self.pos.keys():
            return self.pos[vtSymbol]
        return 0

########################################################################
