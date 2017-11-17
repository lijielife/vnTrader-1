# encoding: UTF-8

"""
开盘抢单套利
"""
import datetime as dt
from datetime import datetime, time, timedelta
import copy

# cPickle序列化
import cPickle
import json
from ctaBase import *
from ctaTemplate2 import CtaTemplate2
from vtConstant import *
from ctaTask import CtaTask, CtaTaskResult

import pandas as pd
from pandas import Series, DataFrame
#from statsmodels.tsa import stattools
#import statsmodels.api as sm

from business_calendar import Calendar
from vtFunction import todayDate

# 状态机数量，对应最大加仓次数
FSM_CNT = 1

# vtOrderID 与 FSM state_id的map
vtOrderID_FSM_map = {}

# localOrderID ---> vtOrderID
localOrderID_vtOrderID_map = {}

# vtOrderID ---> localOrderID
vtOrderID_localOrderID_map = {v:k for k, v in localOrderID_vtOrderID_map.items()}

# 委托列表，只记录首次进入的， 状态变化不记录
# vtOrderID ---> order
orderDict = {}

#--------------------------------------------------------------------------

def calc_spread_from_model(price_cme, price_shfe, usd_cnh, ols_beta):
    """按照回归模型计算价差，价差 = 国内黄金 - 回归预测(国外黄金的人民币价格)"""
    if price_cme > 0 and price_shfe > 0 and 6 < usd_cnh < 8:
        price_cme_adj = price_cme * usd_cnh / 31.1034768
        try:
            price_shfe_predicted = ols_beta['x'] * price_cme_adj + ols_beta['intercept']
            return price_shfe - price_shfe_predicted
        except Exception as e:
            print str(e)
    else:
        raise ValueError(u'无效的参数')

def calc_active_given_spread(spread, price_cme, usd_cnh, ols_beta):
    if price_cme > 0 and 6 < usd_cnh < 8:
        price_cme_adj = price_cme * usd_cnh / 31.1034768
        try:
            price_shfe_predicted = ols_beta['x'] * price_cme_adj + ols_beta['intercept']
            return price_shfe_predicted + spread
        except Exception as e:
            print str(e)
    else:
        raise ValueError(u'无效的参数')
    

def ismarketopen():
    '''SHFE的au是否开市，CME开市时间覆盖SHFE，边界时间均离开交易所时间3s以保证下单安全'''
    invalid_sections = [(time( 2, 29, 57), time( 9,  0, 1)),
                        (time(10, 14, 57), time(10, 30, 1)),
                        (time(11, 29, 57), time(13, 30, 1)),
                        (time(14, 59, 57), time(21,  0, 1))]
    tmpTime = dt.datetime.now().time()
    for sec in invalid_sections:
        if tmpTime > sec[0] and tmpTime < sec[1]:
            return False
    return True

def is_send_parked_time():
    """预埋单下单时间"""
    invalid_sections = [(time( 8, 59, 40), time( 8, 59, 55)),
                        (time(10, 29, 40), time(10, 29, 55)),
                        (time(13, 29, 40), time(13, 29, 55))]
    tmpTime = dt.datetime.now().time()
    for sec in invalid_sections:
        if tmpTime > sec[0] and tmpTime < sec[1]:
            return True
    return False

def is_call_auction_time():
    """集合竞价下单时间"""
    section = (time( 20, 58, 00), time( 20, 58, 30))
    tmpTime = dt.datetime.now().time()
    if tmpTime > section[0] and tmpTime < section[1]:
        return True
    return False


def save_state(states, token):
    """保存状态到文件"""
    l = []
    dic = {}
    dic['trading_token'] = token
    dic['states'] = l
    for state in states:
        d = {}
        if state.__class__ == EndState:
            state.nested_state.__class__ = UnknownState
        d['state_id'] = state.state_id
        d['state_class'] = state.__class__
        d['nested_state_class'] = state.nested_state.__class__
        d['alive'] = state.alive
        d['tradePrice_cme'] = state.tradePrice_cme
        d['tradePrice_shfe'] = state.tradePrice_shfe
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
                state.tradePrice_cme = d['tradePrice_cme']
                state.tradePrice_shfe = d['tradePrice_shfe']
                i += 1
    except Exception as e:
        for state in states:
            state.last_state_class = None
            state.nested_state.new_state(UnknownState)
        state.strategy.writeCtaLog(u'状态文件不存在或被破坏:'+str(e))

