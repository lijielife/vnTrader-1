# encoding: utf-8
from vnctptd import TdApi
from functools import wraps
#from logger.log import get_logger
import traceback
from time import sleep

def debug(func):
    """简单装饰器用于输出函数名"""
    def wrapper(*args, **kw):
        print("")
        print(str(func.__name__))
        return func(*args, **kw)
    return wrapper

class MyTdApi(TdApi):
    connectionStatus = False
    reqID = 0
    @debug
    def onFrontConnected(self):
        """服务器连接"""
        self.connectionStatus = True
        self.login()
        
    #----------------------------------------------------------------------
    @debug
    def onFrontDisconnected(self, n):
        """服务器断开"""
        self.connectionStatus = False
        self.loginStatus = False

        
    #----------------------------------------------------------------------
    @debug
    def onHeartBeatWarning(self, n):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspAuthenticate(self, data, error, n, last):
        """验证客户端回报"""
        if error['ErrorID'] == 0:
            self.authStatus = True
            
            self.writeLog(text.TRADING_SERVER_AUTHENTICATED)
            
            self.login()
        
    #----------------------------------------------------------------------
    @debug
    def onRspUserLogin(self, data, error, n, last):
        """登陆回报"""
        # 如果登录成功，推送日志信息
        if error['ErrorID'] == 0:
            self.frontID = str(data['FrontID'])
            self.sessionID = str(data['SessionID'])
            self.loginStatus = True
            
            #self.writeLog(text.TRADING_SERVER_LOGIN)
            # 确认结算信息
            req = {}
            req['BrokerID'] = self.brokerID
            req['InvestorID'] = self.userID
            self.reqID += 1
            self.reqSettlementInfoConfirm(req, self.reqID)              
                
        # 否则，推送错误信息
        else:
            print 'error:',str(error).decode('string_escape')
        
    #----------------------------------------------------------------------
    @debug
    def onRspUserLogout(self, data, error, n, last):
        """登出回报"""
        # 如果登出成功，推送日志信息
        if error['ErrorID'] == 0:
            self.loginStatus = False
            
            
            self.writeLog(text.TRADING_SERVER_LOGOUT)
                
        # 否则，推送错误信息
        else:
            print 'error:', str(error).decode('string_escape')
        
    #----------------------------------------------------------------------
    @debug
    def onRspUserPasswordUpdate(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspTradingAccountPasswordUpdate(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspOrderInsert(self, data, error, n, last):
        """发单错误（柜台）"""
        # 推送委托信息
        print data        
    #----------------------------------------------------------------------
    @debug
    def onRspParkedOrderInsert(self, data, error, n, last):
        """"""
        print 'insert parked'
        import pprint
        pprint.pprint(data)
        print 'status:%s' %data['Status']
        
    #----------------------------------------------------------------------
    @debug
    def onRspParkedOrderAction(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspOrderAction(self, data, error, n, last):
        """撤单错误（柜台）"""
        print data
        
    #----------------------------------------------------------------------
    @debug
    def onRspQueryMaxOrderVolume(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspSettlementInfoConfirm(self, data, error, n, last):
        """确认结算信息回报"""
        #self.writeLog(text.SETTLEMENT_INFO_CONFIRMED)
        
        # 查询合约代码
        #self.reqID += 1
        #self.reqQryInstrument({}, self.reqID)
        pass

    #----------------------------------------------------------------------
    @debug
    def onRspRemoveParkedOrder(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspRemoveParkedOrderAction(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspExecOrderInsert(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspExecOrderAction(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspForQuoteInsert(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQuoteInsert(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQuoteAction(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspLockInsert(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspCombActionInsert(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryOrder(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryTrade(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryInvestorPosition(self, data, error, n, last):
        """持仓查询回报"""
        print data
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryTradingAccount(self, data, error, n, last):
        """资金账户查询回报"""
        print data
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryInvestor(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryTradingCode(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryInstrumentMarginRate(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryInstrumentCommissionRate(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryExchange(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryProduct(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryInstrument(self, data, error, n, last):
        """合约查询回报"""
        print str(data).decode('string_escape')
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryDepthMarketData(self, data, error, n, last):
        """"""
        print self.userID, data['AskPrice1'], data['AskVolume1']
        
    #----------------------------------------------------------------------
    @debug
    def onRspQrySettlementInfo(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryTransferBank(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryInvestorPositionDetail(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryNotice(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQrySettlementInfoConfirm(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryInvestorPositionCombineDetail(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryCFMMCTradingAccountKey(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryEWarrantOffset(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryInvestorProductGroupMargin(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryExchangeMarginRate(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryExchangeMarginRateAdjust(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryExchangeRate(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQrySecAgentACIDMap(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryProductExchRate(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryProductGroup(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryOptionInstrTradeCost(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryOptionInstrCommRate(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryExecOrder(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryForQuote(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryQuote(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryLock(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryLockPosition(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryInvestorLevel(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryExecFreeze(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryCombInstrumentGuard(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryCombAction(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryTransferSerial(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryAccountregister(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspError(self, error, n, last):
        """错误回报"""
        err = VtErrorData()
        err.gatewayName = self.gatewayName
        err.errorID = error['ErrorID']
        err.errorMsg = error['ErrorMsg'].decode('gbk')
        self.gateway.onError(err)
        
    #----------------------------------------------------------------------
    @debug
    def onRtnOrder(self, data):
        """报单回报"""
        print data
        
    #----------------------------------------------------------------------
    @debug
    def onRtnTrade(self, data):
        """成交回报"""
        print data
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnOrderInsert(self, data, error):
        """发单错误回报（交易所）"""
        print data
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnOrderAction(self, data, error):
        """撤单错误回报（交易所）"""
        print data
        
    #----------------------------------------------------------------------
    def onRtnInstrumentStatus(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnTradingNotice(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnErrorConditionalOrder(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnExecOrder(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnExecOrderInsert(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnExecOrderAction(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnForQuoteInsert(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnQuote(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnQuoteInsert(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnQuoteAction(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnForQuoteRsp(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnCFMMCTradingAccountToken(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnLock(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnLockInsert(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnCombAction(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnCombActionInsert(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryContractBank(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryParkedOrder(self, data, error, n, last):
        """"""
        print 'onRspQryParkedOrder'
        import pprint
        pprint.pprint(data)
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryParkedOrderAction(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryTradingNotice(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryBrokerTradingParams(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQryBrokerTradingAlgos(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQueryCFMMCTradingAccountToken(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnFromBankToFutureByBank(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnFromFutureToBankByBank(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnRepealFromBankToFutureByBank(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnRepealFromFutureToBankByBank(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnFromBankToFutureByFuture(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnFromFutureToBankByFuture(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnRepealFromBankToFutureByFutureManual(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnRepealFromFutureToBankByFutureManual(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnQueryBankBalanceByFuture(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnBankToFutureByFuture(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnFutureToBankByFuture(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnRepealBankToFutureByFutureManual(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnRepealFutureToBankByFutureManual(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onErrRtnQueryBankBalanceByFuture(self, data, error):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnRepealFromBankToFutureByFuture(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnRepealFromFutureToBankByFuture(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspFromBankToFutureByFuture(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspFromFutureToBankByFuture(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRspQueryBankAccountMoneyByFuture(self, data, error, n, last):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnOpenAccountByBank(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnCancelAccountByBank(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    @debug
    def onRtnChangeAccountByBank(self, data):
        """"""
        pass
        
    #----------------------------------------------------------------------
    def connect(self, userID, password, brokerID, address, authCode, userProductInfo):
        """初始化连接"""
        self.userID = userID                # 账号
        self.password = password            # 密码
        self.brokerID = brokerID            # 经纪商代码
        self.address = address              # 服务器地址
        self.authCode = authCode            #验证码
        self.userProductInfo = userProductInfo  #产品信息
        
        # 如果尚未建立服务器连接，则进行连接
        if not self.connectionStatus:
            # 创建C++环境中的API对象，这里传入的参数是需要用来保存.con文件的文件夹路径

            self.createFtdcTraderApi('')
            #self.getTradingDay()
            # 设置数据同步模式为推送从今日开始所有数据
            self.subscribePrivateTopic(0)
            self.subscribePublicTopic(0)            
            
            # 注册服务器地址
            self.registerFront(self.address)
            
            # 初始化连接，成功会调用onFrontConnected
            self.init()
            
        # 若已经连接但尚未登录，则进行登录
        else:
            if self.requireAuthentication and not self.authStatus:
                self.authenticate()
            elif not self.loginStatus:
                self.login()
    
    #----------------------------------------------------------------------
    def login(self):
        """连接服务器"""
        # 如果填入了用户名密码等，则登录
        if self.userID and self.password and self.brokerID:
            req = {}
            req['UserID'] = self.userID
            req['Password'] = self.password
            req['BrokerID'] = self.brokerID
            self.reqID += 1
            self.reqUserLogin(req, self.reqID)   
            
    #----------------------------------------------------------------------
    def authenticate(self):
        """申请验证"""
        if self.userID and self.brokerID and self.authCode and self.userProductInfo:
            req = {}
            req['UserID'] = self.userID
            req['BrokerID'] = self.brokerID
            req['AuthCode'] = self.authCode
            req['UserProductInfo'] = self.userProductInfo
            self.reqID +=1
            self.reqAuthenticate(req, self.reqID)

    #----------------------------------------------------------------------
    def qryAccount(self):
        """查询账户"""
        self.reqID += 1
        self.reqQryTradingAccount({}, self.reqID)
        
    #----------------------------------------------------------------------
    def qryPosition(self):
        """查询持仓"""
        self.reqID += 1
        req = {}
        req['BrokerID'] = self.brokerID
        req['InvestorID'] = self.userID
        self.reqQryInvestorPosition(req, self.reqID)

    def qryParkedOrder(self):
        self.reqID += 1
        req = {}
        req['BrokerID'] = self.brokerID
        req['InvestorID'] = self.userID
        self.reqQryParkedOrder(req, self.reqID)
    
    def qryDepthMarketData(self, symbol):
        self.reqID += 1
        req = {}
        req['InstrumentID'] = symbol
        req['ExchangeID'] = ''
        self.reqQryDepthMarketData(req, self.reqID)
    #----------------------------------------------------------------------
    def sendOrder(self, orderReq, parked=False):
        """发单"""
        self.reqID += 1
        self.orderRef += 1
        
        req = {}
        
        req['InstrumentID'] = orderReq.symbol
        req['LimitPrice'] = orderReq.price
        req['VolumeTotalOriginal'] = orderReq.volume
        
        # 下面如果由于传入的类型本接口不支持，则会返回空字符串
        req['OrderPriceType'] = priceTypeMap.get(orderReq.priceType, '')
        req['Direction'] = directionMap.get(orderReq.direction, '')
        req['CombOffsetFlag'] = offsetMap.get(orderReq.offset, '')
            
        req['OrderRef'] = str(self.orderRef)
        req['InvestorID'] = self.userID
        req['UserID'] = self.userID
        req['BrokerID'] = self.brokerID
        
        req['CombHedgeFlag'] = defineDict['THOST_FTDC_HF_Speculation']       # 投机单
        req['ContingentCondition'] = defineDict['THOST_FTDC_CC_Immediately'] # 立即发单
        req['ForceCloseReason'] = defineDict['THOST_FTDC_FCC_NotForceClose'] # 非强平
        req['IsAutoSuspend'] = 0                                             # 非自动挂起
        req['TimeCondition'] = defineDict['THOST_FTDC_TC_GFD']               # 今日有效
        req['VolumeCondition'] = defineDict['THOST_FTDC_VC_AV']              # 任意成交量
        req['MinVolume'] = 1                                                 # 最小成交量为1
        
        if not parked:
            # 普通下单
            # 判断FAK和FOK
            if orderReq.priceType == PRICETYPE_FAK:
                req['OrderPriceType'] = defineDict["THOST_FTDC_OPT_LimitPrice"]
                req['TimeCondition'] = defineDict['THOST_FTDC_TC_IOC']
                req['VolumeCondition'] = defineDict['THOST_FTDC_VC_AV']
            if orderReq.priceType == PRICETYPE_FOK:
                req['OrderPriceType'] = defineDict["THOST_FTDC_OPT_LimitPrice"]
                req['TimeCondition'] = defineDict['THOST_FTDC_TC_IOC']
                req['VolumeCondition'] = defineDict['THOST_FTDC_VC_CV']        
            self.reqOrderInsert(req, self.reqID)
            vtOrderID = '.'.join([self.gatewayName, str(self.orderRef)])
        else:
            # 预埋单
            del req['OrderRef']
            self.reqParkedOrderInsert(req, self.reqID)
            vtOrderID = '.'.join([self.gatewayName, 'parked', str(self.orderRef)])
        
        # 返回订单号（字符串），便于某些算法进行动态管理
        return vtOrderID
    

    #----------------------------------------------------------------------
    def cancelOrder(self, cancelOrderReq):
        """撤单"""
        self.reqID += 1

        req = {}
        
        req['InstrumentID'] = cancelOrderReq.symbol
        req['ExchangeID'] = cancelOrderReq.exchange
        req['OrderRef'] = cancelOrderReq.orderID
        req['FrontID'] = cancelOrderReq.frontID
        req['SessionID'] = cancelOrderReq.sessionID
        
        req['ActionFlag'] = defineDict['THOST_FTDC_AF_Delete']
        req['BrokerID'] = self.brokerID
        req['InvestorID'] = self.userID
        
        self.reqOrderAction(req, self.reqID)
        
    #----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.exit()

def test():
    from PyQt4 import QtCore
    import sys
    app = QtCore.QCoreApplication(sys.argv)    
    brokerID1 = '9999'
    tdAddress1 = "tcp://180.168.146.187:10000"
    userID1 = '090923'
    password1 = 'fdfzalb'

    authCode = ''
    userProductInfo = ''
    api1 = MyTdApi()
    api1.connect(userID1, password1, brokerID1, tdAddress1, '', '')
    sys.exit(app.exec_())

if __name__ == '__main__':
    test()
