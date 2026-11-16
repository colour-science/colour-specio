"""
Colorimetry Research colorimeter implementation.
"""

from __future__ import annotations

import re
from typing import final

import bidict
import numpy as np

from specio.common.colorimeters import Colorimeter, RawColorimeterMeasurement
from specio.common.utility import specio_warning

from ._common import (
    CRDeviceBase,
    InstrumentType,
)


@final
class CRColorimeter(CRDeviceBase, Colorimeter):
    """Interface with a Colorimetry Research colorimeter, such as the CR-100 or CR-120.

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
    def discover(
        cls, expected_instrument_type: InstrumentType | None = None
    ) -> CRColorimeter:
        """Attempt automatic discovery of the CR serial port and return the
        CR colorimeter object.

        Parameters
        ----------
        expected_instrument_type : InstrumentType | None, optional
            The expected instrument type, defaults to COLORIMETER.

        Returns
        -------
        CRColorimeter
            A successfully discovered CR colorimeter object.

        Raises
        ------
        serial.SerialException
            If no serial port can be automatically linked.
        """
        if expected_instrument_type is None:
            expected_instrument_type = InstrumentType(1)
        return super().discover(expected_instrument_type=expected_instrument_type)

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
            rows = [
                (arg.decode() if isinstance(arg, bytes) else arg).strip()
                for arg in response.arguments
            ]
            # The header line ends in the row count. The parser reads the rows
            # only if they are already waiting, so a slow reply leaves the bare
            # count here; read that many rows now. A device with no filters,
            # such as a CR-100, reports a count of 0 and no rows.
            if len(rows) == 1 and rows[0].isdigit():
                count = int(rows[0])
                rows = [self._port.readline().decode().strip() for _ in range(count)]
            # A row is `ID,name,type`, such as `1,ND-120-1.3,Radiance`; RS
            # Filter reports a selected filter by its name alone.
            filters = bidict.bidict()
            for row in rows:
                fields = row.split(",")
                filters[int(fields[0])] = fields[1]
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
            raise RuntimeError("CR-100/120 only supports up to 3 filter selections!")
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
        # current_filters always has one entry per filter slot (Filter1-3), so
        # count only the slots that actually have a filter selected (id != 0/"None").
        active = [f for f in cur if f != 0]
        if len(active) == 0:
            specio_warning("Check colorimeter has no active filters.")
        elif len(active) == 1:
            specio_warning(
                f"Check colorimeter has one filter: {self.available_filters[active[0]]}"
            )
        else:
            filters_string = ", ".join([self.available_filters[f] for f in active])
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

        samples = self._samples_for_timeout()
        self._port.apply_settings({"timeout": 10 + 0.5 * samples})
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
