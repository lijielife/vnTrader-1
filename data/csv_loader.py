import os
import os.path
import pandas as pd
#import matplotlib.pyplot as plt
from datetime import datetime
#from scipy.ndimage.filters import gaussian_filter1d

CSV_DIR = 'F:\\tempdata'

class DataLoader(object):
    def __init__(self,csv_dir=CSV_DIR, date_format='%Y%m%d'):
        self.csv_dir = csv_dir
        self.date_format = date_format

    def LoadTick(self, symbol, start_date, end_date):
        files = self._searchFiles(symbol, start_date, end_date)
        return self._loadTick(symbol, files)

    

    def _searchFiles(self, symbol, start_date,end_date):
        dt_format = self.date_format
        def _filter_functor(full_filename):
            filename = full_filename.split('\\')[-1]
            fn_s = filename.split('.')[0]
            s,dt = fn_s.split('_')
            s_date = datetime.strptime(start_date, dt_format)
            e_date = datetime.strptime(end_date, dt_format)
            date = datetime.strptime(dt, dt_format)
            return symbol == s and s_date <= date <= e_date
        files = []
        for parent, dirnames, filenames in os.walk(self.csv_dir):
            full_filenames = map(lambda x:'\\'.join([parent, x]), filenames)
            files += full_filenames
        
        files_filtered = filter(_filter_functor, files)
        
        return files_filtered

    def _loadTick(self, symbol, files):
        df_rtn = pd.DataFrame()
        for f in files:
            print 'file'
            filename = f
            df = pd.read_csv(filename, parse_dates=[0], index_col=0, keep_date_col=True)
            print "load data completed"
            #df = pd.read_csv(filename, parse_dates=[2], index_col=2, keep_date_col=True, encoding='gbk')
            datetime = df.index
            df.insert(0, 'datetime', datetime)
            try:
                df_rtn = pd.concat([df_rtn, df])
                df = None
            except KeyError:
                print "%s not found" %symbol
                df = None
                del df
        
        
        
        df_rtn.columns = ['datetime', 'last', 'bid1', 'ask1', 'bidVolume1', 'askVolume1', 'dVolume', 'dAmount', 'dopenInterest']
        #                  0           1           2      3        4            5           6         7         8                            
        return df_rtn
        

    def LoadBar(self, symbol, start_date, end_date, bin='1min'):
        files = self._searchFiles(symbol, start_date, end_date)
        print files
        df = pd.DataFrame()
        for f in files:
            df_tick = self._loadTick(symbol, [f])
            try:
                # Vol = df_tick['Volume']
                # start_vol = Vol[0]
                # dVol = Vol.diff()
                # dVol[0] = start_vol

                # dVol.rename('dVol', inplace=True)
                # df_tick = pd.concat([df_tick, dVol], axis=1)
                # df_tick = df_tick.loc[:, ['lastPrice','dVol']].dropna()
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
    # files = dl._searchFiles('au1806','20180101', '20180501')
    # print len(files)
    # print 'pass'
    # df = dl._loadTick('au1806', files)
    # print df.head(5)
    # print 'pass'
    
    df_rs = dl.LoadTick('data', '20180101', '20180501')
    #df_rs = dl.LoadBar('au1806', '20180101', '20180501','1min')
    #print df_rs.head(5)
    print 'pass'
