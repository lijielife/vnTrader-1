from my_module.particle_filter import ParticleFilter
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PARTICLE_NUM = 500
X_min = 1000
X_max = 3000
dX_min = -50.0
dX_max = 50.0

motion_noise = 2.0
sense_noise = 10.0

def main():
    df = pd.read_csv('data.csv')
    data = df['close']*1.0
    filtered = []
    pf = ParticleFilter(PARTICLE_NUM)
    pf.PF_Init(motion_noise, sense_noise, X_min, X_max, dX_min, dX_max)
    
    for point in data:
        result = pf.Calculate(point)[0]
        filtered.append(result)
    df['filtered'] = filtered
    df.to_csv('pf_result.csv')
    #print filtered
    plt.plot(data)
    plt.plot(filtered)
    plt.show()



if __name__ == '__main__':
    main()
    
