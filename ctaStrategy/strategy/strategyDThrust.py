# encoding: UTF-8
"""
dual thrust
"""
from __future__ import division

import numpy as np

import talib
from copy import copy
from datetime import datetime, timedelta

import vtPath
from ctaBase import *
from ctaTemplate2 import CtaTemplate2
from vtConstant import *
from my_module.ring_buffer import ring_buffer

__BACKTESTING__ = True
MAX_NUMBER = 10000000
MIN_NUMBER = 0

# 主状态基类
class State:
    last_traded_order = None
    intra_trade_high = MIN_NUMBER
    intra_trade_low = MAX_NUMBER
    hist_hlc_dict = {}
    direction = DIRECTION_UNKNOWN
    traded_price = -1;
    def __init__(self, strategy):
        # 0
        self.strategy = strategy
        self.__class__ = State0

    def new_state(self, newstate):
        self.__class__ = newstate
        self.onEnterState()

    def onEnterState(self):
        pass
    
    def inState(self):
        pass

    def onEvent(self, event_type):
        pass

    def need_stoploss(self):
        if self.direction == DIRECTION_LONG:
            pnl = self.strategy.lastPrice - self.last_traded_order.price
            need_sl =  pnl < -self.strategy.stoploss_value
            if need_sl:
                print 'stoploss long pnl = %.1f' % pnl
            return need_sl
        elif self.direction == DIRECTION_SHORT:
            pnl = self.last_traded_order.price - self.strategy.lastPrice
            need_sl = pnl < -self.strategy.stoploss_value
            if need_sl:
                print 'stoploss short pnl = %.1f' % pnl
            return need_sl

    def need_trailing_stoploss(self):
        if self.direction == DIRECTION_LONG:
            return self.strategy.lastPrice < self.intra_trade_high *(1 - self.strategy.trailing_percentage/100.0)
        elif self.direction == DIRECTION_SHORT:
            return self.strategy.lastPrice > self.intra_trade_low * (1 - self.strategy.trailing_percentage/100.0)

    def adjusted_cost(self):
        f = 1.0
        if self.last_traded_order.direction == DIRECTION_SHORT:
            f = -1.0
        time_span = self.strategy.lastTick.datetime - self.last_traded_time
        ac = self.last_traded_order.price*(1 + f * self.strategy.stoploss_discount * time_span.seconds/(3600*24*365))
        return ac

    def update_cost_data(self):
        self.intra_trade_high = self.strategy.lastBar.high
        self.intra_trade_low = self.strategy.lastBar.low

    def update_intra_trade_data(self):
        self.intra_trade_high = max(self.strategy.lastBar.high, self.intra_trade_high)
        self.intra_trade_low = min(self.strategy.lastBar.low, self.intra_trade_low)

    def reset_intra_trade_data(self):
        self.intra_trade_high = MIN_NUMBER
        self.intra_trade_low = MAX_NUMBER

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
        # 0 ---> 1
        self.new_state(State7)

    def inState(self):
        pass
    

class State1(State):
    """Waiting for trading signal"""
    def onEnterState(self):
        print 'Enter S1'
        self.direction = DIRECTION_UNKNOWN
        # recalculate HH, HC, LC, L
        self.hist_hlc_dict = self.strategy.calc_hlc_from_ring_buffer()
        today_open = self.strategy.today_open
        m = max(self.hist_hlc_dict['HH']-self.hist_hlc_dict['LC'], self.hist_hlc_dict['HC']-self.hist_hlc_dict['LL'])
        self.long_trigger = today_open + m * self.strategy.k1
        self.short_trigger = today_open - m * self.strategy.k2
        print 'S1: open = %.1f, long_trigger = %.1f, short_trigger = %.1f' %(today_open, self.long_trigger, self.short_trigger)

    def inState(self):
        #if new trading day and breakthough
        # check up_break or down_break
        self.update_intra_trade_data()
        #check stoploss
        if self.need_stoploss():
            # 1 ---> 5
            print 'S1 stoploss'
            self.new_state(State5)
            return
        if self.need_trailing_stoploss():
            # 1 ---> 5
            print 'S1 trailing stoploss'
            self.new_state(State5)
            return
        if self.strategy.lastPrice > self.long_trigger:
            print 'LONG'
            self.direction = DIRECTION_LONG
            # 1 ---> 2
            self.new_state(State2)
        elif self.strategy.lastPrice < self.short_trigger:
            print 'SHORT'
            self.direction = DIRECTION_SHORT
            # 1 ---> 2
            self.new_state(State2)
    
    def onEvent(self, event_type):
        if event_type == "NEW_DAY":
            self.new_state(State1)


class State2(State):
    """Open"""
    def onEnterState(self):
        print 'Enter S2'
        # sendorder
        pos = self.strategy.pos.get(self.strategy.vtSymbol, 0)
        if pos > 0:
            #hold long
            if self.direction == DIRECTION_LONG:
                # 2 ---> 4
                self.new_state(State4)
                return
            else:
                # close first
                self.strategy.sendOrder(self.strategy.vtSymbol, CTAORDER_SELL, self.strategy.lastPrice - 10, pos, self.strategy)
                # 2 ---> 2cd
                self.new_state(State2cd)
                return
        elif pos < 0:
            #hold short
            if self.direction == DIRECTION_SHORT:
                # 2 ---> 4
                self.new_state(State4)
                return
            else:
                # close first
                self.strategy.sendOrder(self.strategy.vtSymbol, CTAORDER_COVER, self.strategy.lastPrice + 10, -pos, self.strategy)
                # 2 ---> 2cd
                self.new_state(State2cd)
                return
        else:
            #hold net
            direction = CTAORDER_BUY if self.direction==DIRECTION_LONG else CTAORDER_SHORT
            f = 1 if direction==CTAORDER_BUY else -1
            self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastPrice + f * 10, self.strategy.volume, self.strategy)
            # 2 ---> 3
            self.new_state(State3)
            return

    def inState(self):
        pass

