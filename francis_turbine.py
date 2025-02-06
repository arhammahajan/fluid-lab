import math
P_d = float(input("Enter the value of P_d: "))*10
P_s = float(input("Enter the value of P_s: "))*1.033/76
H = P_d + P_s
print("H: ", H)
A_p = (math.pi/4)*(0.08**2)
print("A_p: ", A_p)
A_t = (math.pi/4)*(0.045**2)
print("A_t: ", A_t)
R = float(input("Enter the value of R: "))
h = R*10.33
print("h: ", h)
Q = (0.97*A_p*A_t*math.sqrt(2*9.81*h))/math.sqrt(A_p**2 - A_t**2)
print("Q: ", Q)
E_i = (1000*9.81*Q*H)/1000
print("E_i: ", E_i)
W1 = float(input("Enter W1: "))
W2 = float(input("Enter W2: "))
R_e = (0.2 + 2*0.012)/2
T = (W1+0.094+0.093-W2)*9.81*R_e
print("T: ", T)
N = float(input("Enter the RPM(N): "))
E_o = (2*math.pi*N*T)/(60*1000)
print("E_o: ", E_o)
n = (E_o/E_i)*100
print("Efficiency: ", n)