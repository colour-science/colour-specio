"""
Photo Research spectrometer implementation.
"""

import logging
import time
from dataclasses import dataclass
from typing import final

from colour import SpectralDistribution, SpectralShape

from specio.common import RawSPDMeasurement, SpecRadiometer

from ._common import PRCommandError, PRCommandResponse, PRDeviceBase, PRResponseCode

_MEASUREMENT_TIMEOUT = 60.0


@dataclass
class PRModelConfig:
    """
    Spectral configuration for a specific Photo Research model.

    Parameters
    ----------
    start_nm : int
        Start wavelength in nanometers.
    end_nm : int
        End wavelength in nanometers.
    interval_nm : int
        Wavelength interval in nanometers.
    num_points : int
        Number of spectral data points.
    min_exposure_ms : int
        Minimum fixed exposure time in milliseconds.
    max_exposure_ms : int
        Maximum fixed exposure time in milliseconds.
    """

    start_nm: int
    end_nm: int
    interval_nm: int
    num_points: int
    min_exposure_ms: int
    max_exposure_ms: int


_MODEL_CONFIGS: dict[str, PRModelConfig] = {
    "PR-655": PRModelConfig(380, 780, 4, 101, 3, 6000),
    "PR-670": PRModelConfig(380, 780, 2, 201, 6, 30000),
}

_DEFAULT_CONFIG = PRModelConfig(380, 780, 4, 101, 3, 6000)

_MAX_AVERAGING_SAMPLES = 99


@final
class PRSpectrometer(PRDeviceBase, SpecRadiometer):
    """
    Interface with a Photo Research SpectraScan PR-655 spectroradiometer.

    Implements the `specio.common.SpecRadiometer` interface for the
    Photo Research PR-655 (and compatible PR-6xx models).

    Raises
    ------
    serial.SerialException
        If discovery fails or there are serial port issues.
    PRCommandError
        If a command to the hardware device returns an error.
    """

    @property
    def _config(self) -> PRModelConfig:
        """
        Get the spectral configuration for the connected model.

        Returns
        -------
        PRModelConfig
            Spectral configuration matching the device model.
        """
        return _MODEL_CONFIGS.get(self.model, _DEFAULT_CONFIG)

    @property
    def exposure(self) -> str:
        """
        Get the current exposure (integration) time setting.

        Returns the human-readable exposure string from the device
        configuration. Field 6 of the D602 response contains the mode
        ("Adaptive" or "Fixed") and field 7 contains the time value
        (e.g., "50 ms"). When in adaptive mode, returns "Adaptive".

        Returns
        -------
        str
            Exposure time description from the device (e.g., "Adaptive",
            "50 ms").

        Raises
        ------
        PRCommandError
            If the configuration query fails.
        """
        response = self._write_cmd("D602")
        parts = response.raw_data.split(",")
        if len(parts) >= 8:
            mode = parts[6].strip()
            if mode == "Adaptive":
                return "Adaptive"
            return parts[7].strip()
        return "unknown"

    @exposure.setter
    def exposure(self, ms: int) -> None:
        """
        Set the detector exposure (integration) time.

        Sends the ``SE`` command. Use ``0`` for adaptive exposure, or a
        value in milliseconds for a fixed exposure time.

        Parameters
        ----------
        ms : int
            Exposure time in milliseconds. ``0`` selects adaptive mode.
            Positive values are clamped to the model's supported range
            (e.g. 3-6000 ms for the PR-655, 6-30000 ms for the PR-670).

        Raises
        ------
        PRCommandError
            If the setup command fails.
        """
        config = self._config
        if ms != 0:
            ms = max(config.min_exposure_ms, min(ms, config.max_exposure_ms))
        self._write_cmd(f"SE{ms:d}")

    @property
    def averaging_samples(self) -> int:
        """
        Get the number of measurement cycles averaged per reading.

        Returns
        -------
        int
            Number of averaged cycles.

        Raises
        ------
        PRCommandError
            If the configuration query fails.
        """
        response = self._write_cmd("D602")
        parts = response.raw_data.split(",")
        # Cycles is the 10th field (e.g., "2 cycles")
        if len(parts) >= 10:
            cycles_str = parts[9].strip().split()[0]
            try:
                return int(cycles_str)
            except ValueError:
                return 1
        return 1

    @averaging_samples.setter
    def averaging_samples(self, count: int) -> None:
        """
        Set the number of measurement cycles to average per reading.

        Sends the ``SN`` command.

        Parameters
        ----------
        count : int
            Number of measurements to average, clamped to 1-99.

        Raises
        ------
        PRCommandError
            If the setup command fails.
        """
        count = max(1, min(count, _MAX_AVERAGING_SAMPLES))
        self._write_cmd(f"SN{count:d}")

    def _raw_measure(self) -> RawSPDMeasurement:
        """
        Perform a spectral measurement and return raw spectral data.

        Triggers a measurement (M0 — measure and hold), then retrieves
        spectral data (D5). The D5 response is 101 lines of
        ``wavelength,power`` pairs for the PR-655 (380-780nm at 4nm
        intervals).

        Returns
        -------
        RawSPDMeasurement
            Raw measurement data containing spectral power distribution,
            spectrometer ID, and exposure time.

        Raises
        ------
        PRCommandError
            If the measurement or data retrieval command fails.
        """
        log = logging.getLogger("specio.PR")
        config = self._config
        original_timeout = self._port.timeout

        # Trigger measurement with extended timeout
        log.debug("Triggering spectral measurement (M0)")
        self._port.reset_input_buffer()
        self._write_serial("M0\r")
        self._last_cmd_time = time.time()

        measure_response = self._read_response(timeout=_MEASUREMENT_TIMEOUT)

        # Parse M0 response (status code only, no inline data)
        parsed = self._parse_response(measure_response)
        if parsed.code != PRResponseCode.OK:
            self._port.apply_settings({"timeout": original_timeout})
            raise PRCommandError(
                PRCommandResponse(
                    code=parsed.code,
                    raw_data=measure_response,
                ),
                f"Measurement failed: {measure_response}",
            )

        # Retrieve spectral data — D5 returns data lines directly
        log.debug("Retrieving spectral data (D5)")
        self._write_serial("D5\r")
        self._last_cmd_time = time.time()

        # Read all spectral data lines
        powers: list[float] = []
        for _ in range(config.num_points):
            line = self._read_response(timeout=2.0)
            parts = line.split(",")
            if len(parts) >= 2:
                powers.append(float(parts[1]))
            elif line:
                powers.append(float(line))

        self._port.apply_settings({"timeout": original_timeout})

        shape = SpectralShape(config.start_nm, config.end_nm, config.interval_nm)
        spd = SpectralDistribution(data=powers, domain=shape)

        log.debug("Measurement complete: %d spectral points", len(powers))

        return RawSPDMeasurement(
            spd=spd,
            spectrometer_id=self.readable_id,
            exposure=-1.0,
        )
