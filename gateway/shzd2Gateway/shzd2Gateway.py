# encoding: UTF-8

import os
import json
from copy import copy
from datetime import datetime

from vnshzdmd import MdApi
from vnshzdtd import TdApi
from shzdDataType import *
from vtGateway import *
from language import text

# 以下为一些VT类型和CTP类型的映射字典
# 价格类型映射
priceTypeMap = {}
priceTypeMap[PRICETYPE_LIMITPRICE] = defineDict["TSHZD_OPT_LimitPrice"]
priceTypeMap[PRICETYPE_MARKETPRICE] = defineDict["TSHZD_OPT_AnyPrice"]
priceTypeMapReverse = {v:k for k, v in priceTypeMap.items()}

# 方向类型映射
directionMap = {}
directionMap[DIRECTION_LONG] = defineDict["TSHZD_D_Buy"]
directionMap[DIRECTION_SHORT] = defineDict["TSHZD_D_Sell"]
directionMapReverse = {v:k for k,v in directionMap.items()}

# 开平类型映射
offsetMap = {}
offsetMap[OFFSET_OPEN] = defineDict["TSHZD_OF_Open"]
offsetMap[OFFSET_CLOSE] = defineDict["TSHZD_OF_Close"]
offsetMap[OFFSET_CLOSETODAY] = defineDict["TSHZD_OF_CloseToday"]
offsetMap[OFFSET_CLOSEYESTERDAY] = defineDict["TSHZD_OF_CloseYesterday"]
offsetMapReverse = {v:k for k,v in offsetMap.items()}

# 交易所类型映射
exchangeMap = {}
exchangeMap[EXCHANGE_HKEX] = 'HKEX'
exchangeMap[EXCHANGE_CME] = 'CME'
exchangeMap[EXCHANGE_ICE] = 'ICE'
exchangeMapReverse = {v:k for k,v in exchangeMap.items()}

# 持仓类型映射
posiDirectionMap = {}
posiDirectionMap[DIRECTION_NET] = defineDict["TSHZD_PD_Net"]
posiDirectionMap[DIRECTION_LONG] = defineDict["TSHZD_PD_Long"]
posiDirectionMap[DIRECTION_SHORT] = defineDict["TSHZD_PD_Short"]
posiDirectionMapReverse = {v:k for k,v in posiDirectionMap.items()}

# 产品类型映射
productClassMap = {}
productClassMap[PRODUCT_FUTURES] = defineDict["TSHZD_PC_Futures"]
productClassMap[PRODUCT_OPTION] = defineDict["TSHZD_PC_Options"]
productClassMap[PRODUCT_COMBINATION] = defineDict["TSHZD_PC_Combination"]
productClassMapReverse = {v:k for k,v in productClassMap.items()}

# 委托状态映射
statusMap = {}
statusMap[STATUS_ALLTRADED] = defineDict["TSHZD_OST_AllTraded"]
statusMap[STATUS_PARTTRADED] = defineDict["TSHZD_OST_PartTradedQueueing"]
statusMap[STATUS_NOTTRADED] = defineDict["TSHZD_OST_NoTradeQueueing"]
statusMap[STATUS_CANCELLED] = defineDict["TSHZD_OST_Canceled"]
statusMapReverse = {v:k for k,v in statusMap.items()}

# 交易所币种映射
exchangeCurrencyMap = {}
exchangeCurrencyMap[EXCHANGE_CME] = 'USD'
exchangeCurrencyMap[EXCHANGE_HKEX] = 'HKD-HKFE'
exchangeCurrencyMapReverse = {v:k for k,v in exchangeCurrencyMap.items()}

AUTH_CODE = '55822DC39D9316D5111D9EED00C1CED81B6F0DCEA8D97DDEBD350D939CF8A9D304E3C73A742CFB80'

