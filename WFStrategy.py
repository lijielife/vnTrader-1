import pandas as pd
import matplotlib.pyplot as plt
if __name__ == '__main__':
    df_1min = pd.read_csv('result1.csv', parse_dates=True, index_col=['datetime'], usecols=[1,2,3])
    df_5min = pd.read_csv('result5.csv', parse_dates=True, index_col=['datetime'], usecols=[1,2])
    df_60min = pd.read_csv('result60.csv', parse_dates=True, index_col=['datetime'], usecols=[1,2])
    df = pd.concat([df_1min, df_5min, df_60min], axis=1)
    df = df.fillna(method='ffill')
    print df
    figure1 = plt.subplot(211)
    figure1.plot(list(df['bar1_close']))
    figure2 = plt.subplot(212)
    figure2.plot(list(df['wf_result_60']))
    plt.show()
    #plt.plot(list(df_1min['wf_result_0']))
    #plt.show()
    #print df_1min