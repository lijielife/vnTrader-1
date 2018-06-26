
# encoding: UTF-8
from datetime import datetime, timedelta

import pandas as pd

import vtPath
from ctaBase import *
from ctaStrategy import ctaEngine2
#from data.loader import DataLoader
from data.csv_loader import DataLoader
from gateway import GATEWAY_DICT
from vtEngine import MainEngine

__BAR__ = False

if __name__ == '__main__':
    mainEngine = MainEngine()
    mainEngine.dbConnect()
    drEngine = mainEngine.drEngine
    drEngine.loadSetting()
    dl = DataLoader()
    if __BAR__:
        # ru
        #df_rs = dl.LoadBar('ru1305', '20130104', '20130218', bin='1min')
        #df_rs = dl.LoadBar('ru1309', '20130219', '20130627', bin='1min')
        #df_rs = dl.LoadBar('ru1401', '20130628', '20131103', bin='1min')
        #df_rs = dl.LoadBar('ru1405', '20131104', '20140227', bin='1min')
        #df_rs = dl.LoadBar('ru1409', '20140228', '20140722', bin='1min')
        #df_rs = dl.LoadBar('ru1501', '20140723', '20141120', bin='1min')
        #df_rs = dl.LoadBar('ru1505', '20141121', '20150303', bin='1min')
        #df_rs = dl.LoadBar('ru1509', '20150304', '20150715', bin='1min')
        #df_rs = dl.LoadBar('ru1601', '20150716', '20151125', bin='1min')
        #df_rs = dl.LoadBar('ru1605', '20151126', '20160320', bin='1min')
        #df_rs = dl.LoadBar('ru1609', '20160321', '20160802', bin='1min')
        #df_rs = dl.LoadBar('ru1701', '20160803', '20161127', bin='1min')
        #df_rs = dl.LoadBar('ru1705', '20161128', '20170101', bin='1min')

        # rb
        #df_rs = dl.LoadBar('rb1705', '20170101', '20170322', bin='1min')
        #df_rs = dl.LoadBar('rb1710', '20170323', '20170807', bin='1min')
        #df_rs = dl.LoadBar('rb1801', '20170808', '20171108', bin='1min')
        #df_rs = dl.LoadBar('rb1805', '20171109', '20180329', bin='1min')
        #df_rs = dl.LoadBar('rb1810', '20180330', '20180501', bin='1min')
        df_rs = dl.LoadBar('a1801', '20180101', '20180509', bin='1min')



        dict_rs = df_rs.to_dict(orient='split')
        df_rs = None
        N = len(dict_rs['data'])

        for i in range(N):
            bar = CtaBarData()
            bar.vtSymbol = 'a1801'
            bar.datetime = dict_rs['index'][i].to_pydatetime()
            data = dict_rs['data'][i]
            bar.open = data[0]
            bar.high = data[1]
            bar.low = data[2]
            bar.close = data[3]
            bar.volume = data[4]
            drEngine.insertData(MINUTE_DB_NAME, bar.vtSymbol, bar)
            print 'insert bar'
    else:
        # rb
        #df_rs = dl.LoadTick('rb1705', '20170101', '20170201')
        #df_rs = dl.LoadTick('rb1705', '20170202', '20170301')
        #df_rs = dl.LoadTick('rb1705', '20170302', '20170322')

        #df_rs = dl.LoadTick('rb1710', '20170323', '20170401')
        #df_rs = dl.LoadTick('rb1710', '20170402', '20170501')
        #df_rs = dl.LoadTick('rb1710', '20170502', '20170601')
        #df_rs = dl.LoadTick('rb1710', '20170602', '20170701')
        #df_rs = dl.LoadTick('rb1710', '20170702', '20170807')

        #df_rs = dl.LoadTick('rb1801', '20170808', '20170901')
        #df_rs = dl.LoadTick('rb1801', '20170902', '20171001')
        #df_rs = dl.LoadTick('rb1801', '20171002', '20171108')

        #df_rs = dl.LoadTick('rb1805', '20171109', '20171201')
        #df_rs = dl.LoadTick('rb1805', '20171202', '20180101')
        #df_rs = dl.LoadTick('rb1805', '20180102', '20180201')
        df_rs = dl.LoadTick('data', '20180101', '20180301')
        #df_rs = dl.LoadTick('rb1805', '20180302', '20180329')

        #df_rs = dl.LoadTick('rb1810', '20180330', '20180501')

        # AP
        #######################################################
        #df_rs = dl.LoadTick('AP810', '20180201', '20180301')
        #df_rs = dl.LoadTick('AP810', '20180302', '20180401')
        #df_rs = dl.LoadTick('AP810', '20180402', '20180501')

        # rb1810
        #df_rs = dl.LoadTick('rb1810', '20180502', '20180502')

        N = len(df_rs)
        print N
        for i in range(N):
            tick = CtaTickData()
            tick.vtSymbol = 'rb0001'
            try:
                tick.datetime = df_rs['datetime'][i].to_pydatetime()
                tick.symbol = tick.vtSymbol
                #tick.exchange = df_rs['exchange'][i]
                tick.lastPrice = float(df_rs['last'][i])
                tick.openInterest = int(df_rs['dopenInterest'][i])
                tick.volume = int(df_rs['dVolume'][i])
                tick.amount = float(df_rs['dAmount'][i])
                tick.bidPrice1 = float(df_rs['bid1'][i])
                tick.askPrice1 = float(df_rs['ask1'][i])
                tick.bidVolume1 = int(df_rs['bidVolume1'][i])
                tick.askVolume1 = int(df_rs['askVolume1'][i])
                drEngine.insertData(TICK_DB_NAME, tick.vtSymbol, tick)
            except IndexError as e:
                print str(e)

    print 'done!'
