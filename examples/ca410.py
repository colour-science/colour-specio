import time

from specio.colorimeters import CA410

ca = CA410.discover()

print(ca.measure())

NUM_MEASUREMENTS = 3
print(f"Measuring {NUM_MEASUREMENTS} times...")

t1 = time.perf_counter()
for i in range(NUM_MEASUREMENTS):
    t = ca.measure()
    print(t)
    t2 = time.perf_counter()
    print(f"Running Average: {(t2 - t1) / (i + 1):.2f} seconds")
t2 = time.perf_counter()

print(f"Measured {NUM_MEASUREMENTS} times in {t2 - t1:.2f} seconds.")
print(f"Average time per measurement: {(t2 - t1) / NUM_MEASUREMENTS:.2f} seconds.")
print(f"Device firmware: {ca.firmware}")