###########################################################################
class Shzd2Gateway(VtGateway):
    def __init__(self, eventEngine, gatewayName='SHZD2'):
        super(Shzd2Gateway, self).__init__(eventEngine, gatewayName)

        self.mdApi = ShzdMdApi(self)
        self.tdApi = ShzdTdApi(self)

        self.mdConnected = False
        self.tdConnected = False

        self.qryEnabled = True

        self.setting = {}
        

    #--------------------------------------------------------
    def connect(self):
        filename = self.gatewayName+'_connect.json'
        path = os.path.abspath(os.path.dirname(__file__))
        filename = os.path.join(path, filename)

        try:
            f = file(filename)
        except IOError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = text.LOADING_ERROR
            self.onLog(log)
            return
        
        setting = json.load(f)
        try:
            userID = str(setting['userId'])
            password = str(setting['userPwd'])
            tdAddress = 'tcp://' + str(setting['frontAddress']) +':'+str(setting['frontPort'])
            mdAddress = 'tcp://' + str(setting['marketAddress']) +':'+str(setting['marketPort'])
        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = text.CONFIG_KEY_MISSING
            self.onLog(log)
            return
        self.setting = setting
        #self.mdApi.connect(userID, password, tdAddress, mdAddress)
        self.tdApi.connect(userID, password, tdAddress)
        self.initQuery()

    #--------------------------------------------------------
    def initQuery(self):
        if self.qryEnabled:
            self.qryFunctionList = [self.qryAccount, self.qryPosition]
            self.qryCount = 0
            self.qryTrigger = 2
            self.qryNextFunction = 0
            self.startQuery()

    #--------------------------------------------------------
    def startQuery(self):
        self.eventEngine.register(EVENT_TIMER, self.query)  

    #----------------------------------------------------------------------
    def setQryEnabled(self, qryEnabled):
        """设置是否要启动循环查询"""
        self.qryEnabled = qryEnabled

    #--------------------------------------------------------
    def query(self, event):
        self.qryCount += 1
        if self.qryCount > self.qryTrigger:
            self.qryCount = 0

            function = self.qryFunctionList[self.qryNextFunction]
            function()

            self.qryNextFunction += 1
            if self.qryNextFunction == len(self.qryFunctionList):
                self.qryNextFunction = 0

    #--------------------------------------------------------
    def qryAccount(self):
        self.tdApi.qryAccount()

    #--------------------------------------------------------
    def qryPosition(self):
        self.tdApi.qryPosition()

    #--------------------------------------------------------
    def close(self):
        if self.mdConnected:
            self.mdApi.close()
        if self.tdConnected:
            self.tdApi.close()

    #--------------------------------------------------------
    def inConnected(self):
        return self.mdConnected and self.tdConnected

    #--------------------------------------------------------
    def getGatewaySetting(self):
        return self.setting

    #--------------------------------------------------------
    def subscribe(self, subscribeReq):
        self.mdApi.subscribe(subscribeReq)

    #--------------------------------------------------------
    def sendOrder(self, orderReq):
        return self.tdApi.sendOrder(orderReq)
    
    def cancelOrder(self, cancelOrderReq):
        self.tdApi.cancelOrder(cancelOrderReq)

