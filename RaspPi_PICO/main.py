import ujson as json
from machine import Pin, I2C, SPI, ADC, Timer
import onewire, ds18x20
import sys
import time

# === BLINK SETUP ===
led = Pin(25, Pin.OUT)
blink_timer = Timer()
blink_freq = 2  # Default Hz

def blink(timer):
    led.toggle()

def set_blink_frequency(hz):
    global blink_freq
    try:
        hz = int(hz)
        if hz <= 0:
            blink_timer.deinit()
            return False
        blink_timer.init(freq=hz, mode=Timer.PERIODIC, callback=blink)
        blink_freq = hz
        return True
    except:
        return False

# Initialize blinking
set_blink_frequency(blink_freq)

# I2C setup
i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)

# SPI setup
spi = SPI(0, baudrate=1000000, polarity=0, phase=0,
          sck=Pin(18), mosi=Pin(19), miso=Pin(16))

# GPIO pins
gpio_pins = {
    'gp2': Pin(2, Pin.OUT),
    'gp3': Pin(3, Pin.OUT),
    'gp6': Pin(6, Pin.OUT),
    'gp7': Pin(7, Pin.OUT),
}

# ADC pins
adc_pins = {
    26: ADC(26),
    27: ADC(27),
    28: ADC(28)
}

# 1-Wire setup
ow_pin = Pin(15)
ow = onewire.OneWire(ow_pin)
ds = ds18x20.DS18X20(ow)
roms = ds.scan()

# Wiegand setup (bit collection)
wiegand_bits = []
def wiegand0(pin):
    wiegand_bits.append(0)
def wiegand1(pin):
    wiegand_bits.append(1)
Pin(10, Pin.IN, Pin.PULL_UP).irq(trigger=Pin.IRQ_FALLING, handler=wiegand0)
Pin(11, Pin.IN, Pin.PULL_UP).irq(trigger=Pin.IRQ_FALLING, handler=wiegand1)

# JTAG stub (GPIO12=TCK, GPIO13=TDI)
jtag_tck = Pin(12, Pin.OUT)
jtag_tdi = Pin(13, Pin.OUT)

# JSON send helper
def send_json(obj):
    print(json.dumps(obj))  # Print to USB serial

# Command processor
def process_command(cmd):
    print("Received command:", cmd)
    try:
        c = cmd.get("cmd")

        if c == "i2c_write":
            addr = cmd.get("addr")
            data = bytes(cmd.get("data", []))
            i2c.writeto(addr, data)
            return {"status": "ok", "cmd": "i2c_write"}

        elif c == "i2c_read":
            addr = cmd.get("addr")
            length = cmd.get("length", 1)
            data = i2c.readfrom(addr, length)
            return {"status": "ok", "cmd": "i2c_read", "data": list(data)}

        elif c == "spi_xfer":
            data = bytes(cmd.get("data", []))
            rx = bytearray(len(data))
            spi.write_readinto(data, rx)
            return {"status": "ok", "cmd": "spi_xfer", "data": list(rx)}

        elif c == "gpio_set":
            pin_name = cmd.get("pin")
            val = cmd.get("value", 0)
            pin = gpio_pins.get(pin_name)
            if pin is None:
                return {"status": "error", "error": "Invalid pin"}
            pin.value(val)
            return {"status": "ok", "cmd": "gpio_set", "pin": pin_name, "value": val}

        elif c == "uart_tx":
            data = cmd.get("data", "")
            print(data)
            return {"status": "ok", "cmd": "uart_tx", "echo": data}

        elif c == "adc_read":
            pin = cmd.get("pin", 26)
            adc = adc_pins.get(pin)
            if adc is None:
                return {"status": "error", "error": "Invalid ADC pin"}
            val = adc.read_u16()
            return {"status": "ok", "cmd": "adc_read", "pin": pin, "value": val}

        elif c == "ow_read_temp":
            ds.convert_temp()
            time.sleep_ms(750)
            temps = {rom.hex(): ds.read_temp(rom) for rom in roms}
            return {"status": "ok", "cmd": "ow_read_temp", "temps": temps}

        elif c == "wiegand_data":
            bits = wiegand_bits[:]
            wiegand_bits[:] = []
            return {"status": "ok", "cmd": "wiegand_data", "bits": bits, "bitcount": len(bits)}

        elif c == "jtag_toggle":
            tck = cmd.get("tck", 0)
            tdi = cmd.get("tdi", 0)
            jtag_tdi.value(tdi)
            jtag_tck.value(tck)
            return {"status": "ok", "cmd": "jtag_toggle", "tck": tck, "tdi": tdi}

        elif c == "set_blink_freq":
            hz = cmd.get("hz", 2)
            success = set_blink_frequency(hz)
            if success:
                return {"status": "ok", "cmd": "set_blink_freq", "hz": hz}
            else:
                return {"status": "error", "error": "Invalid frequency"}

        else:
            return {"status": "error", "error": "Unknown command"}

    except Exception as e:
        return {"status": "error", "error": str(e)}

# Read line from USB input
def read_line():
    try:
        return input().strip()  # From USB serial
    except Exception:
        return ""

# Timer for "Waiting for CMD" message
wait_timer = Timer()

def print_waiting_msg(timer):
    print("Waiting for CMD")

# Main loop
def main_loop():
    while True:
        try:
            line = read_line()
            if not line:
                continue
            try:
                cmd = json.loads(line)
            except Exception as e:
                send_json({"status": "error", "error": "JSON decode failed: %s" % str(e)})
                continue
            resp = process_command(cmd)
            send_json(resp)
        except Exception as e:
            sys.print_exception(e)
            time.sleep(1)

# Entry point
if __name__ == "__main__":
    print("System starting...")
    wait_timer.init(period=550, mode=Timer.PERIODIC, callback=print_waiting_msg)
    main_loop()

