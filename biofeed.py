import asyncio
import math
import os
import signal
import sys
import time
import pandas as pd
from bleak import BleakClient
from bleak import BleakScanner
from bleak.uuids import uuid16_dict
import matplotlib.pyplot as plt
import matplotlib

""" Predefined UUID (Universal Unique Identifier) mapping are based on Heart Rate GATT service Protocol that most
Fitness/Heart Rate device manufacturer follow (Polar H10 in this case) to obtain a specific response input from
the device acting as an API """

## Source: https://towardsdatascience.com/creating-a-data-stream-with-polar-device-a5c93c9ccc59

## UUID mapping
uuid16_dict = {v: k for k, v in uuid16_dict.items()}

## This is the device MAC ID, please update with your device ID (of what, the H10?)
## Apparently on MacOS this has to be a UUID not a MAC address
ADDRESS = "D4:52:48:88:EA:04"

# Polar Measurement Data (PMD) Service and Characteristics
# See "Polar Measurement Data Specification for 3rd Party"
# section "Gatt Service and Characteristics Declaration"
PMD_UUID_TEMPLATE = "FB00{0:x}-02E7-F387-1CAD-8ACD2D8DF0C8"

# UUID for the Polar Measurement Data Service
PMD_SERVICE = PMD_UUID_TEMPLATE.format(0x5C80)

## UUID to write or read stream settings
PMD_CONTROL = PMD_UUID_TEMPLATE.format(0x5C81)

## UUID for the data stream itself, to subscribe to notifications
PMD_DATA = PMD_UUID_TEMPLATE.format(0x5C82)

# This standard GATT template should be handled by Bleak right? Why do we need to manually substitute it?
TEMPLATE="0000{0:x}-0000-1000-8000-00805f9b34fb"

## UUID for model number
MODEL_NBR_UUID = TEMPLATE.format(uuid16_dict.get("Model Number String"))

## UUID for manufacturer name ##
MANUFACTURER_NAME_UUID = TEMPLATE.format(uuid16_dict.get("Manufacturer Name String"))

## UUID for battery level ##
BATTERY_LEVEL_UUID = TEMPLATE.format(uuid16_dict.get("Battery Level"))

# Document this "write string".

## UUID for Request of ECG Stream ##
ECG_WRITE = bytearray([0x02, 0x00, 0x00, 0x01, 0x82, 0x00, 0x01, 0x01, 0x0E, 0x00])

# Plolar H10  sampling frequency (check SDK code for other valid values)
ECG_SAMPLING_FREQ = 130

def flag(byte, n):
    return (byte & (1 << n)) != 0

class PolarFeatures:
    # See "read features from device" example in PMD specification document.
    def __init__(self, bytes):
        # Check that this is a "control point feature read response"
        assert bytes[0] == 0x0F
        # Read bitfield showing what features the connected device has.
        # See PMD Measurement Types section of PMD specification document.
        byte = bytes[1]
        self.ecg = flag(byte, 0);
        self.ppg = flag(byte, 1);
        self.acceleration = flag(byte, 2);
        self.pp_interval = flag(byte, 3);
        # bit 4 reserved for future use
        self.gyroscope = flag(byte, 5);
        self.magnetometer = flag(byte, 6);

## Resource allocation for data collection
ecg_session_data = []
ecg_session_time = []

# A series of three-byte integers in millivolts
def convert_ecg_data(sender, data):
    print("ECG data:", data[:10]) #data)
    if data[0] == 0x00:
       timestamp = convert_to_unsigned_long(data, 1, 8)
       step = 3
       samples = data[10:]
       offset = 0
       while offset < len(samples):
           ecg = convert_array_to_signed_int(samples, offset, step)
           # print(ecg)    
           offset += step
           ecg_session_data.extend([ecg])
           ecg_session_time.extend([timestamp])
           
def convert_array_to_signed_int(data, offset, length):
    return int.from_bytes(bytearray(data[offset : offset + length]),       
          byteorder="little", signed=True,)
          
def convert_to_unsigned_long(data, offset, length):
    return int.from_bytes(bytearray(data[offset : offset + length]),   
          byteorder="little", signed=False,)
          
def detection_callback(device, advertisement_data):
    print(device.address, "RSSI:", device.rssi, "Name:", device.name)
    # print(device.address, "RSSI:", device.rssi, advertisement_data)

