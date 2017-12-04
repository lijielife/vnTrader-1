import os
import os.path
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from scipy.ndimage.filters import gaussian_filter1d

HDF_DIR = 'd:/vn.trader/data/h5'

class DataLoader(object):
    def __init__(self,hdf_dir=HDF_DIR, date_format='%Y%m%d'):
        self.hdf_dir = hdf_dir
        self.date_format = date_format

    def LoadTick(self, symbol, start_date, end_date):
        files = self._searchFiles(start_date, end_date)
        return self._loadTick(symbol, files)
    
    def _searchFiles(self, start_date, end_date):
        files = []
        start_date = datetime.strptime(start_date, self.date_format)
        end_date = datetime.strptime(end_date, self.date_format)
        for parent, dirnames, filenames in os.walk(self.hdf_dir):
            print 'file'
            for filename in filenames:
                dt = filename.split('.')[0]
                if start_date <= datetime.strptime(dt, self.date_format) <= end_date:
                    files.append(filename)
        return files

    def _loadTick(self, symbol, files):
        df_rtn = pd.DataFrame()
        for f in files:
            filename = '/'.join([HDF_DIR, f])
            df = pd.read_hdf(filename, 'tick')
            
            try:
                df = df.loc[symbol]
                df_rtn = pd.concat([df_rtn, df])
                df = None
            except KeyError:
                print "%s not found" %symbol
                df = None
                del df
                
        return df_rtn
        

    def LoadBar(self, symbol, start_date, end_date, bin='1min'):
        files = self._searchFiles(start_date, end_date)
        print files
        df = pd.DataFrame()
        for f in files:
            df_tick = self._loadTick(symbol, [f])
            try:
                Vol = df_tick['Volume']
                start_vol = Vol[0]
                dVol = Vol.diff()
                dVol[0] = start_vol

                dVol.rename('dVol', inplace=True)
                df_tick = pd.concat([df_tick, dVol], axis=1)
                df_tick = df_tick.loc[:, ['lastPrice','dVol']].dropna()
                # resample
                df_ohlc = df_tick['lastPrice'].resample(bin).ohlc()
                df_vol = df_tick['dVol'].resample(bin, label='right').sum()
                df_append = pd.concat([df_ohlc, df_vol], axis=1)
                df = pd.concat([df, df_append])
            except KeyError:
                pass
        return df.dropna()
        

if __name__ == '__main__':
    dl = DataLoader()

    df_rs = dl.LoadBar('rb1705', '20161230', '20161230', bin='1min')
    print df_rs
    # plt.figure()
    # fig1 = plt.subplot(211)
    # fig1.plot(list(df_rs['close']))
    # fig2 = plt.subplot(212)
    # blurred = gaussian_filter1d(list(df_rs['dVol']), 3.0)
    # fig2.plot(blurred)
    # blurred_rt = []
    # for i in range(len(df_rs['dVol'])):
    #     b = gaussian_filter1d(list(df_rs['dVol'])[:i+1], 2.0)
    #     blurred_rt.append(b[-1])
    # fig2.plot(list(df_rs['dVol']))
    # fig2.plot(blurred_rt)
    # plt.show()
    


