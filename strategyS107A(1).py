# encoding: UTF-8
"""
dual thrust
"""
from __future__ import division

import copy
import cPickle
import math
from copy import copy
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import talib

import vtPath
from ctaBase import *
from ctaTemplate2 import CtaTemplate2
from my_module.my_buffer import deque_buffer
from ta.funcs import *
from vtConstant import *

MAX_NUMBER = 10000000
MIN_NUMBER = 0

__BACKTESTING__ = True
BACKTESTING_SYMBOL = 'rb9999'
TICK_SIZE = 1
STATE_FILE = 'temp/state.S107A'
if __BACKTESTING__:
    STATE_FILE += '.backtesting'

TRADE_MAP = {}



def tick_is_history(tick):
    return tick.__dict__.get('isHistory', False)

def save_state(state):
    """保存状态到文件"""
    d = {}
    d['state_class'] = state.__class__
    d['last_traded_order'] = state.last_traded_order
    d['intra_trade_high'] = state.intra_trade_high
    d['intra_trade_low'] = state.intra_trade_low
    d['hist_hlc_dict'] = state.hist_hlc_dict
    d['direction'] = state.direction
    try:
        with open(STATE_FILE, 'w') as f:
            data = cPickle.dumps(d)
            f.write(data)
    except Exception as e:
        print str(e)

def load_state(strategy):
    """载入状态"""
    fsm = State(strategy)
    try:
        with open(STATE_FILE, 'r') as f:
            data = cPickle.load(f)
            fsm.__class__ = data['state_class']
            fsm.last_traded_order = data['last_traded_order']
            fsm.intra_trade_high = data['intra_trade_high']
            fsm.intra_trade_low = data['intra_trade_low']
            fsm.hist_hlc_dict = data['hist_hlc_dict']
            fsm.direction = data['direction']
            return fsm
    except Exception as e:
        print(u'状态文件不存在或被破坏:'+str(e))
        return None

# 主状态基类
class State:
    fail_cnt = 0
    working_vtOrderId = ''
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
        #save_state(self)

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
        pnl = self.calc_pnl(self.strategy.lastTick.lastPrice)
        need_sl =  pnl < -self.strategy.stoploss_value
        #3
        # if self.direction==DIRECTION_LONG:
        #     need_sl = need_sl or self.strategy.lastPrice < self.strategy.today_open
        # elif self.direction==DIRECTION_SHORT:
        #     need_sl = need_sl or self.strategy.lastPrice > self.strategy.today_open
        if need_sl:
            self.strategy.writeStrategyLog('[stoploss]: pnl=%r' %pnl)
        return need_sl



    def need_trailing_stoploss(self):
        need_sl = False
        if self.direction == DIRECTION_LONG:
            need_sl = self.strategy.lastTick.lastPrice < self.intra_trade_high *(1 - self.strategy.trailing_percentage/100.0)
            #need_sl = self.strategy.lastPrice < self.intra_trade_high - self.strategy.stoploss_value
        elif self.direction == DIRECTION_SHORT:
            need_sl = self.strategy.lastTick.lastPrice > self.intra_trade_low * (1 + self.strategy.trailing_percentage/100.0)
            #need_sl = self.strategy.lastPrice > self.intra_trade_low + self.strategy.stoploss_value
        if need_sl:
            self.strategy.writeStrategyLog('[trailing]')
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
        self.strategy.writeStrategyLog('Init...')
        try:
            ticks = self.strategy.loadTick(self.strategy.vtSymbol, 5)
            for tick in ticks:
                tick.isHistory= True
                self.strategy.onTick(tick)
            del ticks
        except Exception as e:
            print str(e)
        # 0 ---> 7
        saved = None
        if not __BACKTESTING__:
            saved = load_state(self.strategy)
        if saved and saved.__class__ != State0:
            self.strategy.writeStrategyLog('0 ---> loaded_state') 
            self.new_state(saved.__class__)
            self.__dict__ = saved.__dict__
        else:
            self.strategy.writeStrategyLog('0 ---> 7')
            self.new_state(State7)

    def inState(self):
        pass

