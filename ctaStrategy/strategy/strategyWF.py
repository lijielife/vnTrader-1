# encoding: UTF-8
"""
WF
"""
from __future__ import division
import numpy as np
import pandas as pd

from ctaBase import *
from ctaTemplate2 import CtaTemplate2
from my_module.particle_filter import ParticleFilter
from my_module.wonham_filter import WonhamFilter
from vtConstant import *

PARTICLE_NUM = 10000

# 主状态基类
class State:
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

    def inState(self):
        if self.strategy.strategy_ready:
            # 0 ---> 1
            self.new_state(State1)

class State1(State):
    """Waiting for trading signal"""
    def onEnterState(self):
        print 'Enter S1'

    def inState(self):
        try:
            wfr_1min = self.strategy.WF_result_1min[-1]['wf_result']
        except:
            wfr_1min = -1;
        try:
            wfr_5min = self.strategy.WF_result_5min[-1]['wf_result']
        except:
            wfr_5min = -1;
        try:
            wfr_60min = self.strategy.WF_result_60min[-1]['wf_result']
        except:
            wfr_60min = -1;
        
        print "S1  1M: %.2f  5M: %.2f  60M: %.2f" %(wfr_1min, wfr_5min, wfr_60min)
        
        # if need open
        # Calculate multiframe
        if self.need_open(wfr_1min, wfr_5min, wfr_60min):
            self.new_state(State2)

    def need_open(self, wfr_1min, wfr_5min, wfr_60min):
        if wfr_1min < 0 or wfr_5min < 0 or wfr_60min < 0:
            return False
        threshold = self.strategy.threshold
        if self.strategy.direction_long:
            return wfr_1min > threshold and wfr_5min > threshold and wfr_60min > threshold
        else:
            neg_threshold = 1 - threshold
            return wfr_1min < neg_threshold and wfr_5min < neg_threshold and wfr_60min < neg_threshold

class State2(State):
    """Open"""
    def onEnterState(self):
        print 'Enter S2'
        # sendorder
        direction = CTAORDER_BUY if self.strategy.direction_long else CTAORDER_SHORT
        self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastPrice, self.strategy.volume, self)#, False, False)
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
            # 3 ---> 4
            self.new_state(State4)

class State4(State):
    """Wait Close"""
    def onEnterState(self):
        print 'Enter S4'

    def inState(self):
        try:
            wfr_1min = self.strategy.WF_result_1min[-1]['wf_result']
        except:
            wfr_1min = -1;
        try:
            wfr_5min = self.strategy.WF_result_5min[-1]['wf_result']
        except:
            wfr_5min = -1;
        try:
            wfr_60min = self.strategy.WF_result_60min[-1]['wf_result']
        except:
            wfr_60min = -1;
        print "S4  1M: %.2f  5M: %.2f  60M: %.2f" %(wfr_1min, wfr_5min, wfr_60min)
        # if need close
        if self.need_close(wfr_1min, wfr_5min, wfr_60min):
            # 4 ---> 5
            self.new_state(State5)
    
    def need_close(self, wfr_1min, wfr_5min, wfr_60min):
        if self.strategy.direction_long:
            return wfr_1min < .5 and wfr_5min < .5 and wfr_60min < .5
        else:
            return wfr_1min > .5 and wfr_5min > .5 and wfr_60min > .5