## This is sort-of decoding the PPI Frame Type from the Polar docs (the P-P interval similar to R-R interval), 
## which I think is not actually supported on the H10, but is identically structured to
## the GATT heart rate service (except that the latter has a flags field at the beginning)
def convert_hr_data(sender, data):
    # See BLUETOOTH SERVICE SPECIFICATION for the Heart Rate Service (Document ID: HRS_SPEC)
    # Flags 0-3 are false, flag 4 (R-R interval) is true.
    # This means we get an 8-bit heart rate followed by a 16-bit R-R interval
    if data[0] == 0x16:
        print("rate:", data[1])
        print("interval:", convert_array_to_signed_int(data, 2, 2))
    
class GattHeartRate:
    def __init__(self, bytes):
        # Read bitfield describing how heart rate data are encoded.
        byte = bytes[1]
        self.wide_int = flag(byte, 0); # unsigned 16 bit instead of u8
        self.skin_contact_sensor = flag(byte, 1);
        self.skin_contact_detected = flag(byte, 2);
        self.energy_expended = flag(byte, 3);
        self.r_r_interval = flag(byte, 4);
        # flag bits 5-7 unused
        # next is heart rate field, then energy field, then r-r interval field

            
async def callbackScan():
    scanner = BleakScanner()
    scanner.register_detection_callback(detection_callback)
    await scanner.start()
    await asyncio.sleep(5.0)
    await scanner.stop()
    for d in scanner.discovered_devices:
        print(d)

H10_ADDRESS = "5C92E382-43DC-466E-ADD3-71C1B196E41D"

async def scanPrint():
    print("Scanning for Polar H10...")
    devices = await BleakScanner.discover()
    address = None
    rssi = -90
    for device in devices:
        if device.name.startswith("Polar H10") and device.rssi > rssi:            
            address = device.address
            rssi = device.rssi
    print("Address of H10:", address)
    async with BleakClient(address) as client:
        model_number = await client.read_gatt_char(MODEL_NBR_UUID)
        manufacturer = await client.read_gatt_char(MANUFACTURER_NAME_UUID)
        battery_level = await client.read_gatt_char(BATTERY_LEVEL_UUID)
        print("Model Number: {0}".format("".join(map(chr, model_number))))
        print("Manufacturer: {0}".format("".join(map(chr, manufacturer))))
        print("Battery Level: {0}".format("".join(map(chr, battery_level))))

# asyncio.run(scanPrint())

## UUID for heart rate
##https://stackoverflow.com/questions/69977624/how-do-i-find-out-which-uuid-i-should-use-to-request-data-from-my-polar-h10-sens
## also
##https://stackoverflow.com/questions/52970763/trying-to-get-heart-rate-variability-from-polar-h10-bluetooth-low-energy-sample
## These are standard bluetooth heart rate items, see bluetooth docs.

## GATT Characteristic and Object Type 0x2A37 is "Heart Rate Measurement"
HR_UUID = TEMPLATE.format(0x2A37)
## Bluetooth assigned UUID document also specifies GATT service 0x180D which yields "characteristic not found"

## ECG data is a PMD_DATA stream.
## Heart Rate and RR interval are apparently not available as PMD_DATA streams on the H10, 
## despite what the PDF docs say.

## https://github.com/hbldh/bleak/issues/786 implies there is some problem 
## with write_gatt_char but I haven't seen it. NOTE that issue contains a great "minimum working example"

async def info():
    # When we exit this scope it will close the client 
    # (though confusingly the variable doesn't go out of scope)
    async with BleakClient(H10_ADDRESS) as client:
        services = await client.get_services()
        print("Available services:")
        for service in services:
            print(service)
        model_number = await client.read_gatt_char(MODEL_NBR_UUID)
        manufacturer = await client.read_gatt_char(MANUFACTURER_NAME_UUID)
        battery_level = await client.read_gatt_char(BATTERY_LEVEL_UUID)
        print("Model Number: {0}".format("".join(map(chr, model_number))))
        print("Manufacturer: {0}".format("".join(map(chr, manufacturer))))
        print("Battery Level: {0}%".format(battery_level[0]))    
        att_read = await client.read_gatt_char(PMD_CONTROL)
        print("Polar Measurement Data features:", vars(PolarFeatures(att_read)))
        await client.write_gatt_char(PMD_CONTROL,  ECG_WRITE)
        ## Request notifications of ECG stream
        await client.start_notify(PMD_DATA, convert_ecg_data)
        ## Also start a heart rate notification stream
        await client.start_notify(HR_UUID, convert_hr_data)
        await asyncio.sleep(5.0)
        await client.stop_notify(PMD_DATA)
        await client.stop_notify(HR_UUID)
        await client.disconnect()


asyncio.run(info())
#asyncio.run(callbackScan())
#asyncio.run(scanPrint())
