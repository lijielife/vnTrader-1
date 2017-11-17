# encoding: UTF-8

"""
简单双品种套利
"""
import collections
import copy
# cPickle序列化
import cPickle
import datetime as dt
import json
from datetime import datetime, time, timedelta
from random import randint

import pandas as pd
#from statsmodels.tsa import stattools
import statsmodels.api as smapi
from business_calendar import Calendar
from pandas import DataFrame, Series
from statsmodels.sandbox.regression.predstd import wls_prediction_std

from ctaBase import *
from ctaTask import CtaTask, CtaTaskResult
from ctaTemplate2 import CtaTemplate2
from vtConstant import *
from vtFunction import todayDate

# 状态机数量，对应最大加仓次数
FSM_CNT = 1

# vtOrderID 与 FSM state_id的map
vtOrderID_FSM_map = {}

#--------------------------------------------------------------------------

def calc_spread_from_model(price_act, price_pas, ols_beta):
    """按照回归模型计算价差，价差 = 国内黄金 - 回归预测(国外黄金的人民币价格)"""
    if price_act > 0 and price_pas > 0 :
        try:
            price_act_predicted = ols_beta['x'] * price_pas + ols_beta['intercept']
            return price_act - price_act_predicted
        except:
            pass
    else:
        raise ValueError(u'无效的参数')

def ismarketopen():
    '''SHFE的hc,rb是否开市，边界时间离开交易所时间3s以保证下单安全'''
    invalid_sections = [(time(0,0,0), time(9,0,1)),
                       (time(10,14,57), time(10,30,1)),
                       (time(11,29,57), time(13,30,1)),
                       (time(14,59,57), time(21,0,1)),
                       (time(22,59,57), time(23,59,59))]
    tmpTime = dt.datetime.now().time()
    for sec in invalid_sections:
        if tmpTime > sec[0] and tmpTime < sec[1]:
            return False
    return True

def take_snapshot(data, **kwargs):
    """开平仓前，记录策略中变量的快照， 返回一个字典，用于后续插入数据库"""
    # 线性回归模型的斜率和截距
    ols_beta = data['MyTask_result_data']['ols_beta']
    # 线性回归模型的 R2
    ols_R2 = data['MyTask_result_data']['ols_R2']
    # 真实价差的标准差
    spread_std = data['MyTask_result_data']['spread_std']
    # 开平仓标志
    open_close = 'unknown'
    # 做多或做空价差标志
    long_short = 'unknown'
    # 开平仓的品种
    vtSymbol = 'unknown'
    # 委托价
    order_price = -1
    # 委托手数
    order_volume = -1

    if 'vtSymbol' in kwargs:
        vtSymbol = kwargs['vtSymbol']
    if 'open_close' in kwargs:
        open_close = kwargs['open_close']
    if 'long_short' in kwargs:
        long_short = kwargs['long_short']
    if 'order_price' in kwargs:
        order_price = kwargs['order_price']
    if 'order_volume' in kwargs:
        order_volume = kwargs['order_volume']

    snapshot = {'localtime':dt.datetime.now(),
                'vtSymbol': vtSymbol,
                'open_close': open_close,
                'direction': long_short,
                'order_price': order_price,
                'volume': order_volume,
                'Stats': {'ols_beta': {'x':ols_beta['x'], 'intercept':ols_beta['intercept']}, 'ols_R2':ols_R2, 'spread_std':spread_std}}
    try:
        snapshot['lastTick_active'] = data['lastTick_active'].__dict__
        snapshot['lastTick_passive'] = data['lastTick_passive'].__dict__
    except:
        print 'lastTick not recorded'
    
    return snapshot

def save_state(states, token):
    """保存状态到文件"""
    l = []
    dic = {}
    dic['trading_token'] = token
    dic['states'] = l
    for state in states:
        d = {}
        if state.__class__ == EndState:
            state.__class__ = None
            state.nested_state.__class__ = UnknownState
        d['state_id'] = state.state_id
        d['state_class'] = state.__class__
        d['nested_state_class'] = state.nested_state.__class__
        d['alive'] = state.alive
        d['tradePrice_act'] = state.tradePrice_act
        d['tradePrice_pas'] = state.tradePrice_pas
        d['state_rand_id'] = state.rand_id
        l.append(d)
    try:
        with open(state.strategy.stateFileName, 'w') as f:
            data = cPickle.dumps(dic)
            f.write(data)
    except Exception as e:
        print str(e)


last_load_time = datetime.min
def load_state(stateFileName, states, token):
    """载入状态"""
    global last_load_time
    if datetime.now()-last_load_time < timedelta(seconds=5):
        return
    last_load_time = datetime.now()
    try:
        with open(stateFileName, 'r') as f:
            data = cPickle.load(f)
            l = data['states']
            token = data['trading_token']
            i = 0
            for d in l:
                state = states[i]
                state.state_id = int(d['state_id'])
                state.last_state_class = d['state_class']
                state.nested_state.new_state(d['nested_state_class'])
                state.alive = d['alive']
                state.tradePrice_act = d['tradePrice_act']
                state.tradePrice_pas = d['tradePrice_pas']
                state.rand_id = d['state_rand_id']
                print state.rand_id
                state.nested_state.rand_id = state.rand_id
                i += 1
    except Exception as e:
        for state in states:
            state.last_state_class = None
            state.nested_state.new_state(UnknownState)
            state.rand_id = -1 
            state.nested_state.rand_id = state.rand_id
        state.strategy.writeCtaLog(u'状态文件不存在或被破坏:'+str(e))

