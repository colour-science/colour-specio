from specio.measurement import SPDMeasurement
from specio.serialization.csmf import load_csmf_file, save_csmf_file

if __name__ == "__main__":
    measures = []
    for i in range(10):
        measures.append(SPDMeasurement())  # Generates random measurements

    file = "/Users/tucker/Downloads/test"  # Some file location

    ## File saving DOES NOT create folders
    save_csmf_file(file=file, measurements=measures)
    load_csmf_file(file=file)
