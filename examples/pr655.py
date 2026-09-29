import time

from specio.spectrometers import PRSpectrometer

with PRSpectrometer.discover() as pr:
    pr.exposure = PRSpectrometer.ADAPTIVE_EXPOSURE
    pr.average_samples = 3

    NUM_MEASUREMENTS = 3
    print(f"Measuring {NUM_MEASUREMENTS} times...")

    t1 = time.perf_counter()
    for i in range(NUM_MEASUREMENTS):
        t = pr.measure()
        print(t)
        print(f"Exposure: {t.exposure:.3f} seconds")
        t2 = time.perf_counter()
        print(f"Running Average: {(t2 - t1) / (i + 1):.2f} seconds")
    t2 = time.perf_counter()

    print(f"Measured {NUM_MEASUREMENTS} times in {t2 - t1:.2f} seconds.")
    print(f"Average time per measurement: {(t2 - t1) / NUM_MEASUREMENTS:.2f} seconds.")
    print(f"Device: {pr.readable_id}")