#------------------------------------------------------------------------
# 子状态基类
class NestedState:
    def __init__(self, strategy, main_state):
        self.strategy = strategy
        self.main_state = main_state
        self.code = ''

    def new_state(self, newstate):
        self.__class__ = newstate
        self.onEnterState()

    def onEnterState(self):
        raise NotImplementedError

    def cancel_not_traded(self):
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

    def cancel_not_traded(self):
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

    def cancel_not_traded(self):
        global localOrderID_vtOrderID_map
        cancel_order_id = ''
        if self.main_state.vtOrderID_SS:
            cancel_order_id = self.main_state.vtOrderID_SS
        else:
            cancel_order_id = localOrderID_vtOrderID_map.get(self.main_state.localOrderID_SS, '')
        if cancel_order_id:
            self.strategy.cancelOrder(cancel_order_id)

    def open_passive(self):
        data = self.strategy.data

        direction = CTAORDER_SHORT
        orderPrice = 0.0
        market = True
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_passive,
                                            direction,#CTAORDER_BUY,
                                            orderPrice,
                                            self.strategy.volume_passive,
                                            False, market, False)
        return vtOrderID

    def close_active(self):
        data = self.strategy.data

        direction = CTAORDER_SELL
        orderPrice = data['lastTick_active'].bidPrice1# - self.strategy.priceTick_active

        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                            direction,#CTAORDER_COVER,
                                            orderPrice,
                                            self.strategy.volume_active,
                                            False, not self.strategy.fok, self.strategy.fok)

        return vtOrderID

    def close_passive(self):
        data = self.strategy.data

        direction = CTAORDER_COVER
        orderPrice = 0.0
        market = True
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_passive,
                                            direction,#CTAORDER_SELL,
                                            orderPrice,
                                            self.strategy.volume_passive,
                                            False, market, False)
        return vtOrderID

    def need_take_profit(self, spread):
        return spread >= -1.0 * self.strategy.close_spread

    def need_stop_loss(self, spread, spread_traded):
        return spread <= spread_traded - self.strategy.stopLoss

#-------------------------------------------------------------------------
class ShortSpreadState(NestedState):
    def onEnterState(self):
        print 'Enter Short Spread'
        self.code = 'a'

    def cancel_not_traded(self):
        global localOrderID_vtOrderID_map
        cancel_order_id = ''
        if self.main_state.vtOrderID_LS:
            cancel_order_id = self.main_state.vtOrderID_LS
        else:
            cancel_order_id = localOrderID_vtOrderID_map.get(self.main_state.localOrderID_LS, '')
        if cancel_order_id:
            self.strategy.cancelOrder(cancel_order_id)

    def open_passive(self):
        data = self.strategy.data

        direction = CTAORDER_BUY
        orderPrice = 0.0
        market = True

        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_passive,
                                            direction,#CTAORDER_SHORT,
                                            orderPrice,
                                            self.strategy.volume_passive,
                                            False, market, False)
        return vtOrderID

    def close_active(self):
        data = self.strategy.data

        direction = CTAORDER_COVER
        orderPrice = data['lastTick_active'].askPrice1# + self.strategy.priceTick_active

        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                            direction,#CTAORDER_SELL,
                                            orderPrice,
                                            self.strategy.volume_active,
                                            False, not self.strategy.fok, self.strategy.fok)
        return vtOrderID

    def close_passive(self):
        data = self.strategy.data
        direction = CTAORDER_SELL
        orderPrice = 0.0
        market = True
        vtOrderID = self.strategy.sendOrder(self.strategy.vtSymbol_passive,
                                            direction,#CTAORDER_COVER,
                                            orderPrice,
                                            self.strategy.volume_passive,
                                            False, market, False)
        return vtOrderID
    
    def need_take_profit(self, spread):
        return spread <= self.strategy.close_spread

    def need_stop_loss(self, spread, spread_traded):
        return spread >= spread_traded + self.strategy.stopLoss