class State1(State):
    """Waiting for trading signal"""
    def onEnterState(self):
        self.fail_cnt = 0
        self.strategy.writeStrategyLog('*'*100)
        self.strategy.writeStrategyLog('Enter S1')
        #self.direction = DIRECTION_UNKNOWN
        # recalculate HH, HC, LC, L
        self.hist_hlc_dict = self.strategy.calc_hlc_from_buffer()
        today_open = self.strategy.today_open
        m = max(self.hist_hlc_dict['HH']-self.hist_hlc_dict['LC'], self.hist_hlc_dict['HC']-self.hist_hlc_dict['LL'])
        self.long_trigger = today_open + m * self.strategy.k1 / math.sqrt(self.strategy.N)
        self.short_trigger = today_open - m * self.strategy.k2 / math.sqrt(self.strategy.N)
        self.strategy.writeStrategyLog('S1: open = %.1f, long_trigger = %.1f, short_trigger = %.1f' %(today_open, self.long_trigger, self.short_trigger))
        #2self.strategy.writeCtaLog('trend_index = %f' %self.strategy.get_trend_index())
        
        self.new_state(State1cd)

class State1cd(State):
    """Waiting for trading signal"""
    def onEnterState(self):
        self.strategy.writeStrategyLog('Enter S1cd')
        self.strategy.writeStrategyLog('last=%.1f 60m=%.1f 4h=%.1f 1d=%.1f 1w=%.1f'%(self.strategy.lastTick.lastPrice, self.strategy.SMA31_60m, self.strategy.SMA31_4h, self.strategy.SMA31_1d, self.strategy.SMA31_1w))
        
        save_state(self)

    def inState(self):
        # if self.strategy.get_trend_index() > 0.02:
        #     return
        #if new trading day and breakthough
        # check up_break or down_break
        if not __BACKTESTING__:
            self.strategy.writeStrategyLog('[S1cd] %s: LastPrice=%.2f Long_Trig=%.2f Short_Trig=%.2f'%(self.strategy.lastTick.vtSymbol,self.strategy.lastTick.lastPrice, self.long_trigger, self.short_trigger))
        self.update_intra_trade_data()
        #check stoploss
        if self.need_stoploss():
            # 1cd ---> 5
            self.strategy.writeStrategyLog('1cd ---> 5 : stop loss')
            self.new_state(State5)
            return
        if self.need_trailing_stoploss():
            # 1cd ---> 5
            self.strategy.writeStrategyLog('1cd ---> 5 : trailing')
            self.new_state(State5)
            return
        if self.strategy.lastTick.lastPrice > self.long_trigger and self.strategy.long_prelimitary:
            self.strategy.writeStrategyLog('last=%.1f 60m=%.1f 4h=%.1f 1d=%.1f 1w=%.1f'%(self.strategy.lastTick.lastPrice, self.strategy.SMA31_60m, self.strategy.SMA31_4h, self.strategy.SMA31_1d, self.strategy.SMA31_1w))
            self.strategy.writeStrategyLog('last=%.1f 60mp=%.1f 4hp=%.1f 1dp=%.1f 1wp=%.1f'%(self.strategy.lastTick.lastPrice, self.strategy.SMA31_60m_p, self.strategy.SMA31_4h_p, self.strategy.SMA31_1d_p, self.strategy.SMA31_1w_p))
            #print self.strategy.lastPrice, self.strategy.lastTick.lastPrice, self.long_trigger
            self.direction = DIRECTION_LONG
            # 1cd ---> 2
            self.strategy.writeStrategyLog('1cd ---> 2: LONG Triggered')
            self.new_state(State2)
        elif self.strategy.lastTick.lastPrice < self.short_trigger and self.strategy.short_prelimitary:
            #print self.strategy.lastPrice, self.strategy.lastTick.lastPrice, self.long_trigger
            self.strategy.writeStrategyLog('last=%.1f 60m=%.1f 4h=%.1f 1d=%.1f 1w=%.1f'%(self.strategy.lastTick.lastPrice, self.strategy.SMA31_60m, self.strategy.SMA31_4h, self.strategy.SMA31_1d, self.strategy.SMA31_1w))
            self.strategy.writeStrategyLog('last=%.1f 60mp=%.1f 4hp=%.1f 1dp=%.1f 1wp=%.1f'%(self.strategy.lastTick.lastPrice, self.strategy.SMA31_60m_p, self.strategy.SMA31_4h_p, self.strategy.SMA31_1d_p, self.strategy.SMA31_1w_p))
            self.direction = DIRECTION_SHORT
            # 1cd ---> 2
            self.strategy.writeStrategyLog('1cd ---> 2: SHORT Triggered')
            self.new_state(State2)
    
    def onEvent(self, event_type):
        if event_type == "NEW_DAY":
            # 1cd ---> 1
            self.strategy.writeStrategyLog('1cd ---> 1: NEW_DAY')
            self.new_state(State1)
            return
        # if event_type == "MARKET_CLOSE":
        #     # 1cd ---> 1
        #     self.strategy.writeCtaLog('1cd ---> 8: MARKET CLOSE')
        #     self.last_state = self.__class__
        #     self.new_state(State8)
        #     return

