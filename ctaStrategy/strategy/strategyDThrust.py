# encoding: UTF-8
"""
dual thrust
"""
from __future__ import division

import talib
from copy import copy
from datetime import datetime, timedelta

import vtPath
from ctaBase import *
from ctaTemplate2 import CtaTemplate3
from vtConstant import *

__BACKTESTING__ = True
MAX_NUMBER = 10000000
MIN_NUMBER = 0

# 主状态基类
class State:
    last_traded_order = None
    intra_trade_high = MIN_NUMBER
    intra_trade_low = MAX_NUMBER
    up_break = False
    down_break = False
    def __init__(self, strategy):
        # 0
        self.strategy = strategy
        self.__class__ = State0

    def new_state(self, newstate):
        self.__class__ = newstate
        self.onEnterState()

    def onEnterState(self):
        raise NotImplementedError
    
    def inState(self):
        raise NotImplementedError

class State0(State):
    """Initialization"""
    def onEnterState(self):
        print 'Enter S0'
        try:
            ticks = self.strategy.loadTick(self.strategy.vtSymbol, self.strategy.N)
            for tick in ticks:
                tick.isHistory = True
                self.strategy.onTick(tick)
            del ticks
        except Exception as e:
            print str(e)
        else:
            # 0 ---> 1
            self.new_state(State1)

    def inState(self):
        pass

class State1(State):
    """Waiting for trading signal"""
    def onEnterState(self):
        print 'Enter S1'
        #if new trading day and breakthough
        # check up_break or down_break
        # 1 ---> 2

    def inState(self):
        pass

class State2(State):
    """Open"""
    def onEnterState(self):
        print 'Enter S2'
        # sendorder
        direction = CTAORDER_BUY if self.up_break else CTAORDER_SHORT
        f = 1 if self.strategy.direction_long else -1
        self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastPrice + f * 10, self.strategy.volume, self)#, False, False)
        # 2 ---> 3
        self.new_state(State3)

    def inState(self):
        pass

class State3(State):
    """Opening"""
    def onEnterState(self):
        print 'Enter S3'

    def inState(self):
        if self.strategy.all_traded == True:
            self.last_traded_order = copy(self.strategy.last_traded_order)
            self.last_traded_time = copy(self.strategy.last_traded_time)
            # 3 ---> 4
            self.new_state(State4)

class State4(State):
    """Wait Close"""
    def onEnterState(self):
        self.intra_trade_high = self.strategy.lastBar.high
        self.intra_trade_low = self.strategy.lastBar.low
        print 'Enter S4'

    def inState(self):
        self.intra_trade_high = max(self.strategy.lastBar.high, self.intra_trade_high)
        self.intra_trade_low = min(self.strategy.lastBar.low, self.intra_trade_low)
        #print "S4  1M: %.2f  5M: %.2f  60M: %.2f" %(wfr_1min, wfr_5min, wfr_60min)
        if self.need_stoploss():
            # 4 ---> 5
            print 'stoploss'
            self.new_state(State5)
            return
        if self.need_trailing_stoploss():
            # 4 ---> 5
            print 'trailing stoploss'
            self.new_state(State5)
            return
    
    def need_stoploss(self):
        if self.strategy.direction_long:
            return self.strategy.lastPrice - self.adjusted_cost() < -self.strategy.stoploss_value
        else:
            return self.adjusted_cost() - self.strategy.lastPrice < -self.strategy.stoploss_value

    def need_trailing_stoploss(self):
        if self.strategy.direction_long:
            return self.strategy.lastPrice < self.intra_trade_high *(1 - self.strategy.trailing_percentage/100.0)
        else:
            return self.strategy.lastPrice > self.intra_trade_low * (1 - self.strategy.trailing_percentage/100.0)
        

    def adjusted_cost(self):
        f = 1.0
        if self.last_traded_order.direction == DIRECTION_SHORT:
            f = -1.0
        time_span = self.strategy.lastTick.datetime - self.last_traded_time
        ac = self.last_traded_order.price*(1 + f * self.strategy.stoploss_discount * time_span.seconds/(3600*24*365))
        return ac


