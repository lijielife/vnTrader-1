
from datetime import datetime, timedelta

import pandas as pd

import vtPath
from ctaBase import *
from ctaStrategy import ctaEngine2
from data.loader import DataLoader
from gateway import GATEWAY_DICT
from vtEngine import MainEngine

if __name__ == '__main__':
    mainEngine = MainEngine()
    mainEngine.dbConnect()
    drEngine = mainEngine.drEngine
    drEngine.loadSetting()
    dl = DataLoader()
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
    df_rs = dl.LoadBar('ru1705', '20161128', '20170101', bin='1min')
    
    dict_rs = df_rs.to_dict(orient='split')
    df_rs = None
    N = len(dict_rs['data'])

    for i in range(N):
        bar = CtaBarData()
        bar.vtSymbol = 'ru9999'
        bar.datetime = dict_rs['index'][i].to_pydatetime()
        data = dict_rs['data'][i]
        bar.open = data[0]
        bar.high = data[1]
        bar.low = data[2]
        bar.close = data[3]
        bar.volume = data[4]
        drEngine.insertData(MINUTE_DB_NAME, bar.vtSymbol, bar)
        print 'insert bar'
    print 'done!'
