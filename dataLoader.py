
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
    df_rs = dl.LoadBar('rb1705', '20160501', '20161230', bin='1min')
    dict_rs = df_rs.to_dict(orient='split')
    df_rs = None
    N = len(dict_rs['data'])

    for i in range(N):
        bar = CtaBarData()
        bar.vtSymbol = 'rb1705'
        bar.datetime = dict_rs['index'][i].to_pydatetime()
        data = dict_rs['data'][i]
        bar.open = data[0]
        bar.high = data[1]
        bar.low = data[2]
        bar.close = data[3]
        bar.volume = data[4]
        drEngine.insertData(MINUTE_DB_NAME, bar.vtSymbol, bar)
        print 'insert bar'
