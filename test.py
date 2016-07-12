import Get_Alignment
import matplotlib.pyplot as plt

p = Get_Alignment.parse_vline('/home/ryan/scrap/vline-eV.dat')

plt.plot(p['z'], p['V']['short_range'])
plt.show()

pass