# encoding: UTF-8
"""
dual thrust
"""
from __future__ import division

import numpy as np
import pandas as pd
import math

import talib
from copy import copy
from datetime import datetime, timedelta

import vtPath
from ctaBase import *
from ctaTemplate2 import CtaTemplate2
from vtConstant import *
from my_module.my_buffer import deque_buffer

MAX_NUMBER = 10000000
MIN_NUMBER = 0

__BACKTESTING__ = True
BACKTESTING_SYMBOL = 'rb9999'
TICK_SIZE = 1

log_str = ''
def print_log(str):
    global log_str
    if __BACKTESTING__:
        log_str = log_str + str + '\n'
    #print str

def write_log():
    if not __BACKTESTING__:
        return
    with open('results/log.txt','w') as f:
        #print log_str
        f.write(log_str.encode('utf-8'))


# 主状态基类
class State:
    last_traded_order = None
    intra_trade_high = MIN_NUMBER
    intra_trade_low = MAX_NUMBER
    hist_hlc_dict = {}
    direction = DIRECTION_UNKNOWN

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

    def calc_pnl(self, lastPrice):
        try:
            pos_cost = self.strategy.pos_cost_dict.get(self.strategy.vtSymbol,{})
            pos = pos_cost['position']
            cost = pos_cost['average_cost']
            f = 1 if pos != 0 else 0
            k = 1 if pos > 0 else -1
            return (lastPrice - cost) * f * k
        except Exception as e:
            return 0


    def need_stoploss(self):
        #1
        need_sl = False
        #2
        # pnl = self.calc_pnl(self.strategy.lastPrice)
        # need_sl =  pnl < -self.strategy.stoploss_value
        #3
        # if self.direction==DIRECTION_LONG:
        #     need_sl = need_sl or self.strategy.lastPrice < self.strategy.today_open
        # elif self.direction==DIRECTION_SHORT:
        #     need_sl = need_sl or self.strategy.lastPrice > self.strategy.today_open
        if need_sl:
            print_log('[stoploss]: pnl=%r' %pnl)
        return need_sl



    def need_trailing_stoploss(self):
        need_sl = False
        if self.direction == DIRECTION_LONG:
            need_sl = self.strategy.lastPrice < self.intra_trade_high *(1 - self.strategy.trailing_percentage/100.0)
            #need_sl = self.strategy.lastPrice < self.intra_trade_high - self.strategy.stoploss_value
        elif self.direction == DIRECTION_SHORT:
            need_sl = self.strategy.lastPrice > self.intra_trade_low * (1 + self.strategy.trailing_percentage/100.0)
            #need_sl = self.strategy.lastPrice > self.intra_trade_low + self.strategy.stoploss_value
        if need_sl:
            print_log('[trailing]')
        return need_sl

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
        print_log('Init...')
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
        #print 'Enter S1'
        #self.direction = DIRECTION_UNKNOWN
        # recalculate HH, HC, LC, L
        self.hist_hlc_dict = self.strategy.calc_hlc_from_buffer()
        today_open = self.strategy.today_open
        m = max(self.hist_hlc_dict['HH']-self.hist_hlc_dict['LC'], self.hist_hlc_dict['HC']-self.hist_hlc_dict['LL'])
        self.long_trigger = today_open + m * self.strategy.k1 / math.sqrt(self.strategy.N)
        self.short_trigger = today_open - m * self.strategy.k2 / math.sqrt(self.strategy.N)
        print_log('[%s] S1: open = %.1f, long_trigger = %.1f, short_trigger = %.1f' %(self.strategy.lastBar.datetime, today_open, self.long_trigger, self.short_trigger))
        print_log('trend_index = %f' %self.strategy.get_trend_index())

    def inState(self):
        # if self.strategy.get_trend_index() > 0.02:
        #     return
        #if new trading day and breakthough
        # check up_break or down_break
        self.update_intra_trade_data()
        #check stoploss
        if self.need_stoploss():
            # 1 ---> 5
            #print_log('S1 stoploss')
            self.new_state(State5)
            return
        if self.need_trailing_stoploss():
            # 1 ---> 5
            #print_log('S1 trailing stoploss')
            self.new_state(State5)
            return
        if self.strategy.lastPrice > self.long_trigger:
            print_log('LONG '+str(self.strategy.lastBar.__dict__))
            self.direction = DIRECTION_LONG
            # 1 ---> 2
            self.new_state(State2)
        elif self.strategy.lastPrice < self.short_trigger:
            print_log('SHORT '+str(self.strategy.lastBar.__dict__))
            self.direction = DIRECTION_SHORT
            # 1 ---> 2
            self.new_state(State2)
    
    def onEvent(self, event_type):
        if event_type == "NEW_DAY":
            self.new_state(State1)

