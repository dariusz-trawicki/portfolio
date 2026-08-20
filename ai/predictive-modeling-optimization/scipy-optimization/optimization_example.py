"""
SciPy Optimization Examples
"""
import numpy as np
from scipy.optimize import minimize, linprog
import matplotlib.pyplot as plt

print("=" * 50)
print("EXAMPLE 1: Nonlinear Optimization")
print("=" * 50)

# Objective function: f(x, y) = x^2 + y^2 + xy
def objective(x):
    return x[0]**2 + x[1]**2 + x[0]*x[1]

# Starting point
x0 = [2, 2]

# Optimization using BFGS method
result = minimize(objective, x0, method='BFGS')

print(f"\nStarting point: {x0}")
print(f"Found minimum: {result.x}")
print(f"Function value at minimum: {result.fun:.6f}")
print(f"Success: {result.success}")
print(f"Number of iterations: {result.nit}")

# Visualization
x_range = np.linspace(-3, 3, 100)
y_range = np.linspace(-3, 3, 100)
X, Y = np.meshgrid(x_range, y_range)
Z = X**2 + Y**2 + X*Y

plt.figure(figsize=(10, 8))
plt.contour(X, Y, Z, levels=20, cmap='viridis')
plt.colorbar(label='Function value')
plt.plot(x0[0], x0[1], 'ro', markersize=10, label='Start')
plt.plot(result.x[0], result.x[1], 'r*', markersize=15, label='Minimum')
plt.xlabel('x')
plt.ylabel('y')
plt.title('Nonlinear Optimization - f(x,y) = x² + y² + xy')
plt.legend()
plt.grid(True)
plt.savefig('optimization_plot1.png', dpi=150, bbox_inches='tight')
print("\n✅ Plot saved as 'optimization_plot1.png'")

print("\n" + "=" * 50)
print("EXAMPLE 2: Linear Programming")
print("=" * 50)

# Minimize: -x - 2y (i.e., maximize: x + 2y)
# Subject to:
#   2x + y <= 20
#   -4x + 5y <= 10
#   x >= 0, y >= 0

c = [-1, -2]  # Objective function coefficients (negative for minimize)
A_ub = [[2, 1], [-4, 5]]  # Inequality constraint matrix
b_ub = [20, 10]  # Right-hand side of inequalities

print("\nProblem:")
print("  max: x + 2y")
print("  s.t.:")
print("       2x + y <= 20")
print("       -4x + 5y <= 10")
print("       x, y >= 0")

result_lp = linprog(c, A_ub=A_ub, b_ub=b_ub, method='highs')

print(f"\nOptimal solution: x = {result_lp.x[0]:.2f}, y = {result_lp.x[1]:.2f}")
print(f"Maximum value: {-result_lp.fun:.2f}")
print(f"Status: {result_lp.message}")

# LP Visualization
plt.figure(figsize=(10, 8))

# Constraints
x = np.linspace(0, 12, 400)
y1 = 20 - 2*x  # 2x + y = 20
y2 = (10 + 4*x) / 5  # -4x + 5y = 10

plt.plot(x, y1, label='2x + y = 20', linewidth=2)
plt.plot(x, y2, label='-4x + 5y = 10', linewidth=2)
plt.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
plt.axvline(x=0, color='k', linestyle='-', linewidth=0.5)

# Feasible region
y1_fill = np.minimum(y1, 20)
y2_fill = np.maximum(y2, 0)
y_fill = np.minimum(y1_fill, y2_fill)
y_fill = np.maximum(y_fill, 0)
plt.fill_between(x, 0, y_fill, where=(y_fill >= 0) & (x >= 0), 
                  alpha=0.3, color='green', label='Feasible region')

# Points
plt.plot(result_lp.x[0], result_lp.x[1], 'r*', markersize=20, 
         label=f'Optimum ({result_lp.x[0]:.2f}, {result_lp.x[1]:.2f})')

plt.xlim(0, 12)
plt.ylim(0, 12)
plt.xlabel('x', fontsize=12)
plt.ylabel('y', fontsize=12)
plt.title('Linear Programming - max(x + 2y)', fontsize=14)
plt.legend(fontsize=10)
plt.grid(True, alpha=0.3)
plt.savefig('optimization_plot2.png', dpi=150, bbox_inches='tight')
print("\n✅ Plot saved as 'optimization_plot2.png'")

print("\n" + "=" * 50)
print("EXAMPLE 3: Rosenbrock Function (benchmark)")
print("=" * 50)

def rosenbrock(x):
    """Classic test function - difficult to optimize"""
    return (1 - x[0])**2 + 100*(x[1] - x[0]**2)**2

# Different starting points
starting_points = [
    [-1.2, 1.0],
    [0.0, 0.0],
    [2.0, 2.0]
]

print("\nOptimization from different starting points:")
for i, x0 in enumerate(starting_points, 1):
    result = minimize(rosenbrock, x0, method='BFGS')
    print(f"\n  Start {i}: {x0}")
    print(f"  End: [{result.x[0]:.6f}, {result.x[1]:.6f}]")
    print(f"  Value: {result.fun:.10f}")
    print(f"  Iterations: {result.nit}")

print("\n" + "=" * 50)
print("DONE! 🎉")
print("=" * 50)
