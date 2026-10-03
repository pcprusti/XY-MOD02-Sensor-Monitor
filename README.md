# XY-MOD02-Sensor-Monitor

`xymod02.py` is a Tkinter application for monitoring temperature and relative humidity from an XY-MOD02 Modbus RTU sensor over a serial connection.

## Requirements

Use Python 3 with Tkinter enabled. Install the Python dependencies from the workspace root:

```bash
pip install -r requirements.txt
```

The monitor uses `pyserial` to list COM ports and `pymodbus==2.5.3` for Modbus RTU communication. Tkinter is included with most standard Python installations; on Windows, ensure Tcl/Tk support is selected in the Python installer.

## Start the Monitor

Run from the workspace root:

```bash
python xymod02.py
```

Select the sensor's COM port and Modbus slave address, then click **Connect**. Click **Refresh** to rescan available serial ports. Open **Settings** to change baud rate, data bits, parity, stop bits, or timeout. Settings take effect on the next connection.

Default serial settings are 9600 baud, 8 data bits, no parity, 1 stop bit, and a 1-second timeout. The default slave address is 1.

## Sensor Data

The monitor polls the sensor every two seconds and reads these input registers:

| Register | Measurement | Display conversion |
| --- | --- | --- |
| `0x0001` | Temperature | Register value divided by 10, shown in °C |
| `0x0002` | Relative humidity | Register value divided by 10, shown in % RH |

## Troubleshooting

- If no port is listed, connect the USB-to-serial adapter and click **Refresh**. Install its driver if Windows does not enumerate it.
- If connecting fails, make sure another application is not using the selected COM port.
- If the sensor does not respond, check the slave address and serial settings against the sensor configuration.
- Check the status line for connection errors. The readings remain as placeholders until a valid response is received.

