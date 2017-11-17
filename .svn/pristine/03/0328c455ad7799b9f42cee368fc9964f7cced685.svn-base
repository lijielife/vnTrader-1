def subscribe(self, subscribeReq):
        """订阅行情"""
        
        # 如果尚未连接行情，则将订阅请求缓存下来后直接返回
        if not self.connected:
            self.subscribeReqDict[subscribeReq.symbol] = subscribeReq
            return
        
        contract = Contract()
        contract.localSymbol = str(subscribeReq.symbol)
        contract.symbol = str(subscribeReq.symbol)
        contract.exchange = exchangeMap.get(subscribeReq.exchange, '')
        contract.secType = productClassMap.get(subscribeReq.productClass, '')
        contract.currency = currencyMap.get(subscribeReq.currency, '')
        contract.expiry = subscribeReq.expiry
        contract.strike = subscribeReq.strikePrice
        contract.right = optionTypeMap.get(subscribeReq.optionType, '')
        

        # 获取合约详细信息
        self.tickerId += 1
        self.api.reqContractDetails(self.tickerId, contract)        
        
        # 创建合约对象并保存到字典中
        ct = VtContractData()
        ct.gatewayName = self.gatewayName
        ct.symbol = str(subscribeReq.symbol)
        ct.exchange = subscribeReq.exchange
        ct.vtSymbol = '.'.join([ct.symbol, ct.exchange])
        ct.productClass = subscribeReq.productClass
        self.contractDict[ct.vtSymbol] = ct
        
        # 订阅行情
        self.tickerId += 1   
        self.api.reqMktData(self.tickerId, contract, '', False, TagValueList())