class State2(State):
    """Open"""
    def onEnterState(self):
        self.strategy.writeStrategyLog('Enter S2')
        # sendorder
        pos = self.strategy.pos.get(self.strategy.vtSymbol, 0)
        self.strategy.writeStrategyLog('pos=%r'%pos)
        if pos > 0:
            #hold long
            if self.direction == DIRECTION_LONG:
                if pos >= self.strategy.max_volume:
                    # 2 ---> 4
                    self.strategy.writeStrategyLog('2 ---> 4: MAX_POS LONG')
                    self.new_state(State4)
                    return
            else:
                # close first
                self.working_vtOrderId = self.strategy.sendOrder(self.strategy.vtSymbol, CTAORDER_SELL, self.strategy.lastTick.lastPrice - 10 * TICK_SIZE, pos)
                # 2 ---> 2cd
                self.strategy.writeStrategyLog('2 ---> 2cd: LONG TO SHORT, CLOSE LONG')
                self.new_state(State2cd)
                return
        elif pos < 0:
            #hold short
            if self.direction == DIRECTION_SHORT:
                if abs(pos) >= self.strategy.max_volume:
                    # 2 ---> 4
                    self.strategy.writeStrategyLog('2 ---> 4: MAX_POS SHORT')
                    self.new_state(State4)
                    return
            else:
                # close first
                self.working_vtOrderId = self.strategy.sendOrder(self.strategy.vtSymbol, CTAORDER_COVER, self.strategy.lastTick.lastPrice + 10 * TICK_SIZE, -pos)
                # 2 ---> 2cd
                self.strategy.writeStrategyLog('2 ---> 2cd: SHORT TO LONG, CLOSE SHORT')
                self.new_state(State2cd)
                return
        
        direction = CTAORDER_BUY if self.direction == DIRECTION_LONG else CTAORDER_SHORT
        f = 1 if direction == CTAORDER_BUY else -1
        self.working_vtOrderId = self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastTick.lastPrice + f * 10 * TICK_SIZE, self.strategy.volume)
        # 2 ---> 3
        self.strategy.writeStrategyLog('2 ---> 3: OPEN %s'%self.direction)
        self.new_state(State3)
        return

    def inState(self):
        pass

class State2alt(State):
    """Open alt"""
    def onEnterState(self):
        self.strategy.writeStrategyLog('Enter S2alt')
        self.fail_cnt += 1
        if self.fail_cnt <= 5:
            # sendorder
            pos = self.strategy.pos.get(self.strategy.vtSymbol, 0)
            self.strategy.writeStrategyLog('pos=%r'%pos)
            if pos > 0:
                #hold long
                if self.direction == DIRECTION_LONG:
                    if pos >= self.strategy.max_volume:
                        # 2 ---> 4
                        self.strategy.writeStrategyLog('2 ---> 4: MAX_POS LONG')
                        self.new_state(State4)
                        return
                else:
                    # close first
                    self.working_vtOrderId = self.strategy.sendOrder(self.strategy.vtSymbol, CTAORDER_SHORT, self.strategy.lastTick.lastPrice - 10 * TICK_SIZE, pos)
                    # 2 ---> 2cd
                    self.strategy.writeStrategyLog('2 ---> 2cd: LONG TO SHORT, CLOSE LONG')
                    self.new_state(State2cd)
                    return
            elif pos < 0:
                #hold short
                if self.direction == DIRECTION_SHORT:
                    if abs(pos) >= self.strategy.max_volume:
                        # 2 ---> 4
                        self.strategy.writeStrategyLog('2 ---> 4: MAX_POS SHORT')
                        self.new_state(State4)
                        return
                else:
                    # close first
                    self.working_vtOrderId = self.strategy.sendOrder(self.strategy.vtSymbol, CTAORDER_BUY, self.strategy.lastTick.lastPrice + 10 * TICK_SIZE, -pos)
                    # 2 ---> 2cd
                    self.strategy.writeStrategyLog('2 ---> 2cd: SHORT TO LONG, CLOSE SHORT')
                    self.new_state(State2cd)
                    return
            
            direction = CTAORDER_BUY if self.direction == DIRECTION_LONG else CTAORDER_SHORT
            f = 1 if direction==CTAORDER_BUY else -1
            self.working_vtOrderId = self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastTick.lastPrice + f * 10 * TICK_SIZE, self.strategy.volume)
            # 2 ---> 3
            self.strategy.writeStrategyLog('2 ---> 3: OPEN %s'%self.direction)
            self.new_state(State3)
            return
        else:
            self.new_state(EndState)
            return


    def inState(self):
        pass