###########################################################################
class ShzdMdApi(MdApi):
    def __init__(self, gateway):
        super(ShzdMdApi, self).__init__()
        self.gateway = gateway
        self.gatewayName = gateway.gatewayName

        self.reqID = EMPTY_INT
        self.connectionStatus = False
        self.loginStatus = False
        self.subscribedSymbols = set()

        self.userID = EMPTY_STRING
        self.password = EMPTY_STRING
        self.loginFrontAddress =  EMPTY_STRING
        self.frontAddress = EMPTY_STRING
    
    #--------------------------------------------------------
    def onFrontConnected(self):
        self.connectionStatus = True
        self.writeLog(text.DATA_SERVER_CONNECTED)
        self.gateway.mdConnected = True
        self.loginStatus = True
        print self.subscribedSymbols
        for sreq in self.subscribedSymbols:
            self.subscribe(sreq)

    #--------------------------------------------------------
    def onFrontLoginConnected(self):
        if not self.loginStatus:
            self.login()
        pass

    #--------------------------------------------------------
    def onFrontDisconnected(self, id):
        self.connectionStatus = False
        self.loginStatus = False
        self.gateway.mdConnected = False
        self.writeLog(text.DATA_SERVER_DISCONNECTED)

    #--------------------------------------------------------
    def onHeartBeatWarning(self, id):
        pass

    #--------------------------------------------------------
    def onRspUserLogin(self, data, error, id, last):
        if error['ErrorID'] == 0:
            if last:
                self.writeLog(text.DATA_SERVER_LOGIN)
                self.registerFront(self.frontAddress)
        else:
            err = VtErrorData()
            err.gatewayName = self.gatewayName
            err.errorID = error['ErrorID']
            err.errorMsg = error['ErrorMsg']
            self.gateway.onError(err)

    #--------------------------------------------------------
    def onRspUserLogout(self, data, error, id, last):
        # 如果登出成功，推送日志信息
        if error['ErrorID'] == 0:
            self.loginStatus = False
            self.gateway.mdConnected = False
            
            self.writeLog(text.DATA_SERVER_LOGOUT)
                
        # 否则，推送错误信息
        else:
            err = VtErrorData()
            err.gatewayName = self.gatewayName
            err.errorID = error['ErrorID']
            err.errorMsg = error['ErrorMsg'].decode('gbk')
            self.gateway.onError(err)

    #--------------------------------------------------------
    def onRspError(self, error, id, last):
        err = VtErrorData()
        err.gatewayName = self.gatewayName
        err.errorID = error['ErrorID']
        err.errorMsg = error['ErrorMsg']
        import pprint 
        pprint.pprint(err.__dict__)
        self.gateway.onError(err)

    #--------------------------------------------------------
    def onRspSubMarketData(self, data, error, id, last):
        pass

    #--------------------------------------------------------
    def onRspUnSubMarketData(self, data, error, id, last):
        pass

    #--------------------------------------------------------
    def onRtnDepthMarketData(self, data):
        # 忽略成交量为0的无效tick数据
        if not data['Volume']:
            return
        
        # 创建对象
        tick = VtTickData()
        tick.gatewayName = self.gatewayName
        
        tick.symbol = data['InstrumentID']
        tick.exchange = exchangeMapReverse.get(data['ExchangeID'], u'未知')
        tick.vtSymbol = tick.symbol #'.'.join([tick.symbol, EXCHANGE_UNKNOWN])
        
        tick.lastPrice = data['LastPrice']
        tick.volume = data['Volume']
        tick.openInterest = data['OpenInterest']
        tick.time = '.'.join([data['UpdateTime'], str(data['UpdateMillisec']/100)])
        
        # 这里由于交易所夜盘时段的交易日数据有误，所以选择本地获取
        #tick.date = data['TradingDay']
        tick.date = datetime.now().strftime('%Y%m%d')   
        
        tick.openPrice = data['OpenPrice']
        tick.highPrice = data['HighestPrice']
        tick.lowPrice = data['LowestPrice']
        tick.preClosePrice = data['PreClosePrice']
        
        tick.upperLimit = data['UpperLimitPrice']
        tick.lowerLimit = data['LowerLimitPrice']
        
        # CTP只有一档行情
        tick.bidPrice1 = data['BidPrice1']
        tick.bidVolume1 = data['BidVolume1']
        tick.askPrice1 = data['AskPrice1']
        tick.askVolume1 = data['AskVolume1']
        print tick.symbol, tick.lastPrice, tick.volume
        self.gateway.onTick(tick)

    #--------------------------------------------------------
    def onRtnFilledMarketData(self, data):
        pass
    
    #--------------------------------------------------------
    def connect(self, userID, password, loginFrontAddress, frontAddress):
        self.userID = userID
        self.password = password
        self.loginFrontAddress = loginFrontAddress
        self.frontAddress = frontAddress

        if not self.connectionStatus:
            path = os.getcwd() + '/temp/' + self.gatewayName + '/'
            if not os.path.exists(path):
                os.makedirs(path)
            self.createSHZdMarketApi(path)

            self.init()
            self.authonInfo(AUTH_CODE)
            self.registerLoginFront(self.loginFrontAddress)
            sleep(1)

    #--------------------------------------------------------
    def subscribe(self, subscribeReq):
        if self.loginStatus:
            substr = ','.join([subscribeReq.exchange, subscribeReq.symbol])
            self.subscribeMarketData(substr)
        self.subscribedSymbols.add(subscribeReq)

    #--------------------------------------------------------
    def login(self):
        if self.userID and self.password:
            self.reqID += 1
            req = {}
            req['UserID'] = self.userID
            req['Password'] = self.password
            self.reqUserLogin(req, self.reqID)

    #--------------------------------------------------------
    def close(self):
        self.release()
    
    #--------------------------------------------------------
    def writeLog(self, content):
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = content
        self.gateway.onLog(log)     

