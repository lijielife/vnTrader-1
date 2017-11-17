@simple_log
def onFrontConnected(self):
    pass

@simple_log
def onFrontDisconnected(self, i):
    pass

@simple_log
def onHeartBeatWarning(self, i):
    pass

@simple_log
def onRspAuthenticate(self, data, error, id, last):
    pass

@simple_log
def onRspUserLogin(self, data, error, id, last):
    pass

@simple_log
def onRspUserLogout(self, data, error, id, last):
    pass

@simple_log
def onRspUserPasswordUpdate(self, data, error, id, last):
    pass

@simple_log
def onRspTradingAccountPasswordUpdate(self, data, error, id, last):
    pass

@simple_log
def onRspOrderInsert(self, data, error, id, last):
    pass

@simple_log
def onRspParkedOrderInsert(self, data, error, id, last):
    pass

@simple_log
def onRspParkedOrderAction(self, data, error, id, last):
    pass

@simple_log
def onRspOrderAction(self, data, error, id, last):
    pass

@simple_log
def onRspQueryMaxOrderVolume(self, data, error, id, last):
    pass

@simple_log
def onRspSettlementInfoConfirm(self, data, error, id, last):
    pass

@simple_log
def onRspRemoveParkedOrder(self, data, error, id, last):
    pass

@simple_log
def onRspRemoveParkedOrderAction(self, data, error, id, last):
    pass

@simple_log
def onRspExecOrderInsert(self, data, error, id, last):
    pass

@simple_log
def onRspExecOrderAction(self, data, error, id, last):
    pass

@simple_log
def onRspForQuoteInsert(self, data, error, id, last):
    pass

@simple_log
def onRspQuoteInsert(self, data, error, id, last):
    pass

@simple_log
def onRspQuoteAction(self, data, error, id, last):
    pass

@simple_log
def onRspLockInsert(self, data, error, id, last):
    pass

@simple_log
def onRspCombActionInsert(self, data, error, id, last):
    pass

@simple_log
def onRspQryOrder(self, data, error, id, last):
    pass

@simple_log
def onRspQryTrade(self, data, error, id, last):
    pass

@simple_log
def onRspQryInvestorPosition(self, data, error, id, last):
    pass

@simple_log
def onRspQryTradingAccount(self, data, error, id, last):
    pass

@simple_log
def onRspQryInvestor(self, data, error, id, last):
    pass

@simple_log
def onRspQryTradingCode(self, data, error, id, last):
    pass

@simple_log
def onRspQryInstrumentMarginRate(self, data, error, id, last):
    pass

@simple_log
def onRspQryInstrumentCommissionRate(self, data, error, id, last):
    pass

@simple_log
def onRspQryExchange(self, data, error, id, last):
    pass

@simple_log
def onRspQryProduct(self, data, error, id, last):
    pass

@simple_log
def onRspQryInstrument(self, data, error, id, last):
    pass

@simple_log
def onRspQryDepthMarketData(self, data, error, id, last):
    pass

@simple_log
def onRspQrySettlementInfo(self, data, error, id, last):
    pass

@simple_log
def onRspQryTransferBank(self, data, error, id, last):
    pass

@simple_log
def onRspQryInvestorPositionDetail(self, data, error, id, last):
    pass

@simple_log
def onRspQryNotice(self, data, error, id, last):
    pass

@simple_log
def onRspQrySettlementInfoConfirm(self, data, error, id, last):
    pass

@simple_log
def onRspQryInvestorPositionCombineDetail(self, data, error, id, last):
    pass

@simple_log
def onRspQryCFMMCTradingAccountKey(self, data, error, id, last):
    pass

@simple_log
def onRspQryEWarrantOffset(self, data, error, id, last):
    pass

@simple_log
def onRspQryInvestorProductGroupMargin(self, data, error, id, last):
    pass

@simple_log
def onRspQryExchangeMarginRate(self, data, error, id, last):
    pass

@simple_log
def onRspQryExchangeMarginRateAdjust(self, data, error, id, last):
    pass

@simple_log
def onRspQryExchangeRate(self, data, error, id, last):
    pass

@simple_log
def onRspQrySecAgentACIDMap(self, data, error, id, last):
    pass

@simple_log
def onRspQryProductExchRate(self, data, error, id, last):
    pass

@simple_log
def onRspQryProductGroup(self, data, error, id, last):
    pass

@simple_log
def onRspQryOptionInstrTradeCost(self, data, error, id, last):
    pass

@simple_log
def onRspQryOptionInstrCommRate(self, data, error, id, last):
    pass

@simple_log
def onRspQryExecOrder(self, data, error, id, last):
    pass

@simple_log
def onRspQryForQuote(self, data, error, id, last):
    pass

@simple_log
def onRspQryQuote(self, data, error, id, last):
    pass

