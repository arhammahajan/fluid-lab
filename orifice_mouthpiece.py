import math
T = float(input("Enter the time for 50mm rise: "))
Q_act = 0.00875/T
print("Q_act: ", Q_act)
A = (math.pi/4)*(0.017**2) # area of orifice 
H = float(input("Head over orifice: "))/1000
Q_th = A*math.sqrt((2*9.81*H))
print("Q_th: ", Q_th)
C_d = Q_act/Q_th
print("C_d: ", C_d)

X = float(input("Enter the horizontal distance: "))/100
Y = float(input("Enter the vertical distance: "))/100
C_v = X/math.sqrt(4*Y*H)
print("C_v: ", C_v)

C_c = C_d/C_v
print("C_c: ", C_c)