# 以下为主状态
#-------------------------------------------------------------------------
# 主状态基类
class State:
    strategy = None
    last_state_class = None
    state_id = 0
    alive = True
    tradePrice_cme = 0
    tradePrice_shfe = 0
    target_price_LS = 0 
    target_price_SS = 0
    # 预埋单的本地标识
    localOrderID_LS = ''
    localOrderID_SS = ''
    # 预埋单触发后的vtOrderID
    vtOrderID_LS = ''
    vtOrderID_SS = ''

    def __init__(self, strategy, sid):
        self.strategy = strategy
        self.state_id = sid
        self.nested_state = NestedState(strategy, self)
        # 0
        self.__class__ = State_0

    def new_state(self, newstate):
        self.__class__ = newstate
        self.onEnterState()

    def onEnterState(self):
        raise NotImplementedError
    
    def inState(self):
        raise NotImplementedError

#---------------------------------------------------------------------
#  0. 初始化状态
class State_0(State):
    """打开程序后，从数据库载入历史数据，做初次分析的状态，完成后载入状态文件，切换到保存的状态"""
    def onEnterState(self):
        print 'FSM%d : Enter State 0' %self.state_id

    def inState(self):
        data = self.strategy.data
        if self.strategy.dis == self.state_id:
            print 'FSM%d S0' %self.state_id
        if data['MyTask_inited']:
            # 0 ---> 1
            self.new_state(State_1)
   

#----------------------------------------------------------------------
#  1.载入状态文件
class State_1(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 1' %self.state_id
        # 进入状态 1 即从文件读取保存的状态， 当开市条件满足就切换到保存的状态
        load_state(self.strategy.stateFileName, self.strategy.FSMs, self.strategy.trading_token)
        self.strategy.data['lastTick_active'] = self.strategy.data['lastTick_passive'] = None

    def inState(self):
        data = self.strategy.data
        if self.strategy.dis == self.state_id:
            print 'FSM%d S1' %self.state_id
        if self.last_state_class == None:
            # 1 ---> 2
            self.new_state(State_2) 
        elif data['lastTick_active'] != None and data['lastTick_passive'] != None and ismarketopen():
            # 1 ---> x
            self.new_state(self.last_state_class)

# 2. 等待开仓状态（时间满足）
class State_2(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 2' %self.state_id
    def inState(self):
        print 'FSM%d S2 target l/s = %.2f %.2f, pe = %.1f / %.4f ' \
        %(self.state_id, self.target_price_LS, self.target_price_SS, self.strategy.lastTick_passive.lastPrice, self.strategy.usd_cnh)
        data = self.strategy.data
        MyTask_result_data = data['MyTask_result_data']
        ols_beta = MyTask_result_data['ols_beta']
        try:
            # 做多价差的目标价格
            self.target_price_LS = calc_active_given_spread(-1.0 * self.strategy.target_spread, 
                                                            self.strategy.lastTick_passive.lastPrice, 
                                                            self.strategy.usd_cnh, 
                                                            ols_beta)
            # 做空价差的目标价格
            self.target_price_SS = calc_active_given_spread(self.strategy.target_spread,
                                                            self.strategy.lastTick_passive.lastPrice,
                                                            self.strategy.usd_cnh,
                                                            ols_beta)
        except Exception as e:
            return
        # 检查指定时间点，如果满足时间条件，则主动腿开仓（预埋或集合竞价）
        if is_send_parked_time():
            # 2 ---> 3p
            self.new_state(State_3p)
            return
        if is_call_auction_time():
            # 2 ---> 3ca
            self.new_state(State_3ca)
            return
        

# 3p. 主动腿开仓（双向预埋）
class State_3p(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 3 parked' %self.state_id
        # 3p ---> 4
        self.localOrderID_SS = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                CTAORDER_SHORT,
                                self.target_price_SS,
                                self.strategy.volume_active,
                                False, False, False, True)
        self.localOrderID_LS = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                CTAORDER_BUY,
                                self.target_price_LS,
                                self.strategy.volume_active,
                                False, False, False, True)
        self.vtOrderID_SS = self.vtOrderID_LS = ''
        self.new_state(State_4p)
    def inState(self):
        pass


# 3ca. 主动腿开仓（集合竞价）
class State_3ca(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 3 Call Auction' %self.state_id
        # 3ca ---> 4ca
        self.vtOrderID_SS = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                CTAORDER_SHORT,
                                self.target_price_SS,
                                self.strategy.volume_active,
                                False, False, False, False)
        self.vtOrderID_LS = self.strategy.sendOrder(self.strategy.vtSymbol_active,
                                CTAORDER_BUY,
                                self.target_price_LS,
                                self.strategy.volume_active,
                                False, False, False, False)
        self.localOrderID_LS = self.localOrderID_SS = ''
        self.new_state(State_4ca)
    def inState(self):
        pass

# 4p. 开盘等待成交结果(预埋) (做多或做空价差)
class State_4p(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 4p' %self.state_id
        self.order_LS = self.order_SS = None

    def inState(self):
        global vtOrderID_localOrderID_map, localOrderID_vtOrderID_map, orderDict
        print 'FSM%d S4p' %self.state_id
        if not self.order_LS or not self.order_SS:
            #print 'if not self.order_LS or not self.order_SS'
            # LS
            if self.vtOrderID_LS:
                vtOrderID_LS = self.vtOrderID_LS
            else:
                vtOrderID_LS = localOrderID_vtOrderID_map.get(self.localOrderID_LS)
            # SS
            if self.vtOrderID_SS:
                vtOrderID_SS = self.vtOrderID_SS
            else:
                vtOrderID_SS = localOrderID_vtOrderID_map.get(self.localOrderID_SS)

            #print vtOrderID_LS, vtOrderID_SS

            self.order_LS = orderDict.get(vtOrderID_LS)
            self.order_SS = orderDict.get(vtOrderID_SS)
            
        else:
            if self.strategy.data[u'全部成交']:
                vtOrderID = self.strategy.onOrder_order.vtOrderID
                #localOrderID = vtOrderID_localOrderID_map.get(vtOrderID)
                
                #if localOrderID == self.localOrderID_LS:
                if vtOrderID == self.vtOrderID_LS:
                    # 撤另一边未成交的
                    # 4 ---> 4b
                    self.new_state(State_4b)
                    self.nested_state.new_state(LongSpreadState)
                    return
                #if localOrderID == self.localOrderID_SS:
                if vtOrderID == self.vtOrderID_SS:
                    # 撤另一边未成交的
                    # 4 ---> 4b
                    self.new_state(State_4b)
                    self.nested_state.new_state(ShortSpreadState)
                    return
            if  datetime.now() - self.order_LS.localtime >= timedelta(seconds=10) and \
                datetime.now() - self.order_SS.localtime >= timedelta(seconds=10):
                # 超时10sec
                print 'timeout', self.order_LS.localtime, self.order_SS.localtime
                self.new_state(State_4c)

# 4ca. 开盘等待成交结果(集合竞价) (做多或做空价差)
class State_4ca(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 4ca' %self.state_id
        self.order_LS = self.order_SS = None

    def inState(self):
        global vtOrderID_localOrderID_map, localOrderID_vtOrderID_map, orderDict
        print 'FSM%d S4ca' %self.state_id
        if not self.order_LS or not self.order_SS:
            # LS
            if self.vtOrderID_LS:
                vtOrderID_LS = self.vtOrderID_LS
            
            # SS
            if self.vtOrderID_SS:
                vtOrderID_SS = self.vtOrderID_SS

            self.order_LS = orderDict.get(vtOrderID_LS)
            self.order_SS = orderDict.get(vtOrderID_SS)
            
        else:
            if self.strategy.data[u'全部成交']:
                vtOrderID = self.strategy.onOrder_order.vtOrderID
                #localOrderID = vtOrderID_localOrderID_map.get(vtOrderID)
                
                #if localOrderID == self.localOrderID_LS:
                if vtOrderID == self.vtOrderID_LS:
                    # 撤另一边未成交的
                    # 4 ---> 4b
                    self.new_state(State_4b)
                    self.nested_state.new_state(LongSpreadState)
                    return
                #if localOrderID == self.localOrderID_SS:
                if vtOrderID == self.vtOrderID_SS:
                    # 撤另一边未成交的
                    # 4 ---> 4b
                    self.new_state(State_4b)
                    self.nested_state.new_state(ShortSpreadState)
                    return
            if  datetime.now().time() > time(21, 00, 10):
                # 超时10sec
                print 'timeout'
                self.new_state(State_4c)

# 4b. 单向撤单
class State_4b(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 4b' %self.state_id
        # 撤单操作
        self.nested_state.cancel_not_traded()
        # 4b ---> 4bd
        self.new_state(State_4bd)
    def inState(self):
        pass

# 4bd. 单向撤单完成
class State_4bd(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 4bd' %self.state_id
    def inState(self):
        if self.strategy.data[u'已撤单']:
            # 4bd ---> 5
            self.new_state(State_5)

# 4c. 双向撤单
class State_4c(State):
    def onEnterState(self):
        global localOrderID_vtOrderID_map
        print 'FSM%d : Enter State 4c' %self.state_id
        # 撤两边
        cancel_order_ids = []
        # LS
        if self.vtOrderID_LS:
            cancel_order_id = self.vtOrderID_LS
        else:
            cancel_order_id = localOrderID_vtOrderID_map.get(self.localOrderID_LS, '')
        cancel_order_ids.append(cancel_order_id)

        # SS
        if self.vtOrderID_SS:
            cancel_order_id = self.vtOrderID_SS
        else:
            cancel_order_id = localOrderID_vtOrderID_map.get(self.localOrderID_SS, '')
        cancel_order_ids.append(cancel_order_id)

        for cancel_order_id in cancel_order_ids:
            if cancel_order_id:
                self.strategy.cancelOrder(cancel_order_id)

        # 4c ---> 4cd
        self.new_state(State_4cd)
    def inState(self):
        pass

# 4cd. 双向撤单完成
class State_4cd(State):
    def onEnterState(self):
        print 'FSM%d : Enter State 4cd' %self.state_id
        self.long_all_cancelled = False
        self.short_all_cancelled = False

    def inState(self):
        if self.strategy.data[u'已撤销']:
            vtOrderID = self.strategy.onOrder_order.vtOrderID
            if vtOrderID == self.order_LS.vtOrderID:
                self.long_all_cancelled = True
            if vtOrderID == self.order_SS.vtOrderID:
                self.short_all_cancelled = True

        if self.long_all_cancelled and self.short_all_cancelled:
            self.new_state(State_2)
            return

# 5. 被动腿开仓
class State_5(State):
    global vtOrderID_FSM_map
    def onEnterState(self):
        print 'FSM%d : Enter State 5' %self.state_id
        vtOrderID = self.nested_state.open_passive()
        if vtOrderID:
            vtOrderID_FSM_map[vtOrderID] = self.state_id
        # 5 ---> 6
        self.new_state(State_6)

    def inState(self):
        pass

# 6.被动腿开仓中
class State_6(State):
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
            self.new_state(State_9)
        


# 9. 等待平仓
class State_9(State):
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
            price_cme = price_active = data['lastTick_active'].lastPrice
            price_shfe = price_passive = data['lastTick_passive'].lastPrice
            if data['lastTick_active'].exchange != 'CME':
                price_cme, price_shfe = price_shfe, price_cme
            MyTask_result_data = data['MyTask_result_data']
            ols_beta = MyTask_result_data['ols_beta']
        except:
            return
        
        try:
            spread = calc_spread_from_model(price_cme, price_shfe, self.strategy.usd_cnh, ols_beta)
            spread_traded = calc_spread_from_model( self.tradePrice_cme, 
                                                    self.tradePrice_shfe, 
                                                    self.strategy.usd_cnh, ols_beta)
        except ValueError, e:
            self.strategy.writeCtaLog('ValueError in State 9')
            return

        if self.strategy.dis == self.state_id:
            print "FSM%d 9%s: sprd n/t = %.3f / %.3f, ape = %.1f / %.2f / %.4f"  \
            % (self.state_id, self.nested_state.code, spread, spread_traded, price_active, price_passive, self.strategy.usd_cnh)

        # 检查盘口情况
        bid_ask_spread_active = int((data['lastTick_active'].askPrice1 - data['lastTick_active'].bidPrice1)/self.strategy.priceTick_active)
        bid_ask_spread_passive = int((data['lastTick_passive'].askPrice1 - data['lastTick_passive'].bidPrice1)/self.strategy.priceTick_passive)
        if bid_ask_spread_active > 1 or bid_ask_spread_passive > 1:
            return

        # 平仓条件满足
        if self.nested_state.need_take_profit(spread):
            self.strategy.trading_token.give(self)
            self.new_state(State_10)            
        elif self.nested_state.need_stop_loss(spread, spread_traded):
            # 9 ---> 10
            self.alive = False
            self.strategy.trading_token.give(self)
            self.new_state(State_10)

# 10. 主动腿平仓
class State_10(State):
    global vtOrderID_FSM_map
    def onEnterState(self):
        print 'FSM%d : Enter State 10' %self.state_id
        vtOrderID = self.nested_state.close_active()
        if vtOrderID:
            vtOrderID_FSM_map[vtOrderID] = self.state_id
        # 10 ---> 11
        self.new_state(State_11)

    def inState(self):
        pass          

# 11. 主动腿平仓中
class State_11(State):
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
            self.new_state(State_12)
        elif data[u'已撤销'] == True:
            # 11 ---> 9
            self.new_state(State_9)
       
# 12. 被动腿平仓
class State_12(State):
    global vtOrderID_FSM_map
    def onEnterState(self):
        print 'FSM%d : Enter State 12' %self.state_id
        vtOrderID = self.nested_state.close_passive()
        if vtOrderID:
            vtOrderID_FSM_map[vtOrderID] = self.state_id
        # 12 ---> 13
        self.new_state(State_13)

    def inState(self):
        pass

# 13. 被动腿平仓中
class State_13(State):
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

        list_vtSymbols = ['', '', '']
        for vtSymbol in self.strategy.vtSymbols:
            if 'CME' in vtSymbol:
                list_vtSymbols[1] = vtSymbol
            elif 'OANDA' in vtSymbol:
                list_vtSymbols[2] = vtSymbol
            else:
                list_vtSymbols[0] = vtSymbol

        # 返回的字典实例化
        task_result = CtaTaskResult()
        task_result.data['Exception'] = False
        task_result.task_name = 'MyTask'
        
        try:
            for vtSymbol in list_vtSymbols:
                # 更新时间
                cal = Calendar()
                now_time = dt.datetime.now()
                start_time = cal.addbusdays(now_time, -5)
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
                    var t2 = (hour == 2 && min >= 30) ||
                        (hour >= 3 && hour < 9) ||
                        (hour == 10 && min >= 15 && min < 30) ||
                        (hour == 11 && min >= 30) ||
                        (hour == 12) ||
                        (hour == 13 && min < 30) ||
                        (hour >= 15 && hour < 21);
                    return !(t1 || t2);
                }
                """
                # OA 时区转换
                if 'OANDA' in vtSymbol:
                    start_time = start_time - dt.timedelta(hours=8)
                    now_time = now_time - dt.timedelta(hours=8)
                    today_date = today_date - dt.timedelta(hours=8)
                    where = ''
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
                    # OANDA 时区处理
                    if "OANDA" in vtSymbol:
                        df= df.shift(8, freq='H')

                    # 重采样
                    df_1min = df.resample('1min').ohlc()[('lastPrice','close')]
                    # 释放df占用的内存
                    df = None
                    if "OANDA" in vtSymbol:
                        # 汇率数据更新不频繁，会有分钟线缺失的情况，采用前向插值补齐缺失数据
                        df_1min = df_1min.fillna(method='ffill')

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
            
            # au1712
            df_domestic = self.df_1min_dict[list_vtSymbols[0]]
            # GC1708.CME
            df_foreign = self.df_1min_dict[list_vtSymbols[1]] * self.df_1min_dict[list_vtSymbols[2]] / 31.1034768
            # 两个时间序列存入同一个pandas DataFrame, 数据会按照时间自动对齐
            self.data = pd.concat([df_domestic, df_foreign], axis=1, join_axes=[df_domestic.index])
            # 丢弃缺失值
            self.data = self.data.dropna()
            self.data.to_csv('data.csv')
            # Cointegration
            #-----------------------------------------------------------------------
            # coint_t, pvalue, crit_value = sm.tsa.coint(data.ix[:,0],data.ix[:,1])

            # print '*'*50  
            # print coint_t, pvalue, crit_value
            # print '*'*50  

            # Linear Regression
            #-----------------------------------------------------------------------
            x = self.data.ix[:,1]
            y = self.data.ix[:,0]
            ols = pd.ols(y=y, x=x)
            print ols
            task_result.data['ols_beta'] = ols.beta
            task_result.data['ols_R2'] = ols.r2
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
class HuntStrategy(CtaTemplate2):
    
    className = 'HuntStrategy'
    author = u''
    #------------------------------------------------------------------------
    # 状态机
    FSMs = []
    #------------------------------------------------------------------------
    # 策略参数
    
    std_mult = 1                # 标准差乘数
    std_floor = 0.5             # 标准差的最小值
    stopLoss = 10               # 止损
    close_spread = 0.0          # 平仓价差
    volume_active = 3           # 主动腿手数
    volume_passive = 1          # 被动腿手数
    fok = True
    target_spread = 0.1
    #------------------------------------------------------------------------
    # 策略变量
    lastTick_active = None      # 主动腿最新Tick价格
    lastTick_passive = None     # 被动腿最新Tick价格
    vtSymbol_active = ''
    vtSymbol_passive = ''
    priceTick_active = 0
    priceTick_passive = 0
    dis = 0                     # 控制台输出的FSM id号
    trading_token = TradingToken()
    usd_cnh = 0.0

    stateFilePrefix = './temp/state'
    stateFileName = ''
    # 保存传入状态机的各类数据的字典
    data = {}
    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbols',
                 'std_floor',
                 'std_mult',
                 'volume_active',
                 'volume_passive',
                 'stopLoss']

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(HuntStrategy, self).__init__(ctaEngine, setting)
        self.FSMs = []
        self.myTask = None
        self.stateFileName = '.'.join([self.stateFilePrefix, self.name])
        self.data[u'全部成交'] = False 
        self.data[u'委托失败'] = False
        self.data[u'已撤销'] = False


        self.data['lastTick_active'] = None
        self.data['lastTick_passive'] = None

        self.data['MyTask_inited'] = False
        self.data['MyTask_result_data'] = {}
        


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
        # 状态机实例
        for i in range(0, FSM_CNT):
            fsm = State(self, i)
            self.FSMs.append(fsm)

        # 添加 MyTask， 600秒执行一次
        self.myTask = MyTask(self, 600)
        self.myTask.start()
        self.vtSymbol_active = self.vtSymbols[1]
        self.vtSymbol_passive = self.vtSymbols[0]

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

        #汇率Tick
        if 'OANDA' in tick.vtSymbol:
            return True

        # tick 清洗
        tick_datetime = getTickTime(tick)        
        isTickValid = False
        # 比较当前 tick和 lastTick
        if tick.vtSymbol == self.vtSymbols[1]:
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
        if tick.vtSymbol == self.vtSymbols[1]:
            self.lastTick_active = copy.copy(tick)
        else:
            self.lastTick_passive = copy.copy(tick)

        return isTickValid

    #-----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        print tick.vtSymbol[0:6], 
        if self.isTickValid(tick) == False:
            print u'滤除无效Tick: %s %s %s %d' % (tick.vtSymbol, tick.date, tick.time, tick.volume)
            return
        # 记录最新行情
        if tick.vtSymbol == self.vtSymbols[1]:
            self.data['lastTick_active'] = copy.copy(tick)
        elif tick.vtSymbol == self.vtSymbols[0]:
            self.data['lastTick_passive'] = copy.copy(tick)
        else:
            self.usd_cnh = tick.lastPrice
        # 更新状态机
        for fsm in self.FSMs:
            fsm.inState()
        


    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        pass
        
    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        global localOrderID_vtOrderID_map, orderDict
        print 'onOrder!'
        import pprint
        pprint.pprint(order.__dict__)

        if hasattr(order, 'isParkedTriggered'):
            print 'isParkedTriggered'
            localOrderID_vtOrderID_map[order.localOrderID] = order.vtOrderID
        
        if order.vtOrderID not in orderDict:
            orderDict[order.vtOrderID] = order

        self.onOrder_order = order
        if order.status == STATUS_ALLTRADED:
            self.data[u'全部成交'] = True
        
        if order.status == STATUS_REJECTED:
            self.data[u'委托失败'] = True

        if order.status == STATUS_CANCELLED:
            self.data[u'已撤销'] = True

        for fsm in self.FSMs:
            fsm.inState()

        # 把 data中的有关成交的信息重设
        self.reset_data()
        self.onOrder_order = None
    #----------------------------------------------------------------------
    def onTrade(self, trade):
        global vtOrderID_FSM_map
        try:
            idx = vtOrderID_FSM_map.get(trade.vtOrderID, -1)

            if idx >= 0 and trade.price > 0:
                if trade.exchange == 'CME':
                    self.FSMs[idx].tradePrice_cme = trade.price
                else:
                    self.FSMs[idx].tradePrice_shfe = trade.price

            save_state(self.FSMs, self.trading_token)
            with open('vtOrderID_FSM_map.json', 'w') as f:
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