@simple_log
def onRspQryLock(self, data, error, id, last):
    pass

@simple_log
def onRspQryLockPosition(self, data, error, id, last):
    pass

@simple_log
def onRspQryInvestorLevel(self, data, error, id, last):
    pass

@simple_log
def onRspQryExecFreeze(self, data, error, id, last):
    pass

@simple_log
def onRspQryCombInstrumentGuard(self, data, error, id, last):
    pass

@simple_log
def onRspQryCombAction(self, data, error, id, last):
    pass

@simple_log
def onRspQryTransferSerial(self, data, error, id, last):
    pass

@simple_log
def onRspQryAccountregister(self, data, error, id, last):
    pass

@simple_log
def onRspError(self, error, id, last):
    pass

@simple_log
def onRtnOrder(self, data):
    pass

@simple_log
def onRtnTrade(self, data):
    pass

@simple_log
def onErrRtnOrderInsert(self, data, error):
    pass

@simple_log
def onErrRtnOrderAction(self, data, error):
    pass

@simple_log
def onRtnInstrumentStatus(self, data):
    pass

@simple_log
def onRtnTradingNotice(self, data):
    pass

@simple_log
def onRtnErrorConditionalOrder(self, data):
    pass

@simple_log
def onRtnExecOrder(self, data):
    pass

@simple_log
def onErrRtnExecOrderInsert(self, data, error):
    pass

@simple_log
def onErrRtnExecOrderAction(self, data, error):
    pass

@simple_log
def onErrRtnForQuoteInsert(self, data, error):
    pass

@simple_log
def onRtnQuote(self, data):
    pass

@simple_log
def onErrRtnQuoteInsert(self, data, error):
    pass

@simple_log
def onErrRtnQuoteAction(self, data, error):
    pass

@simple_log
def onRtnForQuoteRsp(self, data):
    pass

@simple_log
def onRtnCFMMCTradingAccountToken(self, data):
    pass

@simple_log
def onRtnLock(self, data):
    pass

@simple_log
def onErrRtnLockInsert(self, data, error):
    pass

@simple_log
def onRtnCombAction(self, data):
    pass

@simple_log
def onErrRtnCombActionInsert(self, data, error):
    pass

@simple_log
def onRspQryContractBank(self, data, error, id, last):
    pass

@simple_log
def onRspQryParkedOrder(self, data, error, id, last):
    pass

@simple_log
def onRspQryParkedOrderAction(self, data, error, id, last):
    pass

@simple_log
def onRspQryTradingNotice(self, data, error, id, last):
    pass

@simple_log
def onRspQryBrokerTradingParams(self, data, error, id, last):
    pass

@simple_log
def onRspQryBrokerTradingAlgos(self, data, error, id, last):
    pass

@simple_log
def onRspQueryCFMMCTradingAccountToken(self, data, error, id, last):
    pass

@simple_log
def onRtnFromBankToFutureByBank(self, data):
    pass

@simple_log
def onRtnFromFutureToBankByBank(self, data):
    pass

@simple_log
def onRtnRepealFromBankToFutureByBank(self, data):
    pass

@simple_log
def onRtnRepealFromFutureToBankByBank(self, data):
    pass

@simple_log
def onRtnFromBankToFutureByFuture(self, data):
    pass

@simple_log
def onRtnFromFutureToBankByFuture(self, data):
    pass

@simple_log
def onRtnRepealFromBankToFutureByFutureManual(self, data):
    pass

@simple_log
def onRtnRepealFromFutureToBankByFutureManual(self, data):
    pass

@simple_log
def onRtnQueryBankBalanceByFuture(self, data):
    pass

@simple_log
def onErrRtnBankToFutureByFuture(self, data, error):
    pass

@simple_log
def onErrRtnFutureToBankByFuture(self, data, error):
    pass

@simple_log
def onErrRtnRepealBankToFutureByFutureManual(self, data, error):
    pass

@simple_log
def onErrRtnRepealFutureToBankByFutureManual(self, data, error):
    pass

@simple_log
def onErrRtnQueryBankBalanceByFuture(self, data, error):
    pass

@simple_log
def onRtnRepealFromBankToFutureByFuture(self, data):
    pass

@simple_log
def onRtnRepealFromFutureToBankByFuture(self, data):
    pass

@simple_log
def onRspFromBankToFutureByFuture(self, data, error, id, last):
    pass

@simple_log
def onRspFromFutureToBankByFuture(self, data, error, id, last):
    pass

@simple_log
def onRspQueryBankAccountMoneyByFuture(self, data, error, id, last):
    pass

@simple_log
def onRtnOpenAccountByBank(self, data):
    pass

@simple_log
def onRtnCancelAccountByBank(self, data):
    pass

@simple_log
def onRtnChangeAccountByBank(self, data):
    pass