#------------------------------------------------------------------------
# 子状态基类
class NestedState:
    def __init__(self, strategy):
        self.strategy = strategy
        self.code = ''
    
    def new_state(self, newstate):
        self.__class__ = newstate
        self.onEnterState()

    def onEnterState(self):
        raise NotImplementedError
    
    def open_active(self):
        raise NotImplementedError
    
    def open_passive(self):
        raise NotImplementedError
    
    def close_active(self):
        raise NotImplementedError

    def close_passive(self):
        raise NotImplementedError
    
    def need_take_profit(self, spread):
        raise NotImplementedError

    def need_stop_loss(self, spread, spread_traded):
        raise NotImplementedError

#-------------------------------------------------------------------------
class UnknownState(NestedState):
    def onEnterState(self):
        pass
    
    def open_active(self):
        pass
    
    def open_passive(self):
        pass
    
    def close_active(self):
        pass

    def close_passive(self):
        pass
    
    def need_take_profit(self, spread):
        return False

    def need_stop_loss(self, spread, spread_traded):
        return False


#-------------------------------------------------------------------------
class LongSpreadState(NestedState):
    def onEnterState(self):
        print 'Enter Long Spread'
        self.code = 'b'

    def open_active(self):
        data = self.strategy.data

        direction = CTAORDER_BUY
        orderPrice = data['lastTick_active'].askPrice1# + self.strategy.priceTick_active

        snapshot = take_snapshot(data, 
                            vtSymbol=self.strategy.vtSymbol_active, 
                            open_close='open', 
                            long_short='long_spread', 
                            order_price=orderPrice,
                            order_volume=self.volume_active)

        snapshot['FSM'] = self.FSM
        snapshot['rand_id'] = self.rand_id
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                direction,#CTAORDER_SHORT,
                                orderPrice,
                                self.volume_active,
                                False, not self.strategy.fok, self.strategy.fok, False, True, append_info=snapshot)

        self.strategy.insertStrategyData(snapshot)
        return vtOrderID

    def open_passive(self):

        data = self.strategy.data

        direction = CTAORDER_SHORT
        orderPrice = self.strategy.lastTick_passive.lowerLimit #
        market = False

        snapshot = take_snapshot(data, 
                            open_close='open', 
                            long_short='long_spread', 
                            vtSymbol=self.strategy.vtSymbol_passive, 
                            order_price=orderPrice, 
                            order_volume=self.volume_passive)
        snapshot['FSM'] = self.FSM
        snapshot['rand_id'] = self.rand_id
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_passive,
                                direction,#CTAORDER_BUY,
                                orderPrice,
                                self.volume_passive,
                                False, market, False, False, True, append_info=snapshot)

        self.strategy.insertStrategyData(snapshot)
        return vtOrderID

    def close_active(self):
        data = self.strategy.data
        direction = CTAORDER_SELL
        orderPrice = data['lastTick_active'].bidPrice1# - self.strategy.priceTick_active
        

        snapshot = take_snapshot(data, 
                            open_close='close', 
                            long_short='long_spread',  
                            vtSymbol=self.strategy.vtSymbol_active, 
                            order_price=orderPrice, 
                            order_volume=self.volume_active)
        snapshot['FSM'] = self.FSM
        snapshot['rand_id'] = self.rand_id
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                direction,#CTAORDER_COVER,
                                orderPrice,
                                self.volume_active,
                                False, not self.strategy.fok, self.strategy.fok, False, True, append_info=snapshot)
        self.strategy.insertStrategyData(snapshot)
        return vtOrderID

    def close_passive(self):
        data = self.strategy.data
        
        direction = CTAORDER_COVER
        orderPrice = self.strategy.lastTick_passive.upperLimit 
        market = False

        snapshot = take_snapshot(data, 
                            open_close='close', 
                            long_short='long_spread', 
                            vtSymbol=self.strategy.vtSymbol_passive, 
                            order_price=orderPrice,
                            order_volume=self.volume_passive)
        snapshot['FSM'] = self.FSM
        snapshot['rand_id'] = self.rand_id
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_passive,
                                direction,#CTAORDER_SELL,
                                orderPrice,
                                self.volume_passive,
                                False, market, False, False, True, append_info=snapshot)
        self.strategy.insertStrategyData(snapshot)
        return vtOrderID

    def need_take_profit(self, spread):
        return spread >= -1.0 * self.close_spread

    def need_stop_loss(self, spread, spread_traded):
        return spread <= spread_traded - self.stopLoss