class State2cd(State):
    "Closing remaining position"
    def onEnterState(self):
        pass
    def inState(self):
        if self.strategy.all_traded.get(self.working_vtOrderId, False) == True:
            # 2cd ---> 2
            self.reset_intra_trade_data()
            self.strategy.writeStrategyLog('2cd ---> 2: Closed, RE-OPEN')
            self.new_state(State2)
            return
        if self.strategy.all_traded.get(self.working_vtOrderId, False) == 'rejected':
            # 2cd ---> 2o
            self.new_state(State2alt)
            return

class State3(State):
    """Opening"""
    def onEnterState(self):
        pass
        #self.strategy.writeCtaLog('Enter S3')

    def inState(self):
        if self.strategy.all_traded.get(self.working_vtOrderId, False) == True:
            #self.last_traded_order = copy(self.strategy.last_traded_order)
            self.last_traded_time = copy(self.strategy.last_traded_time)
            # 3 ---> 4
            self.strategy.writeStrategyLog('3 ---> 4: Opened')
            self.new_state(State4)
    def onEvent(self, event_type):
        pass
        #self.new_state(State1)

class State4(State):
    """idle : stop loss check"""
    def onEnterState(self):
        self.strategy.writeStrategyLog('Enter S4')
        self.update_cost_data()
        save_state(self)

    def inState(self):
        self.update_intra_trade_data()
        if not __BACKTESTING__:
            self.strategy.writeStrategyLog('[S4] %s: LastPrice=%.2f HIGH=%.2f LOW=%.2f'%(self.strategy.vtSymbol, self.strategy.lastTick.lastPrice, self.intra_trade_high, self.intra_trade_low))
        if self.need_stoploss():
            # 4 ---> 5
            self.strategy.writeStrategyLog('4 ---> 5: stoploss')
            self.new_state(State5)
            return
        if self.need_trailing_stoploss():
            # 4 ---> 5
            self.strategy.writeStrategyLog('4 ---> 5: trailing')
            self.new_state(State5)
            return
    
    def onEvent(self, event_type):
        if event_type == "NEW_DAY":
            self.strategy.writeStrategyLog('4 ---> 1: NEW_DAY')
            self.new_state(State1)
        elif event_type == "DAY_CLOSE":
            #self.new_state(State5)
            pass

class State5(State):
    """Close"""
    def onEnterState(self):
        self.strategy.writeStrategyLog('Enter S5')
        # sendorder
        direction = CTAORDER_SELL if self.direction==DIRECTION_LONG else CTAORDER_COVER
        f = 1 if self.direction==DIRECTION_LONG else -1

        volume = self.strategy.volume
        pos_cost = self.strategy.pos_cost_dict.get(self.strategy.vtSymbol,{})
        if pos_cost:
            volume = pos_cost.get('position',0)
        self.working_vtOrderId = self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastTick.lastPrice - f * 10 * TICK_SIZE, abs(volume))
        # 5 ---> 6
        self.strategy.writeStrategyLog('5 ---> 6: %s' %direction)
        self.new_state(State6)
        return

    def inState(self):
        pass

class State5alt(State):
    """Close alt"""
    def onEnterState(self):
        self.fail_cnt += 1
        if self.fail_cnt <= 5:
            self.strategy.writeStrategyLog('Enter S5alt')
            # sendorder
            direction = CTAORDER_SHORT if self.direction==DIRECTION_LONG else CTAORDER_BUY
            f = 1 if self.direction==DIRECTION_LONG else -1

            volume = self.strategy.volume
            pos_cost = self.strategy.pos_cost_dict.get(self.strategy.vtSymbol,{})
            if pos_cost:
                volume = pos_cost.get('position',0)
            self.working_vtOrderId = self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastTick.lastPrice - f * 10 * TICK_SIZE, abs(volume))
            # 5 ---> 6
            self.strategy.writeStrategyLog('5alt ---> 6: %s' %direction)
            self.new_state(State6)
            return
        else:
            self.new_state(EndState)
            return

    def inState(self):
        pass

