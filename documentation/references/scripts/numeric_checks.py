"""Recompute the plan's numerical claims from first principles (no downloaded data)."""
import numpy as np
from scipy.integrate import solve_ivp, quad

# --- Lane-Emden: xi_1 and rho_c / rho_mean for several n ---------------------------------
def lane_emden(n):
    def rhs(xi, y):
        theta, dtheta = y
        return [dtheta, -max(theta, 0.0) ** n - 2.0 * dtheta / xi]
    xi0 = 1e-6  # series start: theta = 1 - xi^2/6
    y0 = [1 - xi0**2 / 6, -xi0 / 3]
    surface = lambda xi, y: y[0]
    surface.terminal, surface.direction = True, -1
    sol = solve_ivp(rhs, [xi0, 50], y0, events=surface, rtol=1e-12, atol=1e-14, max_step=0.01)
    xi1 = sol.t_events[0][0]
    dtheta1 = sol.y_events[0][0][1]
    return xi1, dtheta1, -xi1 / (3 * dtheta1)

print("Lane-Emden (plan: n=1.5 xi1=3.65375 rho_c/rho_mean=5.99071; n=3 xi1=6.89685, 54.1825)")
for n in (0, 1, 1.5, 3):
    xi1, d1, conc = lane_emden(n)
    print(f"  n={n}: xi1={xi1:.5f}  theta'(xi1)={d1:.5f}  rho_c/rho_mean={conc:.5f}")
print(f"  exact n=0: xi1={np.sqrt(6):.5f}, conc=1; exact n=1: xi1={np.pi:.5f}, conc={np.pi**2/3:.5f}")

# --- Eddington standard model (n=3) central temperature for the Sun -----------------------
G, k_B, m_u = 6.674e-11, 1.380649e-23, 1.66054e-27
M, R = 1.989e30, 6.957e8
xi1, d1, conc = lane_emden(3)
rho_mean = M / (4 / 3 * np.pi * R**3)
rho_c = conc * rho_mean
P_c = G * M**2 / R**4 / (4 * np.pi * (3 + 1) * d1**2)
X, Y, Z = 0.70, 0.28, 0.02
mu = 1 / (2 * X + 0.75 * Y + 0.5 * Z)
T_c = mu * m_u * P_c / (k_B * rho_c)  # ideal gas, beta ~ 1
print(f"Eddington n=3 Sun: rho_c={rho_c:.3e} kg/m3, P_c={P_c:.3e} Pa, mu={mu:.3f}, T_c={T_c:.3e} K (plan: ~1.2e7 K)")

# --- Kroupa (2001) IMF: number share born above 8 Msun in 0.1-100 Msun ---------------------
def kroupa(m):
    return np.where(m < 0.5, m ** -1.3, 0.5 * m ** -2.3)  # continuous at 0.5 Msun
tot = quad(kroupa, 0.1, 0.5)[0] + quad(kroupa, 0.5, 100)[0]
above8 = quad(kroupa, 8, 100)[0]
print(f"Kroupa 0.1-100 Msun: share of stars born above 8 Msun = {100*above8/tot:.2f}% (plan: about 0.7%)")
mass_tot = quad(lambda m: m * kroupa(m), 0.1, 0.5)[0] + quad(lambda m: m * kroupa(m), 0.5, 100)[0]
n_above8_per_msun = above8 / mass_tot
print(f"  stars above 8 Msun per 1,000 Msun formed = {1000*n_above8_per_msun:.1f}")

# --- Gough (1981) luminosity evolution and the habitable-zone inner edge -------------------
t_sun = 4.57
def L_gough(t):
    return 1 / (1 + 0.4 * (1 - t / t_sun))
for dt in (0.5, 1.0, 1.5):
    L = L_gough(t_sun + dt)
    print(f"Gough L(t_sun+{dt} Gyr) = {L:.3f} Lsun")
print("Inner-edge distance d = sqrt(L / S_eff): see the second pass once Kopparapu's S_eff values are confirmed")

# --- Orbit widening after the Sun becomes a white dwarf (adiabatic: a * M = const) ---------
for m_wd in (0.52, 0.54, 0.56):
    print(f"Widening factor for a {m_wd} Msun white dwarf = {1/m_wd:.2f}")

# --- Sudden mass loss: circular orbit unbinds when more than half the mass is lost ---------
# bound if v^2 < 2 G (M - dM) / a with v^2 = G M / a  ->  dM < M / 2
print("Instant mass loss unbinds a circular orbit when dM > M/2 (energy argument)")
