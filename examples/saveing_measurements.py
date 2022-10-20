from specio.common import Measurement
from specio.fileio import load_measurements, save_measurements


if __name__ == "__main__":
    measures = []
    for i in range(10):
        measures.append(Measurement())  # Generates random measurements

    file = "/Users/tucker/Downloads/test"  # Some file location

    ## File saving DOES NOT create folders
    save_measurements(file=file, measurements=measures)
    load_measurements(file=file)