#-------------------------------------------------------------------------
class ShortSpreadState(NestedState):
    def onEnterState(self):
        print 'Enter Short Spread'
        self.code = 'a'
    def open_active(self):
        data = self.strategy.data

        direction = CTAORDER_SHORT
        orderPrice = data['lastTick_active'].bidPrice1# - self.strategy.priceTick_active
        

        snapshot = take_snapshot(data, 
                            vtSymbol=self.strategy.vtSymbol_active, 
                            open_close='open', 
                            long_short='short_spread', 
                            order_price=orderPrice, 
                            order_volume=self.volume_active)
        snapshot['FSM'] = self.FSM
        snapshot['rand_id'] = self.rand_id
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                direction,#CTAORDER_BUY,
                                orderPrice,
                                self.volume_active,
                                False, not self.strategy.fok, self.strategy.fok, False, True, append_info=snapshot)
        self.strategy.insertStrategyData(snapshot)
        return vtOrderID

    def open_passive(self):
        data = self.strategy.data
        direction = CTAORDER_BUY
        orderPrice = self.strategy.lastTick_passive.upperLimit
        market = False

        snapshot = take_snapshot(data, 
                            open_close='open', 
                            long_short='short_spread', 
                            vtSymbol=self.strategy.vtSymbol_passive, 
                            order_price=orderPrice, 
                            order_volume=self.volume_passive)
        snapshot['FSM'] = self.FSM
        snapshot['rand_id'] = self.rand_id
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_passive,
                                direction,#CTAORDER_SHORT,
                                orderPrice,
                                self.volume_passive,
                                False, market, False, False, True, append_info=snapshot)
        self.strategy.insertStrategyData(snapshot)
        return vtOrderID

    def close_active(self):
        data = self.strategy.data
        direction = CTAORDER_COVER
        orderPrice = data['lastTick_active'].askPrice1# + self.strategy.priceTick_active


        snapshot = take_snapshot(data, 
                            open_close='close', 
                            long_short='short_spread', 
                            vtSymbol=self.strategy.vtSymbol_active, 
                            order_price=orderPrice, 
                            order_volume=self.volume_active)
        snapshot['FSM'] = self.FSM
        snapshot['rand_id'] = self.rand_id
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                direction,#CTAORDER_SELL,
                                orderPrice,
                                self.volume_active,
                                False, not self.strategy.fok, self.strategy.fok, False, True, append_info=snapshot)
        self.strategy.insertStrategyData(snapshot)
        return vtOrderID

    def close_passive(self):
        data = self.strategy.data
        direction = CTAORDER_SELL
        orderPrice = self.strategy.lastTick_passive.lowerLimit
        market = False

        snapshot = take_snapshot(data, 
                            open_close='close', 
                            long_short='short_spread', 
                            vtSymbol=self.strategy.vtSymbol_passive, 
                            order_price=orderPrice, 
                            order_volume=self.volume_passive)
        snapshot['FSM'] = self.FSM
        snapshot['rand_id'] = self.rand_id
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_passive,
                                direction,#CTAORDER_COVER,
                                orderPrice,
                                self.volume_passive,
                                False, market, False, False,True, append_info=snapshot)
        self.strategy.insertStrategyData(snapshot)
        return vtOrderID
    
    def need_take_profit(self, spread):
        return spread <= self.close_spread

    def need_stop_loss(self, spread, spread_traded):
        return spread >= spread_traded + self.stopLoss

# 以下为主状态
#-------------------------------------------------------------------------
# 主状态基类
class State:
    strategy = None
    last_state_class = None
    state_id = 0
    alive = True
    tradePrice_act = 0
    tradePrice_pas = 0

    def __init__(self, strategy, sid):
        # 策略参数
        #------------------------------------------------------------
        self.max_total_pos = 20          # 最大持仓数（空+多）
        self.std_mult = 1                # 标准差乘数
        self.std_floor = 13              # 标准差的最小值 12 -> 20
        self.R2_floor = 0.8              # Minimum R2 for open position
        self.stopLoss = 10000            # 止损
        self.close_spread = -10          # 平仓价差
        self.volume_active = 1           # 主动腿手数
        self.volume_passive = 1          # 被动腿手数
        
        #------------------------------------------------------------
        self.strategy = strategy
        self.state_id = sid
        self.nested_state = NestedState(strategy)
        self.nested_state.volume_active = self.volume_active
        self.nested_state.volume_passive = self.volume_passive
        self.nested_state.FSM = sid
        self.nested_state.rand_id = -1
        self.nested_state.close_spread = self.close_spread
        self.nested_state.stopLoss = self.stopLoss
        # 0
        self.__class__ = NotInitedState

    def new_state(self, newstate):
        self.__class__ = newstate
        self.onEnterState()

    def onEnterState(self):
        raise NotImplementedError
    
    def inState(self):
        raise NotImplementedError

#---------------------------------------------------------------------
#  0. 初始化状态
class NotInitedState(State):
    """打开程序后，从数据库载入历史数据，做初次分析的状态，完成后载入状态文件，切换到保存的状态"""
    def onEnterState(self):
        print 'FSM%d : Enter State 0' %self.state_id

    def inState(self):
        data = self.strategy.data
        if self.strategy.dis == self.state_id:
            print 'FSM%d S0' %self.state_id
        if data['MyTask_inited']:
            # 0 ---> 1
            self.new_state(NotTradableState)
   