class State2cd(State):
    "Closing remaining position"
    def onEnterState(self):
        pass
    def inState(self):
        if self.strategy.all_traded == True:
            # 2cd ---> 2
            self.reset_intra_trade_data()
            self.new_state(State2)

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
    def onEvent(self, event_type):
        self.new_state(State1)

class State4(State):
    """idle : stop loss check"""
    def onEnterState(self):
        print 'Enter S4'
        self.update_cost_data()

    def inState(self):
        self.update_intra_trade_data()
        if self.need_stoploss():
            # 4 ---> 5
            print 'S4 stoploss'
            self.new_state(State5)
            return
        if self.need_trailing_stoploss():
            # 4 ---> 5
            print 'S4 trailing stoploss'
            self.new_state(State5)
            return
    
    def onEvent(self, event_type):
        if event_type == "NEW_DAY":
            self.new_state(State1)


class State5(State):
    """Close"""
    def onEnterState(self):
        print 'Enter S5'
        # sendorder
        direction = CTAORDER_SELL if self.direction==DIRECTION_LONG else CTAORDER_COVER
        f = 1 if self.direction==DIRECTION_LONG else -1
        self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastPrice - f * 10, self.strategy.volume, self.strategy)
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
            # 6 ---> 7
            self.reset_intra_trade_data()
            self.new_state(State7)
    

class State7(State):
    """Idle, wait for new day"""
    def onEnterState(self):
        print 'Enter S7'
    def inState(self):
        pass
    def onEvent(self, event_type):
        if event_type == 'NEW_DAY':
            # 7 ---> 1
            self.new_state(State1)

########################################################################
class DThrustStrategy(CtaTemplate2):
    
    className = 'DThrustStrategy'
    author = u''

    #------------------------------------------------------------------------
    # 策略参数
    N = 1
    k1 = 0.7
    k2 = 1.0
    # others
    volume = 1
    # stoploss
    stoploss_discount = .3
    stoploss_value = 10
    trailing_percentage = 4
    #----------------------------------------------

    #------------------------------------------------------------------------
    # 策略变量
    bufferSize = N * 300 
    count = 0
    bar = None
    bar_5min = None
    barMinute = EMPTY_STRING

    openArray = ring_buffer(bufferSize)
    highArray = ring_buffer(bufferSize)
    lowArray = ring_buffer(bufferSize)
    closeArray = ring_buffer(bufferSize)
    timeArray = ring_buffer(bufferSize)
    last_day = None
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
        try:
            self.vtSymbol = self.vtSymbols[0]
        except IndexError:
            self.vtSymbol = 'rb1801'
        self.fsm = State(self)
        self.fsm.new_state(State0)

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略启动' %self.name)

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略停止' %self.name)
        position = self.pos.get(self.vtSymbol, 0)
        if position > 0:
            self.sendOrder(self.vtSymbol, CTAORDER_SELL, self.lastPrice - 10, position, self)
        elif position < 0:
            self.sendOrder(self.vtSymbol, CTAORDER_COVER, self.lastPrice + 10, -position, self)

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
    def updateRingBuffers(self, bar):
        self.openArray.push_back(bar.open)
        self.closeArray.push_back(bar.close)
        self.highArray.push_back(bar.high)
        self.lowArray.push_back(bar.low)
        self.timeArray.push_back(bar.datetime)

    def calc_hlc_from_ring_buffer(self):
        HH = max(self.highArray._array)
        LC = min(self.closeArray._array, key=lambda x : x if x else MAX_NUMBER)
        HC = max(self.closeArray._array)
        LL = min(self.lowArray._array, key=lambda x:x if x else MAX_NUMBER)
        return {'HH':HH, 'LC':LC, 'HC':HC, 'LL':LL}
    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.updateRingBuffers(bar)
        if bar.datetime.day != self.last_day:
            self.last_day = bar.datetime.day
            self.today_open = bar.open
            self.fsm.onEvent("NEW_DAY")
        self.lastPrice = bar.close
        self.lastBar = bar
        if __BACKTESTING__:
            self.lastTick = CtaTickData()
            self.lastTick.lastPrice = bar.close
            self.lastTick.datetime = bar.datetime
        
        self.barSeries_1min.append(bar)
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
            if  __BACKTESTING__:
                self.last_traded_time = datetime.strptime(order.orderTime, '%Y-%m-%d %H:%M:%S')
            else:
                self.last_traded_time = datetime.now()
        self.fsm.inState()
        self.all_traded = False

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        self.last_traded_order = trade


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
    
    # 载入历史数据到引擎中
    engine.setDatabase(MINUTE_DB_NAME, 'rb1705')
    
    # 设置产品相关参数
    engine.setSlippage(1)     # 股指1跳
    engine.setRate(0.3/10000)   # 万0.3
    engine.setSize(1)         # 股指合约大小    
    
    # 在引擎中创建策略对象
    engine.initStrategy(DThrustStrategy, {})
    
    # 开始跑回测
    engine.runBacktesting()
    
    # 显示回测结果
    # spyder或者ipython notebook中运行时，会弹出盈亏曲线图
    # 直接在cmd中回测则只会打印一些回测数值
    try:
        engine.showBacktestingResult()
    except Exception as e:
        print str(e)