###########################################################################
class ShzdTdApi(TdApi):
    def __init__(self, gateway):
        super(ShzdTdApi, self).__init__()

        self.gateway = gateway
        self.gatewayName = gateway.gatewayName
        self.reqID = EMPTY_INT
        self.orderRef = EMPTY_INT

        self.connectionStatus = False
        self.loginStatus = False
        self.authStatus = False

        self.userID = EMPTY_STRING
        self.currencyInvestorIdMap = {}
        self.password = EMPTY_STRING
        self.address = EMPTY_STRING

        self.orderPrefix = datetime.now().strftime("%H%M%S.")
        self.posDict = {}
        self.symbolExchangeDict = {}    # 保存合约代码和交易所的映射关系
        self.symbolSizeDict = {}        # 保存合约代码和合约大小的映射关系
        self.OrderID_OrderSysID_Map = {}
    #----------------------------------------------------------------------
    def onFrontConnected(self):
        self.connectionStatus = True
        self.writeLog(text.TRADING_SERVER_CONNECTED)
        self.login()

    def onFrontLoginConnected(self):
        pass
    #----------------------------------------------------------------------
    def onFrontDisconnected(self, id):
        """服务器断开"""
        self.connectionStatus = False
        self.loginStatus = False
        self.gateway.tdConnected = False
    
        self.writeLog(text.TRADING_SERVER_DISCONNECTED)
    
    #----------------------------------------------------------------------
    def onHeartBeatWarning(self, id):
        pass
    
    #----------------------------------------------------------------------
    def onRspUserLogin(self, data, error, id, last):
        """
        ///交易日 直达
        TShZdDateType	TradingDay;
        ///登录成功时间
        TShZdTimeType	LoginTime;	
        ///用户代码  直达
        TShZdUserIDType	UserID;
        ///交易系统名称  直达
        TShZdSystemNameType	SystemName;	
        ///投资者帐号  资金账号  直达
        TShZdAccountIDType	AccountID;
        ///币种，账号的币种  直达
        TShZdCurrencyNoType CurrencyNo;	
        """

        if error['ErrorID'] == 0:
            self.loginStatus = True
            self.gateway.tdConnected = True
            self.writeLog(text.TRADING_SERVER_LOGIN)
            #print data['CurrencyNo']
            self.currencyInvestorIdMap[data['CurrencyNo']] = data['AccountID']
            self.reqID += 1
            self.reqQryInstrument({'ExchangeID': exchangeCurrencyMapReverse.get(data['CurrencyNo'], "CME")}, self.reqID)
        else:
            err = VtErrorData()
            err.gatewayName = self.gatewayName
            err.errorID = error['ErrorID']
            err.errorMsg = error['ErrorMsg']
            self.gateway.onError(err)
        
    #----------------------------------------------------------------------
    def onRspUserLogout(self, data, error, id, last):
        """登出回报"""
        # 如果登出成功，推送日志信息
        if error['ErrorID'] == 0:
            self.loginStatus = False
            self.gateway.tdConnected = False
            
            self.writeLog(text.TRADING_SERVER_LOGOUT)
                
        # 否则，推送错误信息
        else:
            err = VtErrorData()
            err.gatewayName = self.gatewayName
            err.errorID = error['ErrorID']
            err.errorMsg = error['ErrorMsg'].decode('gbk')
            self.gateway.onError(err)

    #----------------------------------------------------------------------
    def onRspUserPasswordUpdate(self, data, error, id, last):
        pass

    #----------------------------------------------------------------------
    def onRspOrderInsert(self, data, error, id, last):
        # import pprint
        # pprint.pprint(data)
        order = VtOrderData()
        order.gatewayName = self.gatewayName
        order.symbol = data['InstrumentID']
        order.exchange = exchangeMapReverse.get(data['ExchangeID'], '')
        order.vtSymbol = '.'.join([order.symbol, order.exchange])
        order.orderID = data['OrderLocalID']

        order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
        order.direction = directionMapReverse.get(data['Direction'], DIRECTION_UNKNOWN)
        order.offset = offsetMapReverse.get(data['CombOffsetFlag'], OFFSET_UNKNOWN)
        order.status = STATUS_UNKNOWN
        order.price = data['LimitPrice']
        order.totalVolume = data['VolumeTotalOriginal']
        self.gateway.onOrder(order)

        if error:
            err = VtErrorData()
            err.gatewayName = self.gatewayName
            err.errorID = error['ErrorID']
            err.errorMsg = error['ErrorMsg']
            self.gateway.onError(err)

    #----------------------------------------------------------------------
    def onRspParkedOrderInsert(self, data, error, id, last):
        pass

    def onRspParkedOrderAction(self, data, error, id, last):
        pass
    #----------------------------------------------------------------------
    def onRspOrderAction(self, data, error, id, last):
        err = VtErrorData()
        err.gatewayName = self.gatewayName
        err.errorID = error['ErrorID']
        err.errorMsg = error['ErrorMsg'].decode('gbk')
        self.gateway.onError(err)
        
    #----------------------------------------------------------------------
    def onRspRemoveParkedOrder(self, data, error, id, last):
        pass

    def onRspRemoveParkedOrderAction(self, data, error, id, last):
        pass

    def onRspQryOrder(self, data, error, id, last):
        pass

    def onRspQryTrade(self, data, error, id, last):
        pass

    #----------------------------------------------------------------------
    def onRspQryInvestorPosition(self, data, error, id, last):
        """///交易所代码  直达
        TShZdExchangeIDType	ExchangeID;
        ///合约代码  直达
        TShZdInstrumentIDType	InstrumentID;	
        ///资金代码  直达
        TShZdInvestorIDType	InvestorID;	
        ///持买量  直达
        TShZdVolumeType	HoldBuyVolume;
        ///持买开均价  直达
        TShZdMoneyType	HoldBuyOpenPrice;
        ///持买均价 直达
        TShZdMoneyType	HoldBuyPrice;
        ///持卖量  直达
        TShZdVolumeType	HoldSaleVolume;
        //持卖开均价  直达
        TShZdMoneyType	HoldSaleOpenPrice;
        ///持卖均价  直达
        TShZdMoneyType	HoldSalePrice;
        ///持买保证金  直达
        TShZdMoneyType	HoldBuyAmount;
        ///持卖保证金  直达
        TShZdMoneyType	HoldSaleAmount;
        ///开仓量  直达
        TShZdVolumeType	OpenVolume;
        ///成交量  直达
        TShZdVolumeType	FilledVolume;	
        ///成交均价  直达
        TShZdMoneyType	FilledAmount;	
        ///手续费  直达
        TShZdMoneyType	Commission;	
        ///持仓盈亏  直达
        TShZdMoneyType	PositionProfit;	
        ///交易日  直达
        TShZdDateType	TradingDay;	"""

        if data['InstrumentID']:
            
            direction = DIRECTION_NET

            if data['HoldBuyVolume'] > 0 and data['HoldSaleVolume'] == 0:
                direction = DIRECTION_LONG
            elif data['HoldSaleVolume'] > 0 and data['HoldBuyVolume'] == 0:
                direction = DIRECTION_SHORT

            # 获取持仓缓存对象
            posName = '.'.join([data['InvestorID'], data['InstrumentID'], direction])
            if posName in self.posDict:
                pos = self.posDict[posName]
            else:
                pos = VtPositionData()
                self.posDict[posName] = pos
                pos.gatewayName = self.gatewayName
                pos.symbol = data['InstrumentID']
                pos.vtSymbol = '.'.join([pos.symbol, data['ExchangeID']])

                pos.direction = direction
                pos.vtPositionName = '.'.join([pos.vtSymbol, pos.direction])

            # 持仓均价
            pos.price += data['HoldBuyPrice'] + data['HoldSalePrice']
            # 汇总总仓
            pos.position = data['HoldBuyVolume'] + data['HoldSaleVolume']
            pos.positionProfit += data['PositionProfit']
            pos.investorID = data['InvestorID']
            
        # 查询回报结束
        if last:
            # 遍历推送
            for pos in self.posDict.values():
                self.gateway.onPosition(pos)
            # 清空缓存
            self.posDict.clear()

    #----------------------------------------------------------------------
    def onRspQryTradingAccount(self, data, error, id, last):
        """
        ///用户代码  直达
        TShZdUserIDType	UserID;	
        ///资金账号  直达
        TShZdAccountIDType	AccountID;
        ///昨可用  直达
        TShZdMoneyType	PreMortgage;
        ///昨权益 直达
        TShZdMoneyType	PreCredit;
        ///昨结存 直达
        TShZdMoneyType	PreDeposit;
        ///今权益  直达
        TShZdMoneyType	CurrBalance;
        ///今可用 直达
        TShZdMoneyType	CurrUse;
        ///今结存 直达
        TShZdMoneyType	CurrDeposit;	
        ///入金金额   直达
        TShZdMoneyType	Deposit;
        ///出金金额   直达
        TShZdMoneyType	Withdraw;
        ///冻结的保证金  直达
        TShZdMoneyType	FrozenMargin;	
        ///当前保证金总额  直达
        TShZdMoneyType	CurrMargin;	
        ///手续费  直达
        TShZdMoneyType	Commission;
        ///平仓盈亏  直达
        TShZdMoneyType	CloseProfit;
        ///净盈利（总盈亏） 直达
        TShZdMoneyType	NetProfit;
        ///未到期平盈   直达
        TShZdMoneyType	UnCloseProfit;
        ///未冻结平盈  直达
        TShZdMoneyType	UnFrozenCloseProfit;	
        ///交易日
        TShZdDateType	TradingDay;	
        ///信用额度  直达
        TShZdMoneyType	Credit;
        ///配资资金  直达
        TShZdMoneyType	Mortgage;
        ///维持保证金  直达
        TShZdMoneyType	KeepMargin;
        ///期权利金  直达
        TShZdMoneyType	RoyaltyMargin;
        ///初始资金  直达
        TShZdMoneyType	FirstInitMargin;
        ///盈利率  直达
        TShZdMoneyType	ProfitRatio;
        ///风险率  直达
        TShZdMoneyType	RiskRatio;
        ///币种，账号的币种  直达
        TShZdCurrencyNoType CurrencyNo;
        ///货币与基币的汇率  直达
	    TShZdMoneyType	CurrencyRatio;
        """
        account = VtAccountData()
        account.gatewayName = self.gatewayName

        account.accountID = data['AccountID']
        account.vtAccountID = '.'.join([self.gatewayName, account.accountID])

        account.preBalance = data['PreCredit']
        account.available = data['CurrUse']
        account.commission = data['Commission']
        account.margin = data['CurrMargin']
        account.closeProfit = data['CloseProfit']
        account.positionProfit = data['NetProfit'] - data['CloseProfit']

        account.balance = data['CurrBalance']
        self.gateway.onAccount(account)

    #----------------------------------------------------------------------
    def onRspQryExchange(self, data, error, id, last):
        pass

    #----------------------------------------------------------------------
    def onRspQryInstrument(self, data, error, id, last):
        contract = VtContractData()
        contract.gatewayName = self.gatewayName

        contract.symbol = data['InstrumentID']
        contract.exchange = exchangeMapReverse.get(data['ExchangeID'], '')
        contract.vtSymbol = '.'.join([contract.symbol, contract.exchange])
        contract.name = str(data['InstrumentName'])

        contract.size = data['VolumeMultiple']
        contract.priceTick = data['PriceTick']
        contract.strikePrice = data['OptionPrice']
        contract.underlyingSymbol = data['OptionCommodityNo']

        if data['OptionType'] == defineDict['TSHZD_OP_Up']:
            contract.optionType = OPTION_CALL
        elif data['OptionType'] == defineDict['TSHZD_OP_Down']:
            contract.optionType = OPTION_PUT

        self.symbolExchangeDict[contract.symbol] = contract.exchange
        self.symbolSizeDict[contract.symbol] = contract.size

        self.gateway.onContract(contract)
        # import pprint
        # pprint.pprint(contract.__dict__)
        if last:
            self.writeLog(text.CONTRACT_DATA_RECEIVED)

    #----------------------------------------------------------------------
    def onRspQryInvestorPositionDetail(self, data, error, id, last):
        pass

    def onRspQryTransferSerial(self, data, error, id, last):
        pass

    #----------------------------------------------------------------------
    def onRspError(self, error, id, last):
        err = VtErrorData()
        err.gatewayName = self.gatewayName
        err.errorID = error['ErrorID']
        err.errorMsg = error['ErrorMsg'].decode('gbk')
        import pprint
        pprint.pprint(err.__dict__)
        self.gateway.onError(err)

    #----------------------------------------------------------------------
    def onRtnOrder(self, data):
        newref = data['OrderRef']
        self.orderRef = max(self.orderRef, int(newref))

        order = VtOrderData()
        order.gatewayName = self.gatewayName

        order.symbol = data['InstrumentID']
        order.exchange = exchangeMapReverse.get(data['ExchangeID'], '')
        order.vtSymbol = '.'.join([order.symbol, order.exchange])
        order.orderID = data['OrderLocalID']
        #order.orderID = data['OrderRef']
        order.vtOrderID = '.'.join([self.gatewayName, order.orderID])

        order.direction = directionMapReverse.get(data['Direction'], DIRECTION_UNKNOWN)
        order.offset = offsetMapReverse.get(data['CombOffsetFlag'], OFFSET_UNKNOWN)
        order.status = statusMapReverse.get(data['OrderSubmitStatus'], STATUS_UNKNOWN)

        order.price = data['LimitPrice']
        order.totalVolume = data['VolumeTotalOriginal']
        order.tradedVolume = data['VolumeTraded']
        order.orderTime = data['InsertTime']
        order.cancelTime = data['CancelTime']

        self.OrderID_OrderSysID_Map[order.vtOrderID] = data['OrderSysID']
        self.gateway.onOrder(order)

    #----------------------------------------------------------------------
    def onRtnTrade(self, data):
        print 'onTrade'
        trade = VtTradeData()
        trade.gatewayName = self.gatewayName

        trade.symbol = data['InstrumentID']
        trade.exchange = exchangeMapReverse.get(data['ExchangeID'], '')
        trade.vtSymbol = '.'.join([trade.symbol, trade.exchange])

        trade.tradeID = data['TradeID']
        trade.vtTradeID = '.'.join([self.gatewayName, trade.tradeID])

        trade.orderID = data['OrderLocalID']
        #trade.orderID = data['OrderRef']
        trade.vtOrderID = '.'.join([self.gatewayName, trade.orderID])

        trade.direction = directionMapReverse.get(data['Direction'],'')

        trade.offset = offsetMapReverse.get(data['OffsetFlag'], '')

        trade.price = data['Price']
        trade.volume = data['Volume']
        trade.tradeTime = data['TradeTime']
        import pprint
        pprint.pprint(trade.__dict__)
        self.gateway.onTrade(trade)

    #----------------------------------------------------------------------
    def onRtnTradeMoney(self, data):
        pass

    #----------------------------------------------------------------------
    def onErrRtnOrderInsert(self, data, error):
        print 'onErrRtnOrderInsert'
        order = VtOrderData()
        order.gatewayName = self.gatewayName
        order.symbol = data['InstrumentID']
        order.exchange = exchangeMapReverse.get(data['ExchangeID'],'')
        order.vtSymbol = '.'.join([order.symbol, order.exchange])
        order.orderID = data['OrderLocalID']
        #order.orderID = data['OrderRef']

        order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
        order.direction = directionMapReverse.get(data['Direction'], DIRECTION_UNKNOWN)
        order.offset = offsetMapReverse.get(data['CombOffsetFlag'], OFFSET_UNKNOWN)
        order.status = STATUS_REJECTED
        order.price = data['LimitPrice']
        order.totalVolume = data['VolumeTotalOriginal']
        print order.__dict__
        self.gateway.onOrder(order)

        err = VtErrorData()
        err.gatewayName = self.gatewayName
        err.errorID = error['ErrorID']
        err.errorMsg = error['ErrorMsg']
        self.gateway.onError(err)

    #----------------------------------------------------------------------
    def onRtnErrorConditionalOrder(self, data):
        pass

    def onRspQryParkedOrder(self, data, error, id, last):
        pass

    def onRspQryParkedOrderAction(self, data, error, id, last):
        pass

    def onRtnOpenCloseTime(self, data):
        pass

    def onRtnMarketOpenCloseTime(self, data):
        pass

    def onRtnCommonOpenCloseTime(self, data):
        pass

    def onRspMoneyRatio(self, data, error, id, last):
        pass

    #----------------------------------------------------------------------
    def connect(self, userID, password, address):
        self.userID = userID
        self.password = password
        self.address = address

        if not self.connectionStatus:
            path = os.getcwd() + '/temp/' + self.gatewayName + '/'
            if not os.path.exists(path):
                os.makedirs(path)
            self.createSHZdTraderApi(path)
            self.init()
            self.authonInfo(AUTH_CODE)
            self.getTradingDay()
            self.registerFront(self.address)
        else:
            self.login()

    #----------------------------------------------------------------------
    def login(self):
        if self.userID and self.password:
            req = {}
            req['UserID'] = self.userID
            req['Password'] = self.password
            self.reqID += 1
            self.reqUserLogin(req, self.reqID)

    #----------------------------------------------------------------------
    def qryAccount(self):
        self.reqID += 1
        req = {}
        req['UserID'] = self.userID
        req['InvestorID'] = self.userID
        self.reqQryTradingAccount(req, self.reqID)

    #----------------------------------------------------------------------
    def qryPosition(self):
        self.reqID += 1
        req = {}
        req['UserID'] = self.userID
        req['InvestorID'] = self.userID
        self.reqQryInvestorPosition(req, self.reqID)

    #----------------------------------------------------------------------
    def sendOrder(self, orderReq):
        """
        ///交易所代码  直达
        TShZdExchangeIDType	ExchangeID;
        ///直达的资金账号  直达
        TShZdInvestorIDType	InvestorID;
        ///合约代码 直达
        TShZdInstrumentIDType	InstrumentID;
        ///系统编号  直达
        TShZdOrderRefType	OrderRef;
        ///本地报单编号  直达
        TShZdOrderLocalIDType	OrderLocalID;
        ///用户代码  直达
        TShZdUserIDType	UserID;
        ///报单价格条件   1限价单 2市价单 3限价止损（stop to limit），4止损（stop to market） 直达
        TShZdOrderPriceTypeType	OrderPriceType;
        ///买卖方向   1买 2卖  直达
        TShZdDirectionType	Direction;
        ///组合开平标志
        TShZdCombOffsetFlagType	CombOffsetFlag;
        ///组合投机套保标志
        TShZdCombHedgeFlagType	CombHedgeFlag;
        ///价格  直达
        TShZdPriceType	LimitPrice;
        ///数量  直达
        TShZdVolumeType	VolumeTotalOriginal;
        ///有效期类型  （1=当日有效, 2=永久有效（GTC），3=OPG，4=IOC，5=FOK，6=GTD，7=ATC，8=FAK） 直达
        TShZdTimeConditionType	TimeCondition;
        ///强平编号  直达
        TShZdDateType	GTDDate;
        ///成交量类型  1=regular 2=FOK 3=IOC
        TShZdVolumeConditionType	VolumeCondition;
        ///最小成交量  必须小于等于委托量；有效期=4时，ShowVolume>=1小于委托量时是FOK，等于委托量时是FAK  直达
        TShZdVolumeType	MinVolume;
        ///触发条件
        TShZdContingentConditionType	ContingentCondition;
        ///止损价  触发价  直达
        TShZdPriceType	StopPrice;
        ///强平原因
        TShZdForceCloseReasonType	ForceCloseReason;
        /// 如果是冰山单，ShowVolume的值1到orderNumber，不是冰山单，ShowVolume的值为0  直达
        TShZdVolumeType	ShowVolume;	
        """
        self.reqID += 1
        self.orderRef += 1
        req = {}

        priceType = orderReq.priceType
        if orderReq.priceType == PRICETYPE_FOK:
            priceType = PRICETYPE_LIMITPRICE
            req['TimeCondition'] = typedefDict['TSHZD_TC_IOC']
            req['MinVolume'] = 0

        req['ExchangeID'] = exchangeMap.get(orderReq.exchange,'')
        currency = exchangeCurrencyMap.get(req['ExchangeID'], 'USD')
        req['OrderRef'] = str(self.orderRef)
        #req['OrderSysID'] = str(self.orderRef)
        req['UserID'] = self.userID
        print self.currencyInvestorIdMap
        req['InvestorID'] = self.currencyInvestorIdMap[currency]
        req['InstrumentID'] = orderReq.symbol
        req['Direction'] = directionMap.get(orderReq.direction, '')
        req['VolumeTotalOriginal'] = orderReq.volume
        req['LimitPrice'] = orderReq.price
        print 'priceType=',priceTypeMap.get(priceType, '')
        req['OrderPriceType'] = priceTypeMap.get(priceType, '')
        req['OrderLocalID'] = self.orderPrefix + str(self.orderRef).rjust(6, '0')

        self.reqOrderInsert(req, self.reqID)
        vtOrderID = '.'.join([self.gatewayName, req['OrderLocalID']])
        #vtOrderID = '.'.join([self.gatewayName, req['OrderRef']])
        return vtOrderID

    #----------------------------------------------------------------------
    def cancelOrder(self, cancelOrderReq):
        """
        ///系统编号
        TShZdOrderRefType	OrderRef;	
        ///报单编号
        TShZdOrderSysIDType	OrderSysID;
        ///操作标志
        TShZdActionFlagType	ActionFlag;
        ///修改的价格 （改单填写）
        TShZdPriceType	LimitPrice;
        ///数量变化(改单填写)
        TShZdVolumeType	VolumeChange;	
        ///用户代码
        TShZdUserIDType	UserID;	
        """
        self.reqID += 1
        req = {}
        #req['OrderRef'] = cancelOrderReq.orderID
        req['OrderSysID'] = self.OrderID_OrderSysID_Map.get(cancelOrderReq.orderID, '')
        req['ActionFlag'] = defineDict['TSHZD_AF_Delete']
        req['UserID'] = self.userID

        self.reqOrderAction(req, self.reqID)

    #----------------------------------------------------------------------
    def close(self):
        self.release()
    #----------------------------------------------------------------------
    def writeLog(self, content):
        """发出日志"""
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = content
        self.gateway.onLog(log) 

