import Tkinter as tk
import ScrolledText
import tkMessageBox
import serial
import serial.tools.list_ports
import threading

try:
    import simplejson as json  # Python 2.6 fallback
except ImportError:
    import json

DEFAULT_BAUD = 115200

class PicoJSONBridgeGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Pico JSON Bridge GUI")
        self.ser = None

        self.templates = {
            "I2C Write": '{"cmd": "i2c_write", "addr": 64, "data": [0, 255]}',
            "I2C Read": '{"cmd": "i2c_read", "addr": 64, "length": 2}',
            "SPI Transfer": '{"cmd": "spi_xfer", "data": [170, 187, 204]}',
            "GPIO Set": '{"cmd": "gpio_set", "pin": "gp2", "value": 1}',
            "UART TX": '{"cmd": "uart_tx", "data": "Hello from PC"}',
            "ADC Read": '{"cmd": "adc_read", "pin": 26}',
            "1-Wire Temp": '{"cmd": "ow_read_temp"}',
            "Wiegand Get": '{"cmd": "wiegand_data"}',
            "JTAG Toggle": '{"cmd": "jtag_toggle", "tck": 1, "tdi": 0}'
        }

        # Serial port dropdown
        self.port_var = tk.StringVar()
        self.port_menu = tk.OptionMenu(master, self.port_var, "")
        self.port_menu.pack(pady=4)
        self.refresh_ports()

        self.refresh_btn = tk.Button(master, text="Refresh Ports", command=self.refresh_ports)
        self.refresh_btn.pack(pady=2)

        self.connect_btn = tk.Button(master, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(pady=2)

        # Templates dropdown
        self.template_var = tk.StringVar()
        self.template_var.set("Select Command Template")
        self.template_menu = tk.OptionMenu(master, self.template_var, *self.templates.keys(), command=self.load_template)
        self.template_menu.pack(pady=4)

        # JSON entry
        self.cmd_label = tk.Label(master, text="Enter JSON command:")
        self.cmd_label.pack()
        self.cmd_entry = tk.Text(master, height=6, width=60)
        self.cmd_entry.insert(tk.END, self.templates["I2C Write"])
        self.cmd_entry.pack(pady=4)

        self.send_btn = tk.Button(master, text="Send", command=self.send_command)
        self.send_btn.pack(pady=2)

        self.clear_btn = tk.Button(master, text="Clear Output", command=self.clear_output)
        self.clear_btn.pack(pady=2)

        self.output_box = ScrolledText.ScrolledText(master, width=80, height=20)
        self.output_box.pack(pady=4)

        self.running = False

    def refresh_ports(self):
        ports = []
        for port in serial.tools.list_ports.comports():
            desc = port[1].lower()
            if "pico" in desc or "usb serial" in desc or "tty" in desc or "com" in port[0].lower():
                ports.append(port[0])
        if not ports:
            ports = ["No Pico Detected"]
        self.port_var.set(ports[0])
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for port in ports:
            menu.add_command(label=port, command=lambda value=port: self.port_var.set(value))

    def toggle_connection(self):
        if self.ser:
            self.running = False
            self.ser.close()
            self.ser = None
            self.connect_btn.config(text="Connect")
            self.output_box.insert(tk.END, "[INFO] Disconnected\n")
        else:
            try:
                self.ser = serial.Serial(self.port_var.get(), DEFAULT_BAUD, timeout=0.1)
                self.running = True
                t = threading.Thread(target=self.read_from_serial)
                t.setDaemon(True)
                t.start()
                self.connect_btn.config(text="Disconnect")
                self.output_box.insert(tk.END, "[INFO] Connected to %s\n" % self.port_var.get())
            except Exception as e:
                tkMessageBox.showerror("Error", "Failed to connect: %s" % e)

    def load_template(self, selection):
        self.cmd_entry.delete("1.0", tk.END)
        self.cmd_entry.insert(tk.END, self.templates[selection])

    def send_command(self):
        if self.ser and self.ser.isOpen():
            try:
                cmd = self.cmd_entry.get("1.0", tk.END).strip()
                obj = json.loads(cmd)
                self.ser.write((json.dumps(obj) + '\n').encode('utf-8'))
                self.output_box.insert(tk.END, ">> %s\n" % json.dumps(obj))
                self.output_box.see(tk.END)
            except Exception as e:
                tkMessageBox.showerror("Error", "Invalid JSON: %s" % e)

    def read_from_serial(self):
        buffer = ""
        while self.running and self.ser:
            try:
                data = self.ser.read(self.ser.inWaiting() or 1)
                if data:
                    try:
                        buffer += data.decode('utf-8')
                    except:
                        continue
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            try:
                                parsed = json.loads(line)
                                formatted = json.dumps(parsed, indent=2)
                                self.output_box.insert(tk.END, "<< %s\n" % formatted)
                            except:
                                self.output_box.insert(tk.END, "<< %s\n" % line)
                            self.output_box.see(tk.END)
            except:
                break

    def clear_output(self):
        self.output_box.delete("1.0", tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = PicoJSONBridgeGUI(root)
    root.mainloop()

