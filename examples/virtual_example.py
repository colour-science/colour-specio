import time

from specio.colorimeters import VirtualColorimeter
from specio.spectrometers import VirtualSpectrometer

# Virtual Spectrometer Example
print("=== Virtual Spectrometer Example ===")
vs = VirtualSpectrometer()

print(f"Device: {vs.manufacturer} {vs.model}")
print(f"Serial: {vs.serial_number}")

NUM_MEASUREMENTS = 3
print(f"Measuring {NUM_MEASUREMENTS} times...")

t1 = time.perf_counter()
for i in range(NUM_MEASUREMENTS):
    t = vs.measure()
    print(t)
    t2 = time.perf_counter()
    print(f"Running Average: {(t2 - t1) / (i + 1):.2f} seconds")
t2 = time.perf_counter()

print(f"Measured {NUM_MEASUREMENTS} times in {t2 - t1:.2f} seconds.")
print(f"Average time per measurement: {(t2 - t1) / NUM_MEASUREMENTS:.2f} seconds.")

print("\n=== Virtual Colorimeter Example ===")

# Virtual Colorimeter Example  
vc = VirtualColorimeter()

print(f"Device: {vc.manufacturer} {vc.model}")
print(f"Serial: {vc.serial_number}")

print(vc.measure())

print(f"Measuring {NUM_MEASUREMENTS} times...")

t1 = time.perf_counter()
for i in range(NUM_MEASUREMENTS):
    t = vc.measure()
    print(t)
    t2 = time.perf_counter()
    print(f"Running Average: {(t2 - t1) / (i + 1):.2f} seconds")
t2 = time.perf_counter()

print(f"Measured {NUM_MEASUREMENTS} times in {t2 - t1:.2f} seconds.")
print(f"Average time per measurement: {(t2 - t1) / NUM_MEASUREMENTS:.2f} seconds.")