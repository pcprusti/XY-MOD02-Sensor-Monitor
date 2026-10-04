#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Display temperature and humidity from an XYMD02 Modbus RTU sensor."""

import queue
import threading
import tkinter as tk
from tkinter import ttk

from pymodbus.client import ModbusSerialClient as ModbusClient
from pymodbus.framer import FramerType
from serial.tools import list_ports


baudrate = 9600
stopbits = 1
bytesize = 8
parity = "N"
timeout = 1
retries = 2


class XYMD02:
    """Access measurement and configuration registers on an XY-MOD02 sensor."""

    def __init__(self, DeviceAddress, client):
        """Bind the Modbus client to the sensor's slave address."""
        self.DeviceAddress = DeviceAddress
        self.client = client

    def _read_register(self, address):
        """Read one input register and convert its tenths-scaled value."""
        response = self.client.read_input_registers(
            address=address, count=1, device_id=self.DeviceAddress
        )
        if response.isError() or not response.registers:
            raise IOError("Sensor returned an invalid Modbus response")
        return response.registers[0] / 10.0

    def _read_holding_register(self, address):
        """Read one unscaled holding register from the sensor."""
        response = self.client.read_holding_registers(
            address=address, count=1, device_id=self.DeviceAddress
        )
        if response.isError() or not response.registers:
            raise IOError("Sensor returned an invalid Modbus response")
        return response.registers[0]

    def ReadTemp(self):
        """Return the measured temperature in degrees Celsius."""
        return self._read_register(0x0001)

    def ReadHumidity(self):
        """Return the measured relative humidity as a percentage."""
        return self._read_register(0x0002)

    def ReadDeviceAdress(self):
        """Return the sensor's configured Modbus slave address."""
        return self._read_holding_register(0x0101)

    def ReadBaudRate(self):
        """Return the sensor's configured baud-rate code."""
        return self._read_holding_register(0x0102)

    def ReadTemperatureCorrection(self):
        """Return the configured temperature correction value."""
        return self._read_holding_register(0x0103)

    def ReadHumidityCorrection(self):
        """Return the configured humidity correction value."""
        return self._read_holding_register(0x0104)

    def WriteDeviceAdress(self, NewDeviceAddress):
        """Write a new slave address to the sensor's address register."""
        return self.client.write_register(
            address=0x0101,
            value=NewDeviceAddress,
            device_id=self.DeviceAddress,
        )


