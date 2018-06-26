import pandas as pd
from datetime import datetime

def main():
    df = pd.read_csv('results/trades.csv', parse_dates=['entryDt', 'exitDt'])
    df_vol = df['volume']
    df_entryDt = df['entryDt']
    df_exitDt = df['exitDt']
    df['Type'] = ['buy' if x>0 else 'sell' for x in df_vol]
    df['Open Time'] = [t.strftime('%Y.%m.%d %H:%M:%S') for t in df_entryDt]
    df['Close Time'] = [t.strftime('%Y.%m.%d %H:%M:%S') for t in df_exitDt]
    df['Volume'] = [abs(x) for x in df_vol]
    df['Symbol'] = 'RB'
    df['S/L'] = 0
    df['T/P'] = 0
    df['Close Price'] = df['exitPrice']
    df['Open Price'] = df['entryPrice']
    df['Commission'] = df['commission']
    df['Swap'] = 0
    df['Profit'] = df['pnl']
    df['Comment']= ''
    df['Magic']= ''
    df = df[['Open Time', 'Type', 'Volume', 'Symbol', 'Open Price', 'S/L', 'T/P', 'Close Time', 'Close Price', 'Commission', 'Swap', 'Profit', 'Comment', 'Magic']]
    print df
    df.to_csv('mt_trades.csv', index=False)

if __name__ == '__main__':
    main()