class State2(State):
    """Open"""
    def onEnterState(self):
        #print_log('Enter S2')
        # sendorder
        pos = self.strategy.pos.get(self.strategy.vtSymbol, 0)
        if pos > 0:
            #hold long
            if self.direction == DIRECTION_LONG:
                if pos >= self.strategy.max_volume:
                    # 2 ---> 4
                    self.new_state(State4)
                    return
            else:
                # close first
                self.strategy.sendOrder(self.strategy.vtSymbol, CTAORDER_SELL, self.strategy.lastPrice - 10 * TICK_SIZE, pos, self.strategy)
                # 2 ---> 2cd
                self.new_state(State2cd)
                return
        elif pos < 0:
            #hold short
            if self.direction == DIRECTION_SHORT:
                if abs(pos) >= self.strategy.max_volume:
                    # 2 ---> 4
                    self.new_state(State4)
                    return
            else:
                # close first
                self.strategy.sendOrder(self.strategy.vtSymbol, CTAORDER_COVER, self.strategy.lastPrice + 10 * TICK_SIZE, -pos, self.strategy)
                # 2 ---> 2cd
                self.new_state(State2cd)
                return
        
        direction = CTAORDER_BUY if self.direction==DIRECTION_LONG else CTAORDER_SHORT
        f = 1 if direction==CTAORDER_BUY else -1
        self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastPrice + f * 10 * TICK_SIZE, self.strategy.volume, self.strategy)
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
            print_log('-'*100)
            self.reset_intra_trade_data()
            self.new_state(State2)

class State3(State):
    """Opening"""
    def onEnterState(self):
        pass
        #print_log('Enter S3')

    def inState(self):
        if self.strategy.all_traded == True:
            #self.last_traded_order = copy(self.strategy.last_traded_order)
            self.last_traded_time = copy(self.strategy.last_traded_time)
            # 3 ---> 4
            self.new_state(State4)
    def onEvent(self, event_type):
        self.new_state(State1)

class State4(State):
    """idle : stop loss check"""
    def onEnterState(self):
        #print_log('Enter S4')
        self.update_cost_data()

    def inState(self):
        self.update_intra_trade_data()
        if self.need_stoploss():
            # 4 ---> 5
            #print_log('S4 stoploss')
            self.new_state(State5)
            return
        if self.need_trailing_stoploss():
            # 4 ---> 5
            #print_log('S4 trailing stoploss')
            self.new_state(State5)
            return
    
    def onEvent(self, event_type):
        if event_type == "NEW_DAY":
            self.new_state(State1)
        elif event_type == "DAY_CLOSE":
            #self.new_state(State5)
            pass

class State5(State):
    """Close"""
    def onEnterState(self):
        print_log('[Close]')
        # sendorder
        direction = CTAORDER_SELL if self.direction==DIRECTION_LONG else CTAORDER_COVER
        f = 1 if self.direction==DIRECTION_LONG else -1

        volume = self.strategy.volume
        pos_cost = self.strategy.pos_cost_dict.get(self.strategy.vtSymbol,{})
        if pos_cost:
            volume = pos_cost.get('position',0)
        self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastPrice - f * 10 * TICK_SIZE, abs(volume), self.strategy)
        # 5 ---> 6
        self.new_state(State6)

    def inState(self):
        print_log('S5')

class State6(State):
    """Closing"""
    def onEnterState(self):
        pass

    def inState(self):
        if self.strategy.all_traded == True:
            # 6 ---> 7
            self.reset_intra_trade_data()
            print_log('-'*100)
            self.new_state(State7)
    