#----------------------------------------------------------------------
#  1.不可交易状态
class NotTradableState(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 1' %self.state_id
        # 进入状态 1 即从文件读取保存的状态， 当开市条件满足就切换到保存的状态
        load_state(self.strategy.stateFileName, self.strategy.FSMs, self.strategy.trading_token)
        self.strategy.data['lastTick_active'] = self.strategy.data['lastTick_passive'] = None

    def inState(self):
        data = self.strategy.data
        if self.strategy.dis == self.state_id:
            print 'FSM%d S1' %self.state_id
        if data['lastTick_active'] != None and data['lastTick_passive'] != None and ismarketopen():
            if self.last_state_class == None:
                # 1 ---> 2
                self.new_state(TradableWaitState) 
            else:
                self.new_state(self.last_state_class)


# 2. 等待开仓
class TradableWaitState(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 2' %self.state_id
        save_state(self.strategy.FSMs, self.strategy.trading_token)

    def inState(self):
        if not ismarketopen():
            # 2 ---> 1
            self.new_state(NotTradableState)
            return

        if not self.alive:
            # 2 ---> 16
            self.new_state(EndState)
            return

        # 是否持有Token
        if self.strategy.trading_token.isHeldBy() and self.strategy.trading_token.isHeldBy()[0] != self.state_id:
            if self.strategy.dis == self.state_id:
                print "State 2: waiting for trading token..."
            return

        data = self.strategy.data
        # 重置策略变量
        self.tradePrice_act = 0 
        self.tradePrice_pas = 0

        try:
            price_active = data['lastTick_active'].lastPrice
            price_passive = data['lastTick_passive'].lastPrice

            MyTask_result_data = data['MyTask_result_data']

            ols_beta = MyTask_result_data['ols_beta']
            # 价差标准差， 最低取值std_floor, 默认5
            spread_std = max(self.std_floor, MyTask_result_data['spread_std'])
            #spread_std = self.std_floor
            # 计算价差
            spread = calc_spread_from_model(price_active, price_passive, ols_beta)
            if self.strategy.dis == self.state_id:
                print "FSM%d S2: sprd = %.2f, std = %.1f, ap = %d / %d" \
                % (self.state_id, spread, spread_std, price_active, price_passive)

            # 检查盘口情况
            maxPrice = max(data['lastTick_active'].askPrice1, data['lastTick_active'].bidPrice1, data['lastTick_active'].lastPrice)
            minPrice = min(data['lastTick_active'].askPrice1, data['lastTick_active'].bidPrice1, data['lastTick_active'].lastPrice)
            bid_ask_spread_active = ((maxPrice - minPrice)/self.strategy.priceTick_active)
            bid_ask_spread_passive = ((data['lastTick_passive'].askPrice1 - data['lastTick_passive'].bidPrice1)/self.strategy.priceTick_passive)
            if bid_ask_spread_active > 1.1 or bid_ask_spread_passive > 1.1:
                print u'盘口检查失败'
                return

            if spread >= spread_std * self.std_mult and MyTask_result_data['ols_R2'] > self.R2_floor:
                # 开仓条件满足
                # 2 ---> 3
                # 做空价差
                # 做多被动腿，检查被动腿持仓情况
                longToday, longYd, shortToday, shortYd = self.strategy.ctaEngine.getPosition(self.strategy.vtSymbol_passive)
                if shortYd < self.volume_passive:
                    #需要开今仓
                    if longToday + longYd + shortToday + shortYd + self.volume_passive > self.max_total_pos:
                        print 'position check failed'
                        return
                longToday, longYd, shortToday, shortYd = self.strategy.ctaEngine.getPosition(self.strategy.vtSymbol_active)
                if longYd < self.volume_active:
                    #需要开今仓
                    if longToday + longYd + shortToday + shortYd + self.volume_active > self.max_total_pos:
                        print 'position check failed'
                        return
                self.strategy.trading_token.give(self)
                self.nested_state.new_state(ShortSpreadState)
                self.new_state(OpenActiveState)
                
            elif spread <= -1.0 * spread_std * self.std_mult and MyTask_result_data['ols_R2'] > self.R2_floor: 
                # 2 ---> 3
                # 做多价差
                # 做空被动腿，检查被动腿持仓情况
                longToday, longYd, shortToday, shortYd = self.strategy.ctaEngine.getPosition(self.strategy.vtSymbol_passive)
                if longYd < self.volume_passive:
                    #需要开今仓
                    if longToday + longYd + shortToday + shortYd + self.volume_passive > self.max_total_pos:
                        print 'position check failed'
                        return
                longToday, longYd, shortToday, shortYd = self.strategy.ctaEngine.getPosition(self.strategy.vtSymbol_active)
                if shortYd < self.volume_active:
                    #需要开今仓
                    if longToday + longYd + shortToday + shortYd + self.volume_active > self.max_total_pos:
                        print 'position check failed'
                        return
                self.strategy.trading_token.give(self)
                self.nested_state.new_state(LongSpreadState)
                self.new_state(OpenActiveState)
                
        except AttributeError, e:
            # 2 ---> 16
            print "Exception in State 2", e
        except ValueError, e:
            print "Exception in State 2", e
       

# 3. 主动腿开仓
class OpenActiveState(State):
    global vtOrderID_FSM_map
    def onEnterState(self):
        print 'FSM%d : Enter State 3' %self.state_id
        self.rand_id = randint(0, 10000)
        self.nested_state.rand_id = self.rand_id
        vtOrderID = self.nested_state.open_active()
        if vtOrderID:
            vtOrderID_FSM_map[vtOrderID] = self.state_id
        # 3 ---> 4
        self.new_state(ActiveOpeningState)

    def inState(self):
        pass


# 4.主动腿开仓中
class ActiveOpeningState(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 4' %self.state_id
        save_state(self.strategy.FSMs, self.strategy.trading_token)

    def inState(self):
        if self.strategy.dis == self.state_id:
            print 'FSM%d S4' %self.state_id
        data = self.strategy.data
        if data[u'全部成交'] == True:
            # 4 ---> 5
            self.new_state(OpenPassiveState)
        elif data[u'委托失败'] == True:
            # 4 ---> 16
            for fsm in self.strategy.FSMs:
                fsm.alive = False
            self.new_state(EndState)
            #self.new_state(TradableWaitState)
        elif data[u'已撤销'] == True:
            # 4 ---> 2
            self.strategy.trading_token.release()
            self.new_state(TradableWaitState)

# 5. 被动腿开仓
class OpenPassiveState(State):
    global vtOrderID_FSM_map
    def onEnterState(self):
        print 'FSM%d : Enter State 5' %self.state_id
        vtOrderID = self.nested_state.open_passive()
        if vtOrderID:
            vtOrderID_FSM_map[vtOrderID] = self.state_id
        # 5 ---> 6
        self.new_state(PassiveOpeningState)

    def inState(self):
        pass

# 6.被动腿开仓中
class PassiveOpeningState(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 6' %self.state_id
        save_state(self.strategy.FSMs, self.strategy.trading_token)

    def inState(self):
        data = self.strategy.data
        if self.strategy.dis == self.state_id:
            print 'FSM%d S6' %self.state_id
        if data[u'委托失败'] == True:
            # 6 ---> 16
            self.strategy.trading_token.release()
            for fsm in self.strategy.FSMs:
                fsm.alive = False
            self.new_state(EndState)
        elif data[u'全部成交'] == True:
            # 6 ---> 9
            self.strategy.trading_token.release()
            self.new_state(WaitCloseState)
        


# 9. 等待平仓
class WaitCloseState(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 9' %self.state_id
        save_state(self.strategy.FSMs, self.strategy.trading_token)

    def inState(self):
        if not ismarketopen():
            # 9 ---> 1
            self.new_state(NotTradableState)
            return

        if not self.alive:
            # 9 ---> 16
            self.new_state(EndState)
            return

        data = self.strategy.data
        # 是否持有Token
        if self.strategy.trading_token.isHeldBy() and self.strategy.trading_token.isHeldBy()[0] != self.state_id:
            if self.strategy.dis == self.state_id:
                print "State 9: waiting for trading token..."
            return

        try:
            price_active = data['lastTick_active'].lastPrice
            price_passive = data['lastTick_passive'].lastPrice
            MyTask_result_data = data['MyTask_result_data']
            ols_beta = MyTask_result_data['ols_beta']
        except:
            return
        
        try:
            spread = calc_spread_from_model(price_active, price_passive, ols_beta)
            spread_traded = calc_spread_from_model( self.tradePrice_act, 
                                                    self.tradePrice_pas, 
                                                    ols_beta)
        except ValueError, e:
            self.strategy.writeCtaLog('ValueError in State 9')
            return

        if self.strategy.dis == self.state_id:
            print "FSM%d 9%s: sprd = %.2f / %.2f, ap = %d / %d"  \
            % (self.state_id, self.nested_state.code, spread, spread_traded, price_active, price_passive)

        # 检查盘口情况
        maxPrice = max(data['lastTick_active'].askPrice1, data['lastTick_active'].bidPrice1, data['lastTick_active'].lastPrice)
        minPrice = min(data['lastTick_active'].askPrice1, data['lastTick_active'].bidPrice1, data['lastTick_active'].lastPrice)
        bid_ask_spread_active = ((maxPrice - minPrice)/self.strategy.priceTick_active)
        bid_ask_spread_passive = ((data['lastTick_passive'].askPrice1 - data['lastTick_passive'].bidPrice1)/self.strategy.priceTick_passive)
        if bid_ask_spread_active > 1.1 or bid_ask_spread_passive > 1.1:
            print u'盘口检查失败'
            return

        # 检查被动腿持仓情况
        longToday, longYd, shortToday, shortYd = self.strategy.ctaEngine.getPosition(self.strategy.vtSymbol_passive)
        longToday_a, longYd_a, shortToday_a, shortYd_a = self.strategy.ctaEngine.getPosition(self.strategy.vtSymbol_active)
                
        if self.nested_state.__class__ == ShortSpreadState:
            #平被动腿多，做空
            #需要开今仓
            if longYd < self.volume_passive and \
                longToday + longYd + shortToday + shortYd + self.volume_passive > self.max_total_pos:
                print 'position check failed'
                return
            if shortYd_a < self.volume_active and \
                longToday_a + longYd_a + shortToday_a + shortYd_a + self.volume_active > self.max_total_pos:
                print 'position check failed'
                return
        elif self.nested_state.__class__ == LongSpreadState:
            #平被动腿空，做多
            #需要开今仓
            if shortYd < self.volume_passive and \
                longToday + longYd + shortToday + shortYd + self.volume_passive > self.max_total_pos:
                print 'position check failed'
                return
            if longYd_a < self.volume_active and \
                longToday_a + longYd_a + shortToday_a + shortYd_a + self.volume_active > self.max_total_pos:
                print 'position check failed'
                return
        
        # 平仓条件满足
        if self.nested_state.need_take_profit(spread):
            self.strategy.trading_token.give(self)
            self.new_state(CloseActiveState)

# 10. 主动腿平仓
class CloseActiveState(State):
    global vtOrderID_FSM_map
    def onEnterState(self):
        print 'FSM%d : Enter State 10' %self.state_id
        vtOrderID = self.nested_state.close_active()
        if vtOrderID:
            vtOrderID_FSM_map[vtOrderID] = self.state_id
        # 10 ---> 11
        self.new_state(ActiveClosingState)

    def inState(self):
        pass          

# 11. 主动腿平仓中
class ActiveClosingState(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 11' %self.state_id
        save_state(self.strategy.FSMs, self.strategy.trading_token)

    def inState(self):
        data = self.strategy.data
        if self.strategy.dis == self.state_id:
            print 'FSM%d S11' %self.state_id
        if data[u'委托失败'] == True:
            # 11 ---> 16
            for fsm in self.strategy.FSMs:
                fsm.alive = False
            self.new_state(EndState)

        elif data[u'全部成交'] == True:
            # 11 ---> 12
            self.new_state(ClosePassiveState)
        elif data[u'已撤销'] == True:
            # 11 ---> 9
            self.strategy.trading_token.release()
            self.new_state(WaitCloseState)
       
# 12. 被动腿平仓
class ClosePassiveState(State):
    global vtOrderID_FSM_map
    def onEnterState(self):
        print 'FSM%d : Enter State 12' %self.state_id
        vtOrderID = self.nested_state.close_passive()
        if vtOrderID:
            vtOrderID_FSM_map[vtOrderID] = self.state_id
        # 12 ---> 13
        self.new_state(PassiveClosingState)

    def inState(self):
        pass

# 13. 被动腿平仓中
class PassiveClosingState(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 13' %self.state_id
        save_state(self.strategy.FSMs, self.strategy.trading_token)

    def inState(self):
        data = self.strategy.data
        if self.strategy.dis == self.state_id:
            print 'FSM%d S13' %self.state_id
        if data[u'全部成交'] == True:
            # 13 ---> 2
            self.strategy.trading_token.release()
            if self.alive:
                self.new_state(TradableWaitState)
                self.nested_state.new_state(UnknownState)
            else:
                # 13 ---> 16
                self.new_state(EndState) 
        elif data[u'委托失败'] == True:
            # 13 ---> 16
            self.strategy.trading_token.release()
            for fsm in self.strategy.FSMs:
                fsm.alive = False
            self.new_state(EndState)
            self.nested_state.new_state(UnknownState)

# 16. 失败后的终结状态
class EndState(State):
    def new_state(self, state):
        pass

    def onEnterState(self):
        print 'FSM%d : Enter EndState' %self.state_id
        save_state(self.strategy.FSMs, self.strategy.trading_token)
        
    def inState(self):
        if self.strategy.dis == self.state_id:
            print 'FSM%d EndState' %self.state_id



########################################################################
class MyTask(CtaTask):
    """载入Tick数据，重采样后统计分析"""
    # 是否已经第一次执行，第一次执行后inited=True
    inited = False
    # 保存分钟线
    df_1min_dict = {}
    # Pandas DataFrame, 用于数据对齐
    data = None

    def taskJob(self):
        t0 = dt.datetime.now()

        list_vtSymbols = self.strategy.vtSymbols

        # 返回的字典实例化
        task_result = CtaTaskResult()
        task_result.data['Exception'] = False
        task_result.task_name = 'MyTask'
        
        try:
            for vtSymbol in list_vtSymbols:
                # 更新时间
                cal = Calendar()
                now_time = dt.datetime.now()
                start_time = cal.addbusdays(now_time, -1 * self.strategy.train_days)
                today_date = todayDate()
                # 开区间的处理，当前日期减去最小的timedelta分辨率
                end_time = today_date - dt.timedelta.resolution

                #where语句，用于剔除错误Tick
                where = """function(){
                    var t1 = Math.abs(this.datetime - this.localtime) > 60 * 1000;
                    var hour = this.datetime.getHours() - 8;
                    if(hour < 0) {
                        hour += 24;
                    }
                    var min = this.datetime.getMinutes();
                    var t2 = (hour < 9) ||
                        (hour == 10 && min >= 15 && min < 30) ||
                        (hour == 11 && min >= 30) ||
                        (hour == 12) ||
                        (hour == 13 && min < 30) ||
                        (hour >= 15 && hour < 21) ||
                        (hour >= 23);
                    return !(t1 || t2);
                }
                """
                if not self.inited:
                    # 首次执行， 从数据库载入5天的原始数据
                    df = self.ctaEngine.loadTickToDataFrame(TICK_DB_NAME, vtSymbol, start_time, now_time, where)
                else:
                    # 再次执行， 从数据库载入当天的原始数据
                    df = self.ctaEngine.loadTickToDataFrame(TICK_DB_NAME, vtSymbol, today_date, now_time, where)
                
                if not df.empty:
                    df = df[['datetime', 'lastPrice']]
                    # 设为时间序列
                    df = df.set_index('datetime')
                    #df.to_csv(vtSymbol+'.raw.csv')                    

                    # 重采样
                    df_1min = df.resample('500ms').ohlc()[('lastPrice','close')]
                    # 释放df占用的内存
                    df = None
                    if self.df_1min_dict.has_key(vtSymbol):
                        # 再次执行
                        try:
                            df_1min_yd = self.df_1min_dict[vtSymbol].ix[start_time : end_time]
                        except:
                            print vtSymbol, 'Exception in df.ix'
                            #self.df_1min_dict[vtSymbol].to_csv(vtSymbol+'.exception.csv')
                            continue
                        self.df_1min_dict[vtSymbol] = pd.concat([df_1min_yd, df_1min], axis=0)
                    else:
                        # 首次执行
                        self.df_1min_dict[vtSymbol] = df_1min
                else:
                    print vtSymbol, ': 0 recs for today.'
            
            # active: hc1801
            df_active = self.df_1min_dict[list_vtSymbols[0]]
            # passive: rb1801
            df_passive = self.df_1min_dict[list_vtSymbols[1]] 
            # 两个时间序列存入同一个pandas DataFrame, 数据会按照时间自动对齐
            self.data = pd.concat([df_active, df_passive], axis=1, join_axes=[df_active.index])
            # 丢弃缺失值
            self.data = self.data.dropna()
            # taking needed data to generate the ols relation
            self.data = self.data[-1 * self.strategy.train_cnt:]
            self.data.to_csv('data.csv')
            # Cointegration
            #-----------------------------------------------------------------------
            # coint_t, pvalue, crit_value = sm.tsa.coint(data.ix[:,0],data.ix[:,1])

            # print '*'*50  
            # print coint_t, pvalue, crit_value
            # print '*'*50  

            # Linear Regression
            #-----------------------------------------------------------------------
            x = self.data.ix[:,1] #passive: rb1801
            y = self.data.ix[:,0] #active: hc1801
            #ols = pd.ols(y=y, x=x)
            #print ols
            X = smapi.add_constant(x)
            ols_ = smapi.OLS(y,X).fit()
            prstd, iv_l, iv_u = wls_prediction_std(ols_)
            is_not_outlier = []
            for i in range(len(y)):
                is_not_outlier.append(y[i] <= iv_u[i] and y[i] >= iv_l[i])
            
            new_x = x[is_not_outlier]
            new_y = y[is_not_outlier]
            new_X = smapi.add_constant(new_x)
            ols = smapi.OLS(new_y, new_X).fit()
            task_result.data['ols_beta'] = {'x':ols.params[1], 'intercept':ols.params[0]}
            task_result.data['ols_R2'] = ols.rsquared
            print ols.summary()
            print 'outliers/tot count:', len(x) - sum(is_not_outlier), '/', len(x)
            #task_result.data['ols_beta'] = ols.beta
            #task_result.data['ols_R2'] = ols.r2
            # spread standard deviation
            task_result.data['spread_std'] = (x-y).std()

        except Exception, e:
            print 'exception:', e
            task_result.data['Exception'] = True
            self.inited = False
            self.df_1min_dict = {}
            self.data = None
            print u"异常， 重设 Task"
        else:
            self.inited = True

        task_result.data['inited'] = self.inited
        print u"Task 耗时: %s" % str(dt.datetime.now()-t0)
        return task_result


#----------------------------------------------------------------------------
class TradingToken:
    def __init__(self):
        self.held_by_list = []

    def give(self, state):
        if not self.held_by_list:
            self.held_by_list.append(state.state_id)
        elif self.held_by_list[0] != state.state_id:
            print 'Token already held by FSM%d' %self.held_by_list[0]

    def release(self):
        if self.held_by_list:
            self.held_by_list = []

    def isHeldBy(self):
        return self.held_by_list
 

########################################################################
class SA_hcrbStrategy(CtaTemplate2):
    
    className = 'SA_hcrbStrategy'
    author = u''

    #------------------------------------------------------------------------
    # 策略参数
    fok = True
    train_cnt = 8000            # Take needed data to generate the relation. When using 1-min bar, then 1day = 345min 
    train_days = 1              # Take more data, then delete the redundancy 
    #------------------------------------------------------------------------
    # 策略变量
    lastTick_active = None      # 主动腿最新Tick价格
    lastTick_passive = None     # 被动腿最新Tick价格
    vtSymbol_active = ''
    vtSymbol_passive = ''
    priceTick_active = 0
    priceTick_passive = 0
    dis = 0                     # 控制台输出的FSM id号
    
    stateFilePrefix = './temp/state'
    stateFileName = ''


    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(SA_hcrbStrategy, self).__init__(ctaEngine, setting)
        self.FSMs = []
        self.myTask = None
        self.stateFileName = '.'.join([self.stateFilePrefix, self.name])
        self.data = {}
        self.data[u'全部成交'] = False 
        self.data[u'委托失败'] = False
        self.data[u'已撤销'] = False

        self.data['lastTick_active'] = None
        self.data['lastTick_passive'] = None

        self.data['MyTask_inited'] = False
        self.data['MyTask_result_data'] = {}
        self.trading_token = TradingToken()


        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）        


    #----------------------------------------------------------------------
    def reset_data(self):
        self.data[u'全部成交'] = False 
        self.data[u'委托失败'] = False
        self.data[u'已撤销'] = False
    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' %self.name)

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        global FSM_CNT

        # 导入状态机参数文件
        fsm_settings = collections.OrderedDict()
        try:
            with open('./temp/settings.%s'%self.name, 'r') as f:
                fsm_settings = json.load(f)
        except Exception as e:
            print str(e)

        # 状态机实例
        for i in range(0, FSM_CNT):
            fsm = State(self, i)
            if fsm_settings:
                setting = fsm_settings.get('%d'%i, {})
                for key in setting:
                    fsm.__dict__[key] = setting[key]
                    fsm.nested_state.__dict__[key] = setting[key]
            self.FSMs.append(fsm)

        # 导出状态机参数文件
        fsm_settings = collections.OrderedDict()
        try:
            with open('./temp/settings.%s'%self.name, 'w') as f:
                for i in range(FSM_CNT):
                    fsm = self.FSMs[i]
                    for key in fsm.__dict__:
                        if '%d'%i not in fsm_settings:
                            fsm_settings['%d'%i] = {}
                        fsm_dict_val = fsm.__dict__[key]
                        #print str(type(fsm_dict_val))
                        if str(type(fsm_dict_val)) in ['<type \'int\'>', '<type \'float\'>', '<type \'string\'>']:
                            fsm_settings['%d'%i][key] = fsm_dict_val
                json.dump(fsm_settings, f, indent=4)
        except Exception as e:
            print str(e)

        # 添加 MyTask， 600秒执行一次
        self.myTask = MyTask(self, 60)
        self.myTask.start()
        self.vtSymbol_active = self.vtSymbols[0]
        self.vtSymbol_passive = self.vtSymbols[1]

        self.priceTick_active = self.getPriceTick(self.vtSymbol_active)
        self.priceTick_passive = self.getPriceTick(self.vtSymbol_passive)


        self.writeCtaLog(u'%s策略启动' %self.name)

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略停止' %self.name)
        try:
            if self.myTask:
                self.myTask.stop()
        except Exception as e:
            print e

    #----------------------------------------------------------------------
    def isTickValid(self, tick):
        """判断Tick是否有效"""
        def getTickTime(tick):
            """从Tick中取出Tick时间， 方便函数"""
            if tick is None:
                return dt.datetime(1970,1,1)
            tick_datetime_str = ' '.join([tick.date, tick.time])
            tick_datetime = None
        
            try:
                tick_datetime = dt.datetime.strptime(tick_datetime_str, '%Y%m%d %H:%M:%S.%f')
            except ValueError:
                try:
                    tick_datetime = dt.datetime.strptime(tick_datetime_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    tick_datetime = dt.datetime.strptime(tick.time, '%Y-%m-%dT%H:%M:%S.%f')

            return tick_datetime        

        # tick 清洗
        tick_datetime = getTickTime(tick)        
        isTickValid = False
        # 比较当前 tick和 lastTick
        if tick.vtSymbol == self.vtSymbols[0]:
            if self.lastTick_active != None:
                time_delta = abs(tick_datetime - dt.datetime.now())
                if (0 <= time_delta.total_seconds() <= 120) and (tick.volume >= self.lastTick_active.volume) and tick.lastPrice > 0:
                    isTickValid = True
                    
        else:
            if self.lastTick_passive != None:
                time_delta = abs(dt.datetime.now() - tick_datetime)
                if (0 <= time_delta.total_seconds() <= 120) and (tick.volume >= self.lastTick_passive.volume) and tick.lastPrice > 0:
                    isTickValid = True

        # 保存 lastTick
        if tick.vtSymbol == self.vtSymbols[0]:
            self.lastTick_active = copy.copy(tick)
        else:
            self.lastTick_passive = copy.copy(tick)

        return isTickValid

    #-----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        if tick.vtSymbol == self.vtSymbol_active:
            print tick.vtSymbol[0:6]
        else:
            print tick.vtSymbol[0:6], 
        if self.dis >= FSM_CNT:
            print 'FSM%d not existed' %self.dis
            self.dis = FSM_CNT - 1
        if self.isTickValid(tick) == False:
            print u'滤除无效Tick: %s %s %s %d' % (tick.vtSymbol, tick.date, tick.time, tick.volume)
            return
        # 记录最新行情
        if tick.vtSymbol == self.vtSymbols[0]:
            self.data['lastTick_active'] = copy.copy(tick)
        elif tick.vtSymbol == self.vtSymbols[1]:
            self.data['lastTick_passive'] = copy.copy(tick)
        else:
            pass
        # 更新状态机
        if tick.vtSymbol == self.vtSymbol_passive:
            for fsm in self.FSMs:
                if self.trading_token.isHeldBy() and self.trading_token.isHeldBy()[0] != fsm.state_id:
                    print 'onTick:  skip FSM%d' %fsm.state_id
                    continue
                fsm.inState()
        


    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        pass
        
    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        print "onOrder(): orderTime = %r ; vtOrderID = %r" % (order.orderTime, order.vtOrderID)

        print order.status
        if order.status == STATUS_ALLTRADED:
            self.data[u'全部成交'] = True
        
        if order.status == STATUS_REJECTED:
            self.data[u'委托失败'] = True

        if order.status == STATUS_CANCELLED:
            self.data[u'已撤销'] = True

        for fsm in self.FSMs:
            if self.trading_token.isHeldBy() and self.trading_token.isHeldBy()[0] != fsm.state_id:
                print 'onOrder:  skip FSM%d' %fsm.state_id
                continue
            fsm.inState()

        # 把 data中的有关成交的信息重设
        self.reset_data()
    #----------------------------------------------------------------------
    def onTrade(self, trade):
        global vtOrderID_FSM_map
        try:
            idx = vtOrderID_FSM_map.get(trade.vtOrderID, -1)

            if idx >= 0 and trade.price > 0:
                if trade.vtSymbol == self.vtSymbol_active:
                    self.FSMs[idx].tradePrice_act = trade.price
                else:
                    self.FSMs[idx].tradePrice_pas = trade.price

            save_state(self.FSMs, self.trading_token)
            with open('vtOrderID_FSM_map.json','w') as f:
                json.dump(vtOrderID_FSM_map, f)
        except Exception as e:
            self.writeCtaLog(str(e))

    #----------------------------------------------------------------------

    def onTask(self, task_result):
        """Task 执行后的回调函数"""
        task_result_data = task_result.data
        if task_result.task_name == 'MyTask':
            # 更新回归模型
            if not task_result_data['Exception']:
                self.data['MyTask_result_data'] = task_result_data
            else:
                print u'统计计算发生异常，不更新回归模型'
            # 第一次运行
            self.data['MyTask_inited'] = task_result_data['inited']


    #------------------------------------------------------------------------
    def onBalance(self, balance):
        pass
