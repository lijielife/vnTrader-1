# encoding: UTF-8

"""
test
"""
from ctaBase import *
from ctaTemplate2 import CtaTemplate2
from vtConstant import *
import cPickle
#from my_module.particle_filter import ParticleFilter


########################################################################
class TestStrategy(CtaTemplate2):
    
    className = 'TestStrategy'
    author = u''
    #------------------------------------------------------------------------
    # 
    
    #------------------------------------------------------------------------
    # 策略参数

    #------------------------------------------------------------------------
    # 策略变量
    count = 0
    bar = None
    barMinute = EMPTY_STRING

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(TestStrategy, self).__init__(ctaEngine, setting)
        self.fok = False
        self.count = 0
        #self.pf = ParticleFilter(10000)
        #self.pf.PF_Init(5.0, 5.0, 1200.0, 1400.0, -5.0, 5.0)
        
        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）        


    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' %self.name)
        self.vtSymbol = self.vtSymbols[0]
        self.putEvent()

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略启动' %self.name)
        #print self.ctaEngine.getPosition('GC1712.CME')
        # pmEngine = self.ctaEngine.mainEngine.pmEngine
        # import pprint
        # pprint.pprint(pmEngine.qryPosition('au1712'))
         


    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略停止' %self.name)
        self.putEvent()

    
    #-----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        #self.ctaEngine.writeWebLog(content)
        print 'tick'
        #print content
        #print tick.lastPrice,
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


            
    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        # pf output
        #filtered_X, filtered_dX, predicted = self.pf.Calculate(bar.close)
        PF = {'type':'PF', 'data':filtered_X}
        Kline = {'type':'Kline', 'data':bar.__dict__}
        content = cPickle.dumps([Kline, PF])
        print 'velocity = %.2f' % filtered_dX
        self.ctaEngine.sendChartData(content, 'Test')
    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        print "onOrder(): orderTime = %r ; vtOrderID = %r; status = %s" % (order.orderTime, order.vtOrderID, order.status)


    #----------------------------------------------------------------------
    def onTrade(self, trade):
        print '-'*50
        print 'onTrade'
        import pprint
        pprint.pprint(trade.__dict__)



        
        