class State6(State):
    """Closing"""
    def onEnterState(self):
        pass

    def inState(self):
        if self.strategy.all_traded.get(self.working_vtOrderId, False) == True:
            # 6 ---> 7
            self.reset_intra_trade_data()
            self.strategy.writeStrategyLog('6 ---> 7: CLOSED')
            self.new_state(State7)
            return
        if self.strategy.all_traded.get(self.working_vtOrderId, False) == 'rejected':
            # 6 ---> 5o
            self.new_state(State5alt)
            return
    
class State7(State):
    """Idle, wait for new day"""
    def onEnterState(self):
        self.strategy.writeStrategyLog('Enter S7')
        self.direction = DIRECTION_UNKNOWN
        save_state(self)
    def inState(self):
        pass
    def onEvent(self, event_type):
        if event_type == 'NEW_DAY':
            # 7 ---> 1
            self.strategy.writeStrategyLog('7 ---> 1: NEW_DAY')
            self.new_state(State1)

class EndState(State):
    """EndState"""
    def onEnterState(self):
        self.strategy.writeStrategyLog('Enter EndState')
        self.direction = DIRECTION_UNKNOWN
    def inState(self):
        pass
    def onEvent(self, event_type):
        pass


########################################################################
class S107AStrategy(CtaTemplate2):
    
    className = 'S107AStrategy'
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
    # 程序启动算新一天
    allow_startup_newday = True
    #------------------------------------------------------------------------
    # 策略变量
    bufferSize = N * 300 
    count = 0
    lastTick = None
    bar = CtaBarData()
    bar_hour = CtaBarData()
    bar_4h = CtaBarData()
    bar_day = CtaBarData()
    bar_week = CtaBarData()
    bar_5min = CtaBarData()
    barMinute = EMPTY_STRING
    barDate = EMPTY_STRING
    barWeek = EMPTY_STRING
    lastTickTime1 = lastTickTime4 = None

    max_len = 50
    barArray = deque_buffer(bufferSize)
    closeArray = deque_buffer(bufferSize)
    ddArray = deque_buffer(bufferSize)
    rddArray = deque_buffer(bufferSize)
    
    # K线
    close_history_60m = []
    close_history_4h = []
    close_history_1d = []
    close_history_1w = []
    close_arr_60m = np.array([np.nan])
    close_arr_4h = np.array([np.nan])
    close_arr_1d = np.array([np.nan])
    close_arr_1w = np.array([np.nan])
    last_day = None

    SMA31_1w_p = None
    SMA31_1d_p = None
    SMA31_4h_p = None
    SMA31_60m_p = None

    pos_cost_dict = {}


    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(S107AStrategy, self).__init__(ctaEngine, setting)
        #self.lastPrice = 0.0
        self.barSeries_1min = []

        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）        
        self.all_traded = {}
        if __BACKTESTING__:
            self.log_str = ''
            self.data = {'close':[], 'trend_index':[]}
    #----------------------------------------------------------------
    def writeStrategyLog(self, log_str):
        self.writeCtaLog(log_str)
        d = {}
        d['data'] = log_str
        d['type'] = 'LOG'
        self.insertStrategyData(d)
    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeStrategyLog(u'%s策略初始化' %self.name)
        if not __BACKTESTING__:
            self.vtSymbol = self.vtSymbols[0]
        else:
            self.vtSymbol = BACKTESTING_SYMBOL
        
        self.fsm = State(self)
        self.fsm.new_state(State0)

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeStrategyLog(u'%s策略启动' %self.name)

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        if self.fsm.__class__ in [State1cd, State4, State7]:
            save_state(self.fsm)
        self.writeStrategyLog(u'%s策略停止' %self.name)

    @staticmethod
    def updateKLine(tick, close_array):
        # 新K线初始化
        if(np.isnan(close_array[-1])):
            close_array[-1] = tick.lastPrice
        # 更新收盘价
        close_array[-1] = tick.lastPrice


    @staticmethod
    def updateHistory(bar, close_history, max_len):
        close_history.append(bar.close)
        if len(close_history) > max_len:
            close_history.pop(0)

    @staticmethod
    def new_bar_time(lasttime, t, period):
        if lasttime is None and t is not None:
            return True
        if period == '1h':
            hours = [(time(9,0,0), time(10,0,0)),
                    (time(10,0,0), time(11,15,0)),
                    (time(11,15,0), time(14,15,0)),
                    (time(14,15,0), time(15,0,0)),
                    (time(21,0,0), time(22,0,0)),
                    (time(22,0,0), time(23,59,59))]
        elif period == '4h':
            hours = [(time(11,15,0), time(15,0,0)),
                    (time(21,0,0), time(23,59,59))]
        index_l = index = -1
        i = 0
        for start,end in hours:
            if start <= lasttime < end:
                index_l = i
            if start <= t < end:
                index = i
            i += 1
        if period == '1h':
            if index - index_l > 0 or index_l == 5 and index == 0:
                return True
        elif period == '4h':
            if index - index_l == 1 or index - index_l == -1:
                return True
        return False
    #-----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        if not (self.isTickValid(tick) or tick.__dict__.get('isHistory', False)) :
            return

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
        
        # 聚合为1小时K线
        time1 = tick.datetime.time()
        if self.new_bar_time(self.lastTickTime1, time1, '1h'):
            # time cross time line
            if self.bar_hour:
                self.onBar_1h(self.bar_hour)

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

            self.bar_hour = bar                  # 这种写法为了减少一层访问，加快速度
            self.lastTickTime1 = time1     # 更新当前的分钟
        else:                               # 否则继续累加新的K线
            bar = self.bar_hour                  # 写法同样为了加快速度
            bar.high = max(bar.high, tick.lastPrice)
            bar.low = min(bar.low, tick.lastPrice)
            bar.close = tick.lastPrice

        # 聚合为4小时K线
        time4 = tick.datetime.time()
        if self.new_bar_time(self.lastTickTime4, time4, '4h'):
            # time cross time line
            if self.bar_4h:
                self.onBar_4h(self.bar_4h)

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

            self.bar_4h = bar                  # 这种写法为了减少一层访问，加快速度
            self.lastTickTime4 = time4     # 更新当前的分钟
        else:                               # 否则继续累加新的K线
            bar = self.bar_4h                  # 写法同样为了加快速度
            bar.high = max(bar.high, tick.lastPrice)
            bar.low = min(bar.low, tick.lastPrice)
            bar.close = tick.lastPrice

        # 聚合为日K线
        tickDay = tick.datetime.day
        if tickDay != self.barDate:
            if self.bar_day:
                self.onBar_day(self.bar_day)

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

            self.bar_day = bar                  # 这种写法为了减少一层访问，加快速度
            self.barDate = tickDay     # 更新当前的分钟
        else:                               # 否则继续累加新的K线
            bar = self.bar_day                  # 写法同样为了加快速度
            bar.high = max(bar.high, tick.lastPrice)
            bar.low = min(bar.low, tick.lastPrice)
            bar.close = tick.lastPrice

        # 聚合为周K线
        tickYear, tickWeek, tickWeekday = tick.datetime.isocalendar()
        if tickWeek != self.barWeek:
            if self.bar_week:
                self.onBar_week(self.bar_week)

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

            self.bar_week = bar                  # 这种写法为了减少一层访问，加快速度
            self.barWeek = tickWeek     # 更新当前的分钟
        else:                               # 否则继续累加新的K线
            bar = self.bar_week                  # 写法同样为了加快速度
            bar.high = max(bar.high, tick.lastPrice)
            bar.low = min(bar.low, tick.lastPrice)
            bar.close = tick.lastPrice

        S107AStrategy.updateKLine(tick, self.close_arr_60m)
        S107AStrategy.updateKLine(tick, self.close_arr_4h)
        S107AStrategy.updateKLine(tick, self.close_arr_1d)
        S107AStrategy.updateKLine(tick, self.close_arr_1w)
        #-------------------------------------------------------------
        # prelimitaries
        self.SMA31_1w = SMA_shift(self.close_arr_1w)
        self.SMA31_1d = SMA_shift(self.close_arr_1d)
        self.SMA31_4h = SMA_shift(self.close_arr_4h)
        self.SMA31_60m = SMA_shift(self.close_arr_60m)

        self.SMA31_1w_p = SMA_shift(self.close_arr_1w[:-1])
        self.SMA31_1d_p = SMA_shift(self.close_arr_1d[:-1])
        self.SMA31_4h_p = SMA_shift(self.close_arr_4h[:-1])
        self.SMA31_60m_p = SMA_shift(self.close_arr_60m[:-1])

        self.long_prelimitary = tick.lastPrice > max([self.SMA31_1w, self.SMA31_1d, self.SMA31_4h, self.SMA31_60m])
        self.long_prelimitary_a = self.SMA31_1w > self.SMA31_1w_p \
            and self.SMA31_1d > self.SMA31_1d_p \
            and self.SMA31_4h > self.SMA31_4h_p \
            and self.SMA31_60m > self.SMA31_60m_p

        self.short_prelimitary = tick.lastPrice < min([self.SMA31_1w, self.SMA31_1d, self.SMA31_4h, self.SMA31_60m])
        self.short_prelimitary_a = self.SMA31_1w < self.SMA31_1w_p \
            and self.SMA31_1d < self.SMA31_1d_p \
            and self.SMA31_4h < self.SMA31_4h_p \
            and self.SMA31_60m < self.SMA31_60m_p

        
        #-------------------------------------------------------------
        if not tick_is_history(tick) and self.fsm.__class__ != State0:
            if tick.datetime.day != self.last_day:
                self.last_day = tick.datetime.day
                self.today_open = tick.lastPrice
                if self.allow_startup_newday or self.in_newday_period():
                    log_str = 'new day:%s'%str(self.get_now_time())
                    self.writeStrategyLog(log_str)

                    self.fsm.onEvent("NEW_DAY")

        self.fsm.inState()
    #----------------------------------------------------------------------
    def create_minute_aggregator(self, period):
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
                    #bar_aggr.close_ = bar.close_
                
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
        #self.lastPrice = bar.close
        self.lastBar = bar
        self.barArray.push_back(bar)
        self.closeArray.push_back(bar.close)
        self.update_dd_rdd_buffer()
        if __BACKTESTING__:
            self.data['close'].append(bar.close)
            self.data['trend_index'].append(self.get_trend_index())


        if __BACKTESTING__:
            self.lastTick = CtaTickData()
            self.lastTick.lastPrice = bar.close
            self.lastTick.datetime = bar.datetime

        
        self.barSeries_1min.append(bar)

        self.fsm.inState()


    #----------------------------------------------------------------------
    def onBar_1h(self, bar):
        self.writeStrategyLog('onBar 1h %.1f %s'%(bar.close, bar.datetime))
        S107AStrategy.updateHistory(bar, self.close_history_60m, self.max_len)
        self.close_arr_60m = np.array(self.close_history_60m + [np.nan])

    #----------------------------------------------------------------------
    def onBar_4h(self, bar):
        self.writeStrategyLog('onBar 4h %.1f %s'%(bar.close, bar.datetime))
        S107AStrategy.updateHistory(bar, self.close_history_4h, self.max_len)
        self.close_arr_4h = np.array(self.close_history_4h + [np.nan])

    #----------------------------------------------------------------------
    def onBar_day(self, bar):
        S107AStrategy.updateHistory(bar, self.close_history_1d, self.max_len)
        self.close_arr_1d = np.array(self.close_history_1d + [np.nan])

    #----------------------------------------------------------------------
    def onBar_week(self, bar):
        S107AStrategy.updateHistory(bar, self.close_history_1w, self.max_len)
        self.close_arr_1w = np.array(self.close_history_1w + [np.nan])

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        self.writeStrategyLog("onOrder(): orderTime = %r ; vtOrderID = %r; status = %s" % (order.orderTime, order.vtOrderID, order.status))
        d = order.__dict__
        d['type'] = 'ORDER'
        d['addition_info_anything'] = {'foo':'anything', 'fun':'can_be_dictionary'}
        self.insertStrategyData(d)
        if order.status == STATUS_ALLTRADED:
            self.all_traded[order.vtOrderID] = 'onOrder'
            self.last_traded_time = self.get_now_time()
        if order.status == STATUS_REJECTED:
            self.all_traded[order.vtOrderID] = 'rejected'
        self.fsm.inState()

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        global TRADE_MAP
        TRADE_MAP[trade.vtOrderID] = trade
        ###########################
        d = trade.__dict__
        d['type'] = 'TRADE'
        d['addition_info_anything'] = {'foo':'anything', 'fun':'can_be_dictionary'}
        self.insertStrategyData(d)
        ###########################
        self.writeStrategyLog("onTrade(): volume= %r, direction= %s; price= %r" %(trade.volume, trade.direction, trade.price))
        if self.all_traded.get(trade.vtOrderID, False) == 'onOrder':
            self.all_traded[trade.vtOrderID] = True
        f = 1 if trade.direction == DIRECTION_LONG else -1
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
        self.fsm.inState()

    #----------------------------------------------------------------------
    def get_now_time(self):
        if __BACKTESTING__:
            if self.lastTick:
                return self.lastTick.datetime
            else:
                return datetime(1970, 1, 1)
        else:
            return datetime.now()

    #----------------------------------------------------------------------
    def isTickValid(self, tick):
        if not __BACKTESTING__:
            if tick is None:
                self.writeStrategyLog('invalid tick: None')
                return False
            if tick.__dict__.get('isHistory', False):
                return True
            if tick.vtSymbol != self.vtSymbol:
                self.writeStrategyLog('invalid tick: vtSymbol mismatch')
                return False
            if tick.lastPrice <= 0:
                self.writeStrategyLog('invalid tick: tick price <= 0')
                return False
            if not self.ismarketopen():
                self.writeStrategyLog('invalid tick: market not open')
                return False
            time_delta = abs(tick.datetime - self.get_now_time())
            if time_delta.total_seconds() > 120:
                self.writeStrategyLog(str(tick.datetime)+':'+str(self.get_now_time()))
                self.writeStrategyLog('invalid tick: tick time mismatch')
                return False
        if not self.tick_in_marketopen_period(tick):
            self.writeStrategyLog('invalid tick: not in trading time')
            return False
        return True
    
    #---------------------------------------------
    def in_newday_period(self):
        """开盘时段"""
        now_time = self.get_now_time()
        sections = [(time( 8, 59, 30), time( 9, 00, 30))]
        for sec in sections:
            if now_time > sec[0] and now_time < sec[1]:
                return True
        return False

    def ismarketopen(self):
        '''SHFE是否开市，CME开市时间覆盖SHFE，边界时间均离开交易所时间3s以保证下单安全'''
        invalid_sections = [(time(0,0,0), time(9,0,1)),
                       (time(10,14,57), time(10,30,1)),
                       (time(11,29,57), time(13,30,1)),
                       (time(14,59,57), time(21,0,1)),
                       (time(22,59,57), time(23,59,59))]
        for sec in invalid_sections:
            if tmpTime > sec[0] and tmpTime < sec[1]:
                return False
        return True

    def tick_in_marketopen_period(self, tick):
        '''SHFE是否开市，CME开市时间覆盖SHFE，边界时间均离开交易所时间3s以保证下单安全'''
        invalid_sections = [(time(0,0,0), time(9,0,0)),
                       (time(10,15,0), time(10,30,0)),
                       (time(11,30,0), time(13,30,0)),
                       (time(15,00,0), time(21,0,0)),
                       (time(23,00,0), time(23,59,59))]
        tmpTime = tick.datetime.time()
        for sec in invalid_sections:
            if tmpTime > sec[0] and tmpTime < sec[1]:
                return False
        return True


