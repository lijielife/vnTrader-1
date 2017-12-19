import pandas as pd
import matplotlib.pyplot as plt
if __name__ == '__main__':
    df = pd.read_csv('results/data.csv')
    close = list(df['close'])
    index = list(df['trend_index'])

    fig1 = plt.subplot(211)
    fig1.plot(close)

    fig2 = plt.subplot(212)
    fig2.plot(index)

    plt.show()