class SensorApp:
    """Build and manage the Tkinter sensor monitor window."""

    def __init__(self, root):
        """Initialize the window, controls, and background event polling."""
        self.root = root
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.last_error = None
        self.serial_settings = {
            "baudrate": baudrate,
            "bytesize": bytesize,
            "parity": parity,
            "stopbits": stopbits,
            "timeout": timeout,
        }

        self.root.title("XY-MOD02 Sensor Monitor")
        self.root.geometry("500x390")
        self.root.minsize(440, 360)
        self.root.configure(background="#f2f5f4")
        self._configure_styles()
        self._build_ui()
        self.refresh_ports()
        self.root.after(100, self._process_events)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _configure_styles(self):
        """Configure the ttk styles used throughout the monitor window."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f5f4")
        style.configure("TLabel", background="#f2f5f4", foreground="#20312f")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#61716e")
        style.configure("Reading.TLabel", font=("Segoe UI", 30, "bold"), foreground="#173f3a")
        style.configure("Unit.TLabel", font=("Segoe UI", 12), foreground="#61716e")
        style.configure(
            "Status.TLabel",
            font=("Segoe UI", 9),
            foreground="#526360",
            background="#f2f5f4",
            padding=(0, 4),
        )
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("TCombobox", padding=5)
        style.configure("TSpinbox", padding=5)

    def _build_ui(self):
        """Create the serial controls, measurement panels, and status line."""
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)

        heading = ttk.Frame(outer)
        heading.pack(fill="x")
        ttk.Label(heading, text="XY-MOD02 Monitor", style="Title.TLabel").pack(side="left")
        self.settings_button = ttk.Button(
            heading, text="Settings", command=self.open_settings
        )
        self.settings_button.pack(side="right")
        self.connection_summary = tk.StringVar()
        ttk.Label(
            outer, textvariable=self.connection_summary, style="Subtitle.TLabel"
        ).pack(anchor="w", pady=(3, 18))
        self._update_connection_summary()

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 20))
        ttk.Label(controls, text="COM port").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="Slave address").grid(row=0, column=1, sticky="w", padx=(12, 0))

        self.port_var = tk.StringVar()
        port_controls = ttk.Frame(controls)
        port_controls.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        port_controls.columnconfigure(0, weight=1)
        self.port_box = ttk.Combobox(
            port_controls, textvariable=self.port_var, state="readonly", width=18
        )
        self.port_box.grid(row=0, column=0, sticky="ew")
        self.refresh_button = ttk.Button(port_controls, text="Refresh", command=self.refresh_ports)
        self.refresh_button.grid(row=0, column=1, padx=(6, 0))

        self.slave_var = tk.IntVar(value=1)
        self.slave_box = ttk.Spinbox(
            controls, from_=1, to=247, textvariable=self.slave_var, width=8
        )
        self.slave_box.grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(5, 0))
        self.connect_button = ttk.Button(controls, text="Connect", command=self.toggle_connection)
        self.connect_button.grid(row=1, column=2, sticky="e", padx=(12, 0), pady=(5, 0))
        controls.columnconfigure(0, weight=1)

        readings = ttk.Frame(outer)
        readings.pack(fill="both", expand=True)
        self.temperature_value = tk.StringVar(value="--.-")
        self.humidity_value = tk.StringVar(value="--.-")
        self._reading_panel(readings, 0, "TEMPERATURE", self.temperature_value, "°C")
        self._reading_panel(readings, 1, "HUMIDITY", self.humidity_value, "% RH")

        self.status_var = tk.StringVar(value="Disconnected")
        ttk.Label(outer, textvariable=self.status_var, style="Status.TLabel").pack(
            anchor="w", pady=(14, 0)
        )

    @staticmethod
    def _reading_panel(parent, column, title, value, unit):
        """Add one labeled measurement panel to the readings row."""
        panel = ttk.Frame(parent, padding=(18, 16))
        panel.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0))
        ttk.Label(panel, text=title, style="Subtitle.TLabel").pack(anchor="w")
        line = ttk.Frame(panel)
        line.pack(anchor="w", pady=(10, 0))
        ttk.Label(line, textvariable=value, style="Reading.TLabel").pack(side="left")
        ttk.Label(line, text=unit, style="Unit.TLabel").pack(side="left", padx=(6, 0), pady=(12, 0))
        parent.columnconfigure(column, weight=1)

    def refresh_ports(self):
        """Rescan available serial ports and update the COM-port selector."""
        ports = [port.device for port in list_ports.comports()]
        current = self.port_var.get()
        self.port_box["values"] = ports
        if current in ports:
            self.port_var.set(current)
        elif ports:
            self.port_var.set(ports[0])
        else:
            self.port_var.set("")
            self.status_var.set("No serial ports found")

    def _update_connection_summary(self):
        """Display the currently selected Modbus serial parameters."""
        settings = self.serial_settings
        self.connection_summary.set(
            f"Modbus RTU  /  {settings['baudrate']} baud, "
            f"{settings['bytesize']}{settings['parity']}"
            f"{float(settings['stopbits']):g}"
        )

    def open_settings(self):
        """Open a dialog to edit serial settings for the next connection."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Serial Settings")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        content = ttk.Frame(dialog, padding=18)
        content.pack(fill="both", expand=True)
        settings = self.serial_settings
        baud_var = tk.StringVar(value=str(settings["baudrate"]))
        data_bits_var = tk.StringVar(value=str(settings["bytesize"]))
        parity_var = tk.StringVar(value=settings["parity"])
        stop_bits_var = tk.StringVar(value=str(settings["stopbits"]))
        timeout_var = tk.StringVar(value=str(settings["timeout"]))

        fields = (
            ("Baud rate", baud_var, ("1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200")),
            ("Data bits", data_bits_var, ("5", "6", "7", "8")),
            ("Parity", parity_var, ("N", "E", "O", "M", "S")),
            ("Stop bits", stop_bits_var, ("1", "1.5", "2")),
        )
        for row, (label, variable, values) in enumerate(fields):
            ttk.Label(content, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Combobox(
                content, textvariable=variable, values=values, state="readonly", width=16
            ).grid(row=row, column=1, sticky="ew", padx=(18, 0), pady=5)

        ttk.Label(content, text="Timeout (seconds)").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(content, textvariable=timeout_var, width=19).grid(
            row=4, column=1, sticky="ew", padx=(18, 0), pady=5
        )
        error_var = tk.StringVar()
        ttk.Label(content, textvariable=error_var, foreground="#a12f2f").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        buttons = ttk.Frame(content)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")

        def apply_settings():
            """Validate and apply the values entered in the settings dialog."""
            try:
                new_timeout = float(timeout_var.get())
                if new_timeout <= 0:
                    raise ValueError
            except ValueError:
                error_var.set("Timeout must be a positive number.")
                return

            self.serial_settings = {
                "baudrate": int(baud_var.get()),
                "bytesize": int(data_bits_var.get()),
                "parity": parity_var.get(),
                "stopbits": float(stop_bits_var.get()),
                "timeout": new_timeout,
            }
            self._update_connection_summary()
            dialog.destroy()

        ttk.Button(buttons, text="Apply", command=apply_settings).pack(
            side="right", padx=(0, 8)
        )

    def toggle_connection(self):
        """Start sensor polling or request the active polling thread to stop."""
        if self.worker and self.worker.is_alive():
            self.stop_event.set()
            self.last_error = None
            self.status_var.set("Disconnecting...")
            self.connect_button.configure(state="disabled")
            return

        port = self.port_var.get()
        if not port:
            self.status_var.set("Select an available COM port")
            return
        try:
            slave_address = int(self.slave_var.get())
            if not 1 <= slave_address <= 247:
                raise ValueError
        except (ValueError, tk.TclError):
            self.status_var.set("Slave address must be between 1 and 247")
            return

        self.stop_event.clear()
        self.last_error = None
        self.port_box.configure(state="disabled")
        self.slave_box.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.settings_button.configure(state="disabled")
        self.connect_button.configure(text="Disconnect")
        self.status_var.set(f"Connecting to {port}, slave {slave_address}...")
        self.worker = threading.Thread(
            target=self._poll_sensor,
            args=(port, slave_address, self.serial_settings.copy()),
            daemon=True,
        )
        self.worker.start()

    def _poll_sensor(self, port, slave_address, settings):
        """Connect to the sensor and queue readings for the Tkinter thread."""
        client = None
        try:
            client = ModbusClient(
                port=port,
                framer=FramerType.RTU,
                stopbits=settings["stopbits"],
                bytesize=settings["bytesize"],
                parity=settings["parity"],
                baudrate=settings["baudrate"],
                timeout=settings["timeout"],
                retries=retries,
            )
            if not client.connect():
                raise ConnectionError(f"Could not open {port}")
            sensor = XYMD02(DeviceAddress=slave_address, client=client)
            self.events.put(("connected", port, slave_address))

            while not self.stop_event.is_set():
                temperature = sensor.ReadTemp()
                humidity = sensor.ReadHumidity()
                self.events.put(("reading", temperature, humidity))
                self.stop_event.wait(2)
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            if client is not None:
                client.close()
            self.events.put(("stopped",))

    def _process_events(self):
        """Apply queued connection and reading events on the GUI thread."""
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break

            if event[0] == "connected":
                self.status_var.set(f"Connected: {event[1]}  |  Slave {event[2]}")
            elif event[0] == "reading":
                self.temperature_value.set(f"{event[1]:.1f}")
                self.humidity_value.set(f"{event[2]:.1f}")
            elif event[0] == "error":
                self.last_error = event[1]
            elif event[0] == "stopped":
                self.port_box.configure(state="readonly")
                self.slave_box.configure(state="normal")
                self.refresh_button.configure(state="normal")
                self.settings_button.configure(state="normal")
                self.connect_button.configure(text="Connect", state="normal")
                if self.last_error:
                    self.status_var.set(f"Error: {self.last_error}")
                else:
                    self.status_var.set("Disconnected")

        self.root.after(100, self._process_events)

    def _close(self):
        """Stop background polling and close the application window."""
        self.stop_event.set()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SensorApp(root)
    root.mainloop()





