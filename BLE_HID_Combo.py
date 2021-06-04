# Implements a BLE HID keyboard

from micropython import const
import struct
import bluetooth


def ble_irq(event, data):
    global conn_handle
    if event == 1:
        print("connect")
        conn_handle = data[0]
    else:
        print("event:", event, data)


ble = bluetooth.BLE()
ble.active(1)
ble.irq(ble_irq)

UUID = bluetooth.UUID

F_READ = bluetooth.FLAG_READ
F_WRITE = bluetooth.FLAG_WRITE
F_READ_WRITE = bluetooth.FLAG_READ | bluetooth.FLAG_WRITE
F_READ_NOTIFY = bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY

ATT_F_READ = 0x01
ATT_F_WRITE = 0x02

# fmt: off
HID_REPORT_MAP = bytes([
    0x05, 0x01,     # Usage Page (Generic Desktop)
    0x09, 0x06,     # Usage (Keyboard)
    0xA1, 0x01,     # Collection (Application)
    0x85, 0x01,     #     Report ID (1)
    0x75, 0x01,     #     Report Size (1)
    0x95, 0x08,     #     Report Count (8)
    0x05, 0x07,     #     Usage Page (Key Codes)
    0x19, 0xE0,     #     Usage Minimum (224)
    0x29, 0xE7,     #     Usage Maximum (231)
    0x15, 0x00,     #     Logical Minimum (0)
    0x25, 0x01,     #     Logical Maximum (1)
    0x81, 0x02,     #     Input (Data, Variable, Absolute); Modifier byte
    0x95, 0x01,     #     Report Count (1)
    0x75, 0x08,     #     Report Size (8)
    0x81, 0x01,     #     Input (Constant); Reserved byte
    0x95, 0x05,     #     Report Count (5)
    0x75, 0x01,     #     Report Size (1)
    0x05, 0x08,     #     Usage Page (LEDs)
    0x19, 0x01,     #     Usage Minimum (1)
    0x29, 0x05,     #     Usage Maximum (5)
    0x91, 0x02,     #     Output (Data, Variable, Absolute); LED report
    0x95, 0x01,     #     Report Count (1)
    0x75, 0x03,     #     Report Size (3)
    0x91, 0x01,     #     Output (Constant); LED report padding
    0x95, 0x06,     #     Report Count (6)
    0x75, 0x08,     #     Report Size (8)
    0x15, 0x00,     #     Logical Minimum (0)
    0x25, 0x65,     #     Logical Maximum (101)
    0x05, 0x07,     #     Usage Page (Key Codes)
    0x19, 0x00,     #     Usage Minimum (0)
    0x29, 0x65,     #     Usage Maximum (101)
    0x81, 0x00,     #     Input (Data, Array); Key array (6 bytes)
    0xC0,           # End Collection
    #here-----把鍵盤和多媒體的 HID_REPORT_MAP 並在一起
    0x05, 0x0C,     # Usage Page (CONSUMER PAGE)
    0x09, 0x01,     # Usage (Consumer Control)
    0xA1, 0x01,     # Collection (Application)
    0x85, 0x02,     #     here Report ID (2)
    0x75, 0x10,     #     Report Size (16)
    0x95, 0x01,     #     Report Count (1)
    0x15, 0x01,     #     Logical Minimum (0)
    0x26,
    0x8C, 0x02,     #     Logical Maximum (1)
    0x19, 0x01,     #     Usage Minimum (224)
    0x2A,
    0x8C, 0x02,     #     Usage Maximum (231)
    0x81, 0x00,     #     Input (Data, Variable, Absolute); Modifier byte
    0xC0,           # End Collection
])
# fmt: on

# 建立伺服器
hid_service = (
    UUID(0x1812),  # Human Interface Device            人機介面設備
    (
        (UUID(0x2A4A), F_READ),  # HID information     HID信息
        (UUID(0x2A4B), F_READ),  # HID report map      HID報告圖
        (UUID(0x2A4C), F_WRITE),  # HID control point  HID控制點
        (UUID(0x2A4D), F_READ_NOTIFY, (
            (UUID(0x2908), ATT_F_READ),)
        ),  # Keyboard HID report / reference
        (UUID(0x2A4D), F_READ_WRITE, (
            (UUID(0x2908), ATT_F_READ),)
        ),  # Keyboard status HID report / reference
        (UUID(0x2A4D), F_READ_NOTIFY, (
            (UUID(0x2908), ATT_F_READ),)
        ),  # here Consumer Control HID report / reference
        (UUID(0x2A4E), F_READ_WRITE),  # HID protocol mode
    ),
)