class State5(State):
    """Close"""
    def onEnterState(self):
        self.intra_trade_high = MIN_NUMBER
        self.intra_trade_low = MAX_NUMBER
        print 'Enter S5'
        # sendorder
        direction = CTAORDER_SELL if self.strategy.direction_long else CTAORDER_COVER
        f = 1 if self.strategy.direction_long else -1
        self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastPrice - f * 10, self.strategy.volume, self)#, False, False)
        # 5 ---> 6
        self.new_state(State6)

    def inState(self):
        print 'S5'
        pass

class State6(State):
    """Closing"""
    def onEnterState(self):
        print 'Enter S6'

    def inState(self):
        if self.strategy.all_traded == True:
            # 6 ---> 1
            self.new_state(State1)
        

########################################################################
class DThrustStrategy(CtaTemplate2):
    
    className = 'DThrustStrategy'
    author = u''

    #------------------------------------------------------------------------
    # 策略参数
    N = 5
    k1 = 0.7
    k2 = 0.7
    # others
    volume = 1
    # stoploss
    stoploss_discount = .3
    stoploss_value = 20
    trailing_percentage = 2
    #----------------------------------------------

    #------------------------------------------------------------------------
    # 策略变量
    bufferSize = 100
    count = 0
    bar = None
    bar_5min = None
    barMinute = EMPTY_STRING

    openArray = np.zeros(bufferSize)
    highArray = np.zeros(bufferSize)
    lowArray = np.zeros(bufferSize)
    closeArray = np.zeros(bufferSize)

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(DThrustStrategy, self).__init__(ctaEngine, setting)
        self.lastPrice = 0.0
        self.barSeries_1min = []

        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）        
        self.all_traded = False
    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' %self.name)
        self.vtSymbol = self.vtSymbols[0]
        self.fsm = State(self)

        
        
    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略启动' %self.name)

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略停止' %self.name)

    #-----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        self.lastPrice = tick.lastPrice
        self.lastTick = tick
        # 聚合为1分钟K线
        tickMinute = tick.datetime.minute

        if tickMinute != self.barMinute:
            if self.bar:
                self.onBar(self.bar)

            bar = CtaBarData()
            bar.vtSymbol = tick.vtSymbol
            bar.symbol = tick.symbol
            bar.exchange = tick.exchange

            bar.open = tick.lastPrice
            bar.high = tick.lastPrice
            bar.low = tick.lastPrice
            bar.close = tick.lastPrice

            bar.date = tick.date
            bar.time = tick.time
            bar.datetime = tick.datetime    # K线的时间设为第一个Tick的时间

            self.bar = bar                  # 这种写法为了减少一层访问，加快速度
            self.barMinute = tickMinute     # 更新当前的分钟
        else:                               # 否则继续累加新的K线
            bar = self.bar                  # 写法同样为了加快速度

            bar.high = max(bar.high, tick.lastPrice)
            bar.low = min(bar.low, tick.lastPrice)
            bar.close = tick.lastPrice

        self.fsm.inState()
    #----------------------------------------------------------------------
    def create_aggregator(self, period):
        # closure buffer
        bar_aggr_buf = [None]
        def aggregator(bar, callback):
            if bar.datetime.minute % period == 0:
                # 如果已经有聚合5分钟K线
                if bar_aggr_buf[0]:
                    # 将最新分钟的数据更新到目前5分钟线中
                    bar_aggr = bar_aggr_buf[0]
                    bar_aggr.high = max(bar_aggr.high, bar.high)
                    bar_aggr.low = min(bar_aggr.low, bar.low)
                    bar_aggr.close = bar.close
                    
                    # 推送5分钟线数据
                    callback(bar_aggr)
                    
                    # 清空5分钟线数据缓存
                    bar_aggr_buf[0] = None
            else:
                # 如果没有缓存则新建
                if not bar_aggr_buf[0]:
                    bar_aggr = CtaBarData()
                    
                    bar_aggr.vtSymbol = bar.vtSymbol
                    bar_aggr.symbol = bar.symbol
                    bar_aggr.exchange = bar.exchange
                
                    bar_aggr.open = bar.open
                    bar_aggr.high = bar.high
                    bar_aggr.low = bar.low
                    bar_aggr.close = bar.close
                    bar_aggr.close_ = bar.close_
                
                    bar_aggr.date = bar.date
                    bar_aggr.time = bar.time
                    bar_aggr.datetime = bar.datetime 
                    
                    bar_aggr_buf[0] = bar_aggr
                else:
                    bar_aggr = bar_aggr_buf[0]
                    bar_aggr.high = max(bar_aggr.high, bar.high)
                    bar_aggr.low = min(bar_aggr.low, bar.low)
                    bar_aggr.close = bar.close
        return aggregator
    #----------------------------------------------------------------------
    def updateArrays(self, bar):
        # 保存K线数据
        self.closeArray[0:self.bufferSize-1] = self.closeArray[1:self.bufferSize]
        self.highArray[0:self.bufferSize-1] = self.highArray[1:self.bufferSize]
        self.lowArray[0:self.bufferSize-1] = self.lowArray[1:self.bufferSize]
        
        self.closeArray[-1] = bar.close
        self.highArray[-1] = bar.high
        self.lowArray[-1] = bar.low

    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.lastPrice = bar.close
        self.lastBar = bar
        bar.close_ = (bar.high + bar.low)/2
        if __BACKTESTING__:
            self.lastTick = CtaTickData()
            self.lastTick.lastPrice = bar.close
            self.lastTick.datetime = bar.datetime
        for i in range(3):
            bar.close_ = self.pfs[i].Calculate(bar.close_)[0]
        
        self.barSeries_1min.append(bar)
        self.updateArrays(bar)

        self.pos_1min.append({'datetime':bar.datetime, 'pos':self.pos.get(bar.vtSymbol, 0)})
        self.aggregate_5min(bar, self.onBar_5min)
        self.aggregate_60min(bar, self.onBar_60min)

        self.fsm.inState()

    #----------------------------------------------------------------------
    def onBar_5min(self, bar):
        pass
    #----------------------------------------------------------------------
    def onBar_60min(self, bar):
        pass        

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        print "onOrder(): orderTime = %r ; vtOrderID = %r; status = %s" % (order.orderTime, order.vtOrderID, order.status)
        if order.status == STATUS_ALLTRADED:
            self.all_traded = True
            #self.last_traded_order = order
            if  __BACKTESTING__:
                self.last_traded_time = datetime.strptime(order.orderTime, '%Y-%m-%d %H:%M:%S')
            else:
                self.last_traded_time = datetime.now()
        self.fsm.inState()
        self.all_traded = False

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        # print '-'*50
        # print 'onTrade'
        self.last_traded_order = trade
        pass



def backtesting():
    # 以下内容是一段回测脚本的演示，用户可以根据自己的需求修改
    # 建议使用ipython notebook或者spyder来做回测
    # 同样可以在命令模式下进行回测（一行一行输入运行）
    import vtPath
    from ctaBacktesting import BacktestingEngine
    
    # 创建回测引擎
    engine = BacktestingEngine()
    
    # 设置引擎的回测模式为K线
    engine.setBacktestingMode(engine.BAR_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate('20160622')
    engine.setEndDate('20160705')
    
    # 载入历史数据到引擎中
    engine.setDatabase(MINUTE_DB_NAME, 'rb1705')
    
    # 设置产品相关参数
    engine.setSlippage(1)     # 股指1跳
    engine.setRate(0.3/10000)   # 万0.3
    engine.setSize(1)         # 股指合约大小    
    
    # 在引擎中创建策略对象
    engine.initStrategy(WFStrategy, {})
    
    # 开始跑回测
    engine.runBacktesting()
    
    # 显示回测结果
    # spyder或者ipython notebook中运行时，会弹出盈亏曲线图
    # 直接在cmd中回测则只会打印一些回测数值
    try:
        engine.showBacktestingResult()
    except Exception as e:
        print str(e)