def backtesting():
    # 以下内容是一段回测脚本的演示，用户可以根据自己的需求修改
    # 建议使用ipython notebook或者spyder来做回测
    # 同样可以在命令模式下进行回测（一行一行输入运行）
    import vtPath
    from ctaBacktesting import BacktestingEngine
    
    # 创建回测引擎
    engine = BacktestingEngine()
    
    # 设置引擎的回测模式为K线
    engine.setBacktestingMode(engine.TICK_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate('20170101', 5)
    engine.setEndDate('20180501')
    
    # 载入历史数据到引擎中
    engine.setDatabase(TICK_DB_NAME, BACKTESTING_SYMBOL)
    
    # 设置产品相关参数
    engine.setSlippage(1*TICK_SIZE)     # 股指1跳
    engine.setRate(2/10000)   # 万0.3
    engine.setSize(1)         # 股指合约大小    
    
    # 在引擎中创建策略对象
    engine.initStrategy(S107AStrategy, {})
    
    # 开始跑回测
    engine.runBacktesting()
    
    # 显示回测结果
    # spyder或者ipython notebook中运行时，会弹出盈亏曲线图
    # 直接在cmd中回测则只会打印一些回测数值
    try:
        engine.showBacktestingResult()
    except Exception as e:
        print str(e)