class State7(State):
    """Idle, wait for new day"""
    def onEnterState(self):
        #print_log('Enter S7')
        self.direction = DIRECTION_UNKNOWN
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
    k1 = .7
    k2 = .7
    # others
    volume = 1
    max_volume = 4
    # stoploss
    stoploss_discount = .3
    stoploss_value = 80 * TICK_SIZE
    trailing_percentage = 2
    #----------------------------------------------

    #------------------------------------------------------------------------
    # 策略变量
    bufferSize = N * 300 
    count = 0
    bar = None
    bar_5min = None
    barMinute = EMPTY_STRING

    barArray = deque_buffer(bufferSize)
    closeArray = deque_buffer(bufferSize)
    ddArray = deque_buffer(bufferSize)
    rddArray = deque_buffer(bufferSize)
    
    last_day = None

    pos_cost_dict = {}
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
        if __BACKTESTING__:
            self.log_str = ''
            self.data = {'close':[], 'trend_index':[]}



    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' %self.name)
        try:
            self.vtSymbol = self.vtSymbols[0]
        except IndexError:
            self.vtSymbol = 'rb9999'
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
        
        write_log()
        df = pd.DataFrame(self.data)
        df.to_csv('results/data.csv')

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
    def calc_hlc_from_buffer(self):
        HH = max(self.barArray._array, key=lambda x:x.high)
        LC = min(self.barArray._array, key=lambda x:x.close if x.close else MAX_NUMBER)
        HC = max(self.barArray._array, key=lambda x:x.close)
        LL = min(self.barArray._array, key=lambda x:x.low if x.low else MAX_NUMBER)
        return {'HH':HH.high, 'LC':LC.close, 'HC':HC.close, 'LL':LL.low}

    #----------------------------------------------------------------------
    @staticmethod
    def maxdrawdown(arr):
        arr = np.array(arr)
        tmp = (np.maximum.accumulate(arr) - arr)/np.maximum.accumulate(arr)
        i = np.argmax(tmp)
        if i==0:
            return 0.0
        return tmp[i]
    
    @staticmethod
    def maxdrawdown_r(arr):
        arr = np.array(arr)
        tmp = (arr - np.minimum.accumulate(arr))/np.minimum.accumulate(arr)
        i = np.argmax(tmp)
        if i==0:
            return 0.0
        return tmp[i]

    #----------------------------------------------------------------------
    def update_dd_rdd_buffer(self):
        new_dd = self.maxdrawdown(self.closeArray._array)
        new_rdd = self.maxdrawdown_r(self.closeArray._array)
        self.ddArray.push_back(new_dd)
        self.rddArray.push_back(new_rdd)

    #----------------------------------------------------------------------
    def get_trend_index(self):
        a = sum(self.ddArray._array)/self.ddArray.length()
        b = sum(self.rddArray._array)/self.rddArray.length()
        #print a, b
        return min(a, b)
    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        self.lastPrice = bar.close
        self.lastBar = bar
        self.barArray.push_back(bar)
        self.closeArray.push_back(bar.close)
        self.update_dd_rdd_buffer()
        if __BACKTESTING__:
            self.data['close'].append(bar.close)
            self.data['trend_index'].append(self.get_trend_index())

        if bar.datetime.day != self.last_day:
            self.last_day = bar.datetime.day
            self.today_open = bar.open
            self.fsm.onEvent("NEW_DAY")

        if bar.datetime.hour == 22 and bar.datetime.minute >= 50:
            self.fsm.onEvent('DAY_CLOSE')

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
        print_log("onOrder(): orderTime = %r ; vtOrderID = %r; status = %s" % (order.orderTime, order.vtOrderID, order.status))
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
        #self.last_traded_order = trade
        print_log("onTrade(): volume= %r, direction= %s; price= %r" %(trade.volume, trade.direction, trade.price))
        f = 1 if trade.direction==DIRECTION_LONG else -1
        pos_cost = self.pos_cost_dict.get(trade.vtSymbol,{})
        if not pos_cost:
            self.pos_cost_dict[trade.vtSymbol] = {'position': trade.volume * f, 'average_cost': trade.price}
        else:
            sum_cost = pos_cost['position'] * pos_cost['average_cost'] + trade.volume * f * trade.price
            pos_cost['position'] += trade.volume * f
            pos = pos_cost['position']
            if pos!= 0:
                pos_cost['average_cost'] = sum_cost / pos_cost['position']
            else:
                pos_cost['average_cost'] = 0
        print_log(str(self.pos_cost_dict))



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
    engine.setStartDate('20130101')
    #engine.setEndDate('20160101')
    
    # 载入历史数据到引擎中
    engine.setDatabase(MINUTE_DB_NAME, BACKTESTING_SYMBOL)
    
    # 设置产品相关参数
    engine.setSlippage(2*TICK_SIZE)     # 股指1跳
    engine.setRate(2/10000)   # 万0.3
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