# register services  註冊服務
ble.config(gap_name="MP-keyboard")
handles = ble.gatts_register_services((hid_service,))
print(handles)
#here 多了 h_com 和 h_d3
h_info, h_hid, _, h_rep, h_d1, _, h_d2, h_com, h_d3, h_proto = handles[0]

# set initial data
ble.gatts_write(h_info, b"\x01\x01\x00\x02")  # HID info: ver=1.1, country=0, flags=normal
ble.gatts_write(h_hid, HID_REPORT_MAP)  # HID report map
ble.gatts_write(h_d1, struct.pack("<BB", 1, 1))  # report: id=1, type=input
ble.gatts_write(h_d2, struct.pack("<BB", 1, 2))  # report: id=1, type=output
ble.gatts_write(h_d3, struct.pack("<BB", 2, 1))  #here  report: id=2, type=input
ble.gatts_write(h_proto, b"\x01")  # protocol mode: report

# advertise 廣告
adv = (
    b"\x02\x01\x06"
    b"\x03\x03\x12\x18"  # complete list of 16-bit service UUIDs: 0x1812
    b"\x03\x19\xc1\x03"  # appearance: keyboard
    b"\x0c\x09MP-keyboard"  # complete local name(要與上面的gap_name一樣)
)
conn_handle = None
ble.gap_advertise(100_000, adv)

# once connected use the following to send reports

# 可以查看以下對照表
# https://circuitpython.readthedocs.io/projects/hid/en/latest/_modules/adafruit_hid/keycode.html
# https://www.usb.org/sites/default/files/documents/hut1_12v2.pdf
def send_keycode(mod, code):
    # here press the key, 控制鍵盤用 h_rep
    ble.gatts_notify(conn_handle, h_rep, struct.pack("8B", mod, 0, code, 0, 0, 0, 0, 0))
    # release the key
    ble.gatts_notify(conn_handle, h_rep, b"\x00\x00\x00\x00\x00\x00\x00\x00")

def send_char(char):
    if char == " ":
        mod = 0
        code = 0x2C
    elif ord("a") <= ord(char) <= ord("z"):
        mod = 0
        code = 0x04 + ord(char) - ord("a")
    elif ord("A") <= ord(char) <= ord("Z"):
        mod = 2
        code = 0x04 + ord(char) - ord("A")
    else:
        assert 0
    send_keycode(mod, code)
    #     ble.gatts_notify(conn_handle, h_rep, struct.pack("8B", mod, 0, code, 0, 0, 0, 0, 0))
    #     ble.gatts_notify(conn_handle, h_rep, b"\x00\x00\x00\x00\x00\x00\x00\x00")


def send_str(st):
    for c in st:
        send_char(c)

def send_media_code(code):   # 0x28:ENTER    0x46:Print Scrn
    # here 控制音量用 h_com
    ble.gatts_notify(conn_handle, h_com, struct.pack("2B", code, 0x00))
    ble.gatts_notify(conn_handle, h_com, b"\x00\x00")

def vol_inc():
    send_media_code(0xE9)

def vol_dec():
    send_media_code(0xEA)

def screen_shot():   # 0x28:ENTER    0x46:Print Scrn
    send_keycode(0, 0x46)

from machine import Pin
import time

b12_prev = True   # 是否按下按鈕
b13_prev = True   # 是否按下按鈕

b12 = Pin(12, Pin.IN, Pin.PULL_UP)
b13 = Pin(13, Pin.IN, Pin.PULL_UP)
while True:
    if b12_prev and (not b12.value()):
        screen_shot()
        print("截圖")
    b12_prev = b12.value()
    if b13_prev and (not b13.value()):
        vol_inc()
        print("大聲 ")
    b13_prev = b13.value()
    
    time.sleep(0.05)