"""
Colorimetry Research colorimeter implementation.
"""

import re
from typing import cast, final

import bidict
import numpy as np

from specio.common.colorimeters import Colorimeter, RawColorimeterMeasurement
from specio.common.utility import specio_warning

from ._common import CRDeviceBase, InstrumentType


@final
class CRColorimeter(CRDeviceBase, Colorimeter):
    """Interface with a colorimetry research brand CR-250 or CR-300 in colorimeter mode.

    Implements the `specio.colorimeters.Colorimeter` interface for direct XYZ measurements.

    Raises
    ------
    serial.SerialException
        if `CRColorimeter.discover` fails or there are other serial port issues.
    CommandError
        A error was encountered in parsing the result of the serial command to
        the hardware device.
    """

    @classmethod
    def discover(cls) -> "CRColorimeter":
        """Attempt automatic discovery of the CR serial port and return the
        CR colorimeter object.

        Returns
        -------
        CRColorimeter
            A successfully discovered CR colorimeter object.

        Raises
        ------
        serial.SerialException
            If no serial port can be automatically linked.
        """
        return super().discover(expected_instrument_type=InstrumentType.COLORIMETER)

    def __init__(
        self,
        port: str,
    ) -> None:
        """
        Initialize a CR colorimeter controller.

        Parameters
        ----------
        port : str
            The serial port device path (e.g., '/dev/ttyUSB0', 'COM3').

        Raises
        ------
        serial.SerialException
            If the serial port cannot be opened or configured.
        """
        super().__init__(port)
        self._warn_filter_selection()

    @property
    def available_filters(self) -> bidict.bidict[int, str]:
        """
        Get the mapping of available optical filters for the colorimeter.

        Returns
        -------
        bidict.bidict[int, str]
            Bidirectional dictionary mapping filter IDs to filter names.
            ID 0 always maps to "None" for no filter selection.

        Raises
        ------
        CommandError
            If the filter query command fails.
        """
        if not hasattr(self, "_available_filters"):
            response = self._write_cmd("RC Filter")
            filters = bidict.bidict()
            for arg in response.arguments:
                arg = cast("bytes", arg)
                items = arg.decode().strip().split(",")
                filters[int(items[0])] = items[1]
            filters[0] = "None"
            self._available_filters = filters
        return self._available_filters

    @property
    def current_filters(self) -> tuple[int, int, int]:
        """
        Get the currently selected filter IDs for all three filter positions.

        Returns
        -------
        tuple[int, int, int]
            Tuple of three filter IDs representing the current filter selection
            for positions 1, 2, and 3.

        Raises
        ------
        CommandError
            If the filter status query command fails.
        """
        response = self._write_cmd("RS Filter")
        arguments = response.arguments[0].split(",")

        out = []
        for f in arguments:
            out += [self.available_filters.inverse[f]]
        return tuple(out)

    @current_filters.setter
    def current_filters(self, filters: tuple[int, ...]) -> None:
        """
        Set the current filter selection for all three filter positions.

        Parameters
        ----------
        filters : tuple[int, ...]
            Tuple of filter IDs to set. Maximum 3 filters supported.
            Use -1 or omit positions to deselect filters.

        Raises
        ------
        RuntimeError
            If more than 3 filters are specified.
        CommandError
            If any filter setting command fails.
        """
        if len(filters) > 3:
            raise RuntimeError("CR-100/120 only supports up to 3 filter selectons!")
        for i in range(1, 4):
            cur_filter_id = filters[i - 1] if i <= len(filters) else -1
            self._write_cmd(f"SM Filter{i:.0f} {cur_filter_id:.0f}")

        self._warn_filter_selection()

    @property
    def current_filters_names(self) -> tuple[str, str, str]:
        """
        Get the names of the currently selected filters.

        Returns
        -------
        tuple[str, str, str]
            Tuple of three filter names corresponding to the current filter selection.

        Raises
        ------
        CommandError
            If the filter status query command fails.
        """
        # ignore type error. Cannot interpret list builder size.
        return tuple([self.available_filters[k] for k in self.current_filters])  # type: ignore

    def _warn_filter_selection(self) -> None:
        """
        Issue warnings about the current filter configuration.

        Emits warnings when no filters are selected, only one filter is selected,
        or multiple filters are stacked, as these configurations may affect
        measurement accuracy and should be verified by the user.
        """
        cur = self.current_filters
        if len(cur) == 0:
            specio_warning("Check colorimeter has no active filters.")
        elif len(cur) == 1:
            specio_warning(
                f"Check colorimeter has one filter: {self.available_filters[cur[0]]}"
            )
        else:
            filters_string = ", ".join([self.available_filters[f] for f in cur])
            specio_warning(f"Check colorimeter has stacked filters: {filters_string}.")

    def _raw_measure(self) -> RawColorimeterMeasurement:
        """
        Perform a colorimetric measurement and return raw XYZ values.

        Returns
        -------
        RawColorimeterMeasurement
            Raw measurement data containing XYZ values, device ID, and exposure time.

        Raises
        ------
        CommandError
            If the measurement command fails or times out.
        """
        t = self._port.timeout

        self._port.apply_settings({"timeout": 10 + 0.5 * self.average_samples})
        response = self._write_cmd("M")

        self._port.apply_settings({"timeout": 0.21})
        response = self._write_cmd("RM XYZ")

        XYZ = np.asarray([float(s) for s in response.arguments[0].split(",")])

        exposure = self._write_cmd("RM Exposure").arguments[0]
        exMatch = re.match(r"\d*\.?\d*", exposure)
        exposure = float(exMatch.group()) / 1000 if exMatch else -1

        self._port.apply_settings({"timeout": t})

        return RawColorimeterMeasurement(
            XYZ=XYZ,
            device_id=self.readable_id,
            exposure=exposure,
        )
