area = 0.7 * 0.4 # area of measuring tank 
x = 0.42 # level difference 
h = 0.1 # rise of water level
t = float(input("Enter the time required for 100mm rise: "))
q_act = (area*h)/t
print("Q_act: ",q_act, "m^3/s")

g = float(input("Enter the pressure gauge reading: "))*10
v = float(input("Enter the vacuum gauge reading: "))*13.6/1000
h = g+v+x
print("H: ", h, 'm')

w = 28 # eq weight of water 
bp = w*q_act*h # output power 
print("B.P.: ",bp,'kW')

T = float(input("Enter the time required for 10 pulses: "))
ip = (3600/1600)*(5/T)
print("I.P.: ",ip,'kW')

n = (bp/(ip))*100
print("n: ", n)