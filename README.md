# Biofeed

## UDP rebroadcast of Bluetooth heart rate sensor data

This is a basic example of interfacing with a bluetooth single-lead ECG device (heart rate monitor). The data received are rebroadcast over UDP for consumption by other devices on the same IP network. My intended use case is in biofeedback experiments. Specifically, I intend to create plugins that read this stream and produce modulation signals for a modular synthesizer.

I do not have much experience interfacing with Bluetooth devices, so rather than diving into platform-specific calls to OS Bluetooth services, I wanted to begin with a cross-platform library in Python. The code here was written for the Polar H10 because this is the device I have on hand. It has only been tested with this device, but certain aspects of the code should work with other heart rate devices.

The Polar H10 provides heart rate, R-R interval, and the realtime ECG data from which these figures are derived. The ECG data is filtered on the device to remove low frequency components from muscle movement etc. It can also provide other data such as accelerometer data which are not yet read by this example.

The H10 is a Bluetooth Low Energy (BLE) device, a standard which is actually completely separate from classic Bluetooth. The heart rate and R-R interval data area follow the Bluetooth Low Energy (BLE) Generic Attribute Profile (GATT), which makes them non-proprietary and allows them to be read by devices from various manufacturers without special configuration. The ECG data follows the proprietary Polar Measurement Data (PMD) specification.

## Abbreviations
- BLE: Bluetooth Low Energy, a separate specification from "classic" Bluetooth.
- PMD: Polar Measurement Data. This is explained by the PMD Specification document.
- PPG: Photoplethysmography (PPG) is optical blood flow data, as collected by watches or armbands like the Polar OH1. The Polar H10 collects true ECG data rather than PPG.
- Other relevant abbreviations are defined _at the end_ of the Polar Measurement Data Specification.

## Bluetooth Low Energy
Bluetooth Low Energy (BLE) is a completely separate standard from classic Bluetooth. BLE Servers advertise their presence every so often. They may advertise frequently after some kind of interaction, then back off to save energy.

BLE has a data rate of 100kbit to 1Mbit per second. This is not sufficient for transmitting voice, but fine for many other purposes. It uses very little energy. Some devices like the H10 can run for one or two years on a single cell battery.

BLE has several pairing procedures. Some devices Just Work (this is apparently the technical name), while others rely on passkey entry to flout Man In The Middle (MITM) attacks. The H10 seems to "just work". Connections begin in Security Mode 1, Level 1 (no authentication and no encryption) and can then be upgraded to any security level. [1]

A certain UUID range is reserved for GATT standard services. These are represented with four hex digits (a 16 bit integer), which are substituted into the first 32-bit section of the UUID (e.g. the service `ABCD` gives the UUID `0000ABCD-0000-1000-8000-00805f9b34fb`). All other pseudorandom UUIDs can be used by manufacturers for their own purposes. You shouldn't need to manually insert the 16 bit numbers into this standard UUID (as done in some example code). I'd expect the bluetooth library to do this for you.

Each device has a MAC address and UUID that uniquely identify it. For some reason these are not used to connect to the device on MacOS. A UUID is used instead.

BLE GATT defines some technical terms. It's important when reading technical documentation like the Polar Measurement Data (PMD) Specification to interpret these terms in their narrow GATT technical sense, not as everyday English words. The hierarchy of terms is: Device -> Service -> Characteristic -> Detail. Each one of these has a reserved UUID (in the case of standard GATT) or a pseudorandom one assigned by a manufacturer for proprietary extensions. I will write these terms with Initial Capitals to indicate that they are being used in their narrow technical sense. When reading the PMD specification, note that a list of acronyms is *at the end* of the document, and some important interactions are given only as examples without text explanation.

Heart Rate is a standard Characteristic. The H10 defines an additional Polar Measurement Data (PMD) Service whose UUID begins with `FB005C80`. This contains two Characteristics whose UUIDs are the same as the Service except that the initial 32-bit segments end with `5C81` (the PMD Control Point) and `5C82` (the PMD Data MTU Characteristic).

If the H10 is paired with some other device (such as your phone or watch), you may get `bleak.exc.BleakError: Device with address X was not found`. Or maybe if the contacts are not wet - once I wet them, I saw it three times in 5 seconds. But then it failed again - maybe I need to call stop_notify and disconnect to free it up. Or maybe it was simply Bluetility interfering with my connection attempt.

The H10 seems to advertise its presence even when it's not being worn, but also seems to refuse connections until it detects skin contact.

The ECG data is not present in the standard GATT profile and is specific to Polar. It uses a Service and Characteristics described in the Polar Measurement Data (PMD) Specification document, which is available as a PDF in the Polar BLE SDK repository on GitHub.

read_gatt_char means read a Characteristic, not a *character*.

There are no spec pages for querying or setting stream settings or starting a stream, but the document contains examples of doing these things for Acceleration, ECG, and PPG streams with embedded explanations of the bytes in the messages.

A tool called Bluetility can be used on MacOS to browse the characteristics of nearby bluetooth devices.
https://github.com/jnross/Bluetility/releases

Sources:
[1](https://medium.com/rtone-iot-security/deep-dive-into-bluetooth-le-security-d2301d640bfc) 
- https://en.wikipedia.org/wiki/QRS_complex
- https://en.wikipedia.org/wiki/Bluetooth_Low_Energy#Software_model 
- [Polar BLE SDK on GitHub](https://github.com/polarofficial/polar-ble-sdk) This is only for mobile (iOS and Android) but may contain some clues in the source code and GitHub issues, and contains PDF reference docs.
- The GitHub issues such as [this one](https://github.com/polarofficial/polar-ble-sdk/issues/213) contain examples of how to configure the PMD stream.
- It contains a [sample application](https://github.com/polarofficial/polar-ble-sdk/blob/master/examples/example-android/androidBleSdkTestApp/app/src/main/java/com/polar/androidblesdk/MainActivity.kt) that may give some clues about standard usage patterns

