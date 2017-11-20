import matplotlib.pyplot as plt
import pandas as pd

if __name__ == '__main__':
    df1 = pd.read_csv('results/result1.csv', parse_dates='datetime', index_col='datetime',usecols=['datetime', 'bar1_close', 'wf_result'])
    df1 = df1.rename(columns={'bar1_close':'close', 'wf_result':'wfr_1min'})
    df5 = pd.read_csv('results/result5.csv', parse_dates='datetime', index_col='datetime',usecols=['datetime', 'wf_result'])
    df5 = df5.rename(columns={'wf_result':'wfr_5min'})
    df60 = pd.read_csv('results/result60.csv', parse_dates='datetime', index_col='datetime',usecols=['datetime', 'wf_result'])
    df60 = df60.rename(columns={'wf_result':'wfr_60min'})
    df = pd.concat([df1, df5, df60], axis=1).fillna(method='ffill')
    df1 = df5 = df60 = None
    fig1 = plt.subplot(211)
    fig1.plot(list(df['close']))
    fig2 = plt.subplot(212)
    fig2.plot(list(df['wfr_1min']))
    fig2.plot(list(df['wfr_5min']))
    fig2.plot(list(df['wfr_60min']))
    plt.show()