#######################################
def testtd():
    import sys
    from PyQt4 import QtCore
    app = QtCore.QCoreApplication(sys.argv)

    def print_log(event):
        log = event.dict_['data']
        print ':'.join([log.logTime, log.logContent])

    eventEngine = EventEngine2()
    eventEngine.register(EVENT_LOG, print_log)
    eventEngine.start()

    gateway = Shzd2Gateway(eventEngine)
    gateway.connect()

    # sleep(1)
    # req = VtOrderReq()
    # req.direction = DIRECTION_LONG
    # req.exchange = 'CME'
    # req.symbol = 'GC1712'
    # req.volume = 1
    # req.price = 1275.0
    # req.priceType = PRICETYPE_LIMITPRICE
    # vtOrderID = gateway.sendOrder(req)

    # sleep(1)
    # import pprint
    # pprint.pprint(gateway.tdApi.OrderID_OrderSysID_Map)
    # cancelreq = VtCancelOrderReq()
    # cancelreq.orderID = vtOrderID
    # gateway.cancelOrder(cancelreq)
    sys.exit(app.exec_())

# def testmd():
#     import sys
#     from PyQt4 import QtCore
#     app = QtCore.QCoreApplication(sys.argv)

#     def print_log(event):
#         log = event.dict_['data']
#         print ':'.join([log.logTime, log.logContent])

#     eventEngine = EventEngine2()
#     eventEngine.register(EVENT_LOG, print_log)
#     eventEngine.start()

#     gateway = Shzd2Gateway(eventEngine)
#     gateway.connect()
#     subreq1 = VtSubscribeReq()
#     subreq1.symbol = 'GC1712'
#     subreq1.exchange = 'CME'

#     subreq2 = VtSubscribeReq()
#     subreq2.symbol = 'CL1712'
#     subreq2.exchange = 'CME'
#     gateway.subscribe(subreq1)
#     gateway.subscribe(subreq2)

#     sys.exit(app.exec_())