class State5(State):
    """Close"""
    def onEnterState(self):
        print 'Enter S5'
        # sendorder
        direction = CTAORDER_SELL if self.strategy.direction_long else CTAORDER_COVER
        self.strategy.sendOrder(self.strategy.vtSymbol, direction, self.strategy.lastPrice, self.strategy.volume, self)#, False, False)
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
class WFStrategy(CtaTemplate2):
    
    className = 'WFStrategy'
    author = u''

    #------------------------------------------------------------------------
    # 策略参数
    #f = 6.7 / 31.1034768
    f = 1.0
    motion_noise = 5.0 * f
    sense_noise = 5.0 * f
    X_min = 200.0 * f
    X_max = 300.0 * f
    dX_min = -5.0 * f
    dX_max = 5.0 * f

    mu0 = .0005
    mu1 = -.0005

    lambda0 = .005
    lambda1 = .005
    sig = .001
    dt = 1./(60*24)
    #T = len(df_1min)*dt

    # Slow switching Q
    Q  = np.array([[-lambda0, lambda0],
                   [ lambda1,-lambda1]])

    mu = [mu0, mu1]

    volume = 1
    direction_long = True
    threshold = 0.9
    #------------------------------------------------------------------------
    # 策略变量
    count = 0
    bar = None
    bar_5min = None
    barMinute = EMPTY_STRING

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(WFStrategy, self).__init__(ctaEngine, setting)
        self.lastPrice = 0.0
        self.count = 0
        self.pf = ParticleFilter(PARTICLE_NUM)
        self.pf.PF_Init(self.motion_noise, self.sense_noise, self.X_min, self.X_max, self.dX_min, self.dX_max)
        self.barSeries_1min = []
        self.barSeries_5min = []
        self.barSeries_60min = []

        self.WF_result_1min = []
        self.WF_result_5min = []
        self.WF_result_60min = []
        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）        
        self.all_traded = False
        self.wf1 = WonhamFilter()
        self.wf5 = WonhamFilter()
        self.wf60 =WonhamFilter()
        self.wf1.WF_Init(self.dt, self.Q, self.mu, self.sig)
        self.wf5.WF_Init(self.dt*5, self.Q, self.mu, self.sig)
        self.wf60.WF_Init(self.dt*60, self.Q, self.mu, self.sig)
    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' %self.name)
        self.aggregate_5min = self.create_aggregator(5)
        self.aggregate_60min = self.create_aggregator(60)

        self.fsm = State(self)
        try:
            self.vtSymbol = self.vtSymbols[0]
            self.strategy_ready = False
            ticks = self.loadTick(self.vtSymbols[0], 1)
            for tick in ticks:
                tick.isHistory = True
                self.onTick(tick)
            del ticks
        except Exception as e:
            self.vtSymbol = 'au1706'
            print str(e)
        self.strategy_ready = True
        
        
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
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        # pf output
        self.lastPrice = bar.close;
        self.barSeries_1min.append(bar)
        self.aggregate_5min(bar, self.onBar_5min)
        self.aggregate_60min(bar, self.onBar_60min)
        try:
            dY = np.log(self.barSeries_1min[-1].close) - np.log(self.barSeries_1min[-2].close)
            self.WF_result_1min.append({'datetime':self.barSeries_1min[-1].datetime, 'bar1_close':bar.close, 'wf_result':self.wf1.Calculate(dY)[0]})
        except IndexError as e:
            pass
        self.fsm.inState()
    #----------------------------------------------------------------------
    def onBar_5min(self, bar):
        self.barSeries_5min.append(bar)
        try:
            dY = np.log(self.barSeries_5min[-1].close) - np.log(self.barSeries_5min[-2].close)
            #self.WF_result_5min.append(self.wf5.Calculate(dY))
            self.WF_result_5min.append({'datetime':self.barSeries_5min[-1].datetime, 'wf_result':self.wf5.Calculate(dY)[0]})
        except IndexError as e:
            pass

    #----------------------------------------------------------------------
    def onBar_60min(self, bar):
        self.barSeries_60min.append(bar)
        try:
            dY = np.log(self.barSeries_60min[-1].close) - np.log(self.barSeries_60min[-2].close)
            #self.WF_result_60min.append(self.wf60.Calculate(dY))
            self.WF_result_60min.append({'datetime':self.barSeries_60min[-1].datetime, 'wf_result':self.wf60.Calculate(dY)[0]})
        except IndexError as e:
            pass
        df_1min = pd.DataFrame(self.WF_result_1min)
        df_5min = pd.DataFrame(self.WF_result_5min)
        df_60min = pd.DataFrame(self.WF_result_60min)
        df_1min.to_csv('results/result1.csv')
        df_5min.to_csv('results/result5.csv')
        df_60min.to_csv('results/result60.csv')

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        print "onOrder(): orderTime = %r ; vtOrderID = %r; status = %s" % (order.orderTime, order.vtOrderID, order.status)
        if order.status == STATUS_ALLTRADED:
            self.all_traded = True
        self.fsm.inState()
        self.all_traded = False

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        # print '-'*50
        # print 'onTrade'
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
    engine.setStartDate('20160601')
    
    # 载入历史数据到引擎中
    engine.setDatabase(MINUTE_DB_NAME, 'au1706')
    
    # 设置产品相关参数
    engine.setSlippage(0.05)     # 股指1跳
    engine.setRate(0.3/10000)   # 万0.3
    engine.setSize(1)         # 股指合约大小    
    
    # 在引擎中创建策略对象
    engine.initStrategy(WFStrategy, {})
    
    # 开始跑回测
    engine.runBacktesting()
    
    # 显示回测结果
    # spyder或者ipython notebook中运行时，会弹出盈亏曲线图
    # 直接在cmd中回测则只会打印一些回测数值
    engine.showBacktestingResult()