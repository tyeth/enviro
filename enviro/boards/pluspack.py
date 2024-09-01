# # Board file for Pico Enviro+ Pack

# from machine import Pin, I2C, ADC, UART
# from pimoroni import BME68X, LTR559, PMS5003, Microphone, Button, RGBLED
# from picographics import PicoGraphics, DISPLAY_ENVIRO_PLUS

# # I2C setup for Enviro+ Pack
# i2c = I2C(0, sda=Pin(4), scl=Pin(5))

import enviro.helpers as helpers
import math
from breakout_bme68x import BreakoutBME68X
from breakout_ltr559 import BreakoutLTR559
from enviro import config
from enviro import i2c
import time
from breakout_ltr559 import BreakoutLTR559
from machine import Pin, PWM, ADC, UART
from enviro import i2c
from phew import logging
from pimoroni import Analog
from enviro import i2c, activity_led
import enviro.helpers as helpers
from phew import logging
from enviro.constants import WAKE_REASON_RTC_ALARM, WAKE_REASON_BUTTON_PRESS


bme688 = BreakoutBME68X(i2c, address=0x77)
ltr559 = BreakoutLTR559(i2c)


# Sensor setup
mic = Microphone(ADC(26))

# Optional PMS5003 particulate matter sensor setup
# Ensure the PMS5003 is connected and uncomment the following lines to enable
pms5003 = PMS5003(
    uart=UART(1, tx=Pin(8), rx=Pin(9), baudrate=9600),
    pin_enable=Pin(3),
    pin_reset=Pin(2)
)

# Display setup
display = PicoGraphics(display=DISPLAY_ENVIRO_PLUS)

# LED setup
led = RGBLED(6, 7, 10, invert=True)

# Button setup
button_a = Button(12, invert=True)
button_b = Button(13, invert=True)
button_x = Button(14, invert=True)
button_y = Button(15, invert=True)

noise_adc = ADC(0)

ltr559_interrupt_pin = Pin(22 , Pin.IN)

sensor_reset_pin = Pin( , Pin.OUT, value=True)
sensor_enable_pin = Pin( , Pin.OUT, value=False)
boost_enable_pin = Pin( , Pin.OUT, value=False)


# how long to capture the microphone signal for when taking a reading, in milliseconds
MIC_SAMPLE_TIME_MS = 500


PM1_UGM3                = 2
PM2_5_UGM3              = 3
PM10_UGM3               = 4
PM1_UGM3_ATHMOSPHERIC   = 5
PM2_5_UGM3_ATHMOSPHERIC = 6
PM10_UGM3_ATHMOSPHERIC  = 7
PM0_3_PER_LITRE         = 8
PM0_5_PER_LITRE         = 9
PM1_PER_LITRE           = 10
PM2_5_PER_LITRE         = 11
PM5_PER_LITRE           = 12
PM10_PER_LITRE          = 13

def particulates(particulate_data, measure):
  # bit of a fudge to convert decilitres into litres... who uses decilitre?!
  multiplier = 10 if measure >= PM0_3_PER_LITRE else 1
  return ((particulate_data[measure * 2] << 8) | particulate_data[measure * 2 + 1]) * multiplier



def startup(reason):
  global last_ltr559_trigger
  import wakeup

  # check if rain sensor triggered wake
  rain_sensor_trigger = wakeup.get_gpio_state() & (1 << 10)

  if rain_sensor_trigger:
    # read the current rain entries
    rain_entries = []
    if helpers.file_exists("rain.txt"):
      with open("rain.txt", "r") as rainfile:
        rain_entries = rainfile.read().split("\n")

    # add new entry
    logging.info(f"> add new rain trigger at {helpers.datetime_string()}")
    rain_entries.append(helpers.datetime_string())

    # limit number of entries to 190 - each entry is 21 bytes including
    # newline so this keeps the total rain.txt filesize just under one
    # filesystem block (4096 bytes)
    rain_entries = rain_entries[-190:]

    # write out adjusted rain log
    with open("rain.txt", "w") as rainfile:
      rainfile.write("\n".join(rain_entries))

    last_ltr559_trigger = True

    # if we were woken by the RTC or a Poke continue with the startup
    return (reason is WAKE_REASON_RTC_ALARM 
      or reason is WAKE_REASON_BUTTON_PRESS)

  # there was no rain trigger so continue with the startup
  return True

def check_trigger():
  global last_ltr559_trigger
  ltr559_sensor_trigger = ltr559_interrupt_pin.value()

  if ltr559_sensor_trigger and not last_ltr559_trigger:
    activity_led(100)
    time.sleep(0.05)
    activity_led(0)

    # read the current rain entries
    rain_entries = []
    if helpers.file_exists("rain.txt"):
      with open("rain.txt", "r") as rainfile:
        rain_entries = rainfile.read().split("\n")

    # add new entry
    logging.info(f"> add new rain trigger at {helpers.datetime_string()}")
    rain_entries.append(helpers.datetime_string())

    # limit number of entries to 190 - each entry is 21 bytes including
    # newline so this keeps the total rain.txt filesize just under one 
    # filesystem block (4096 bytes)
    rain_entries = rain_entries[-190:]

    # write out adjusted rain log
    with open("rain.txt", "w") as rainfile:
      rainfile.write("\n".join(rain_entries))

  last_ltr559_trigger = ltr559_sensor_trigger



def get_sensor_readings(seconds_since_last, is_usb_power):
    time.sleep(0.5)
    data = bme688.read()

    temperature = round(data[0], 2)
    humidity = round(data[2], 2)

    # Compensate for additional heating when on usb power - this also changes the
    # relative humidity value.
    if is_usb_power:
        adjusted_temperature = temperature - config.usb_power_temperature_offset
        absolute_humidity = helpers.relative_to_absolute_humidity(humidity, temperature)
        humidity = helpers.absolute_to_relative_humidity(absolute_humidity, adjusted_temperature)
        temperature = adjusted_temperature

    pressure = round(data[1] / 100.0, 2)
    gas_resistance = round(data[3])
    # an approximate air quality calculation that accounts for the effect of
    # humidity on the gas sensor
    # https://forums.pimoroni.com/t/bme680-observed-gas-ohms-readings/6608/25
    aqi = round(math.log(gas_resistance) + 0.04 * humidity, 1)

    # bme280 returns the register contents immediately and then starts a new reading
    # we want the current reading so do a dummy read to discard register contents first
    bme280.read()
    time.sleep(0.1)
    bme280_data = bme280.read()

    logging.debug("  - starting sensor")
    boost_enable_pin.value(True)
    sensor_enable_pin.value(True)
    logging.debug("  - wait 5 seconds for airflow")
    time.sleep(5) # allow airflow to start

    # setup the i2c bus for the particulate sensor
    logging.debug("  - taking pms5003i reading")
    
    # Reading from PMS5003 for particulate matter concentrations
    try:
        
        pm_data = pms5003.read()
        print(pm_data)
        print()
        print(dir(pm_data))
        pm1_0 = pm_data.pm_ug_per_m3(1.0)
        pm2_5 = pm_data.pm_ug_per_m3(2.5)
        pm10 = pm_data.pm_ug_per_m3(10)
    except Exception as e:
        print("PMS5003 read error:", e)
        pm1_0, pm2_5, pm10 = None, None, None

    sensor_enable_pin.value(False)
    boost_enable_pin.value(False)

    logging.debug("  - taking microphone reading")
    start = time.ticks_ms()
    min_value = 1.65
    max_value = 1.65
    while time.ticks_diff(time.ticks_ms(), start) < MIC_SAMPLE_TIME_MS:
        value = (noise_adc.read_u16() * 3.3) / 65535
        min_value = min(min_value, value)
        max_value = max(max_value, value)

    noise_vpp = max_value - min_value


    return {
      'temperature': round(temperature, 2),
      'humidity': round(humidity, 2),
      'pressure': round(pressure, 2),
      'gas_resistance': round(gas_resistance, 2),
      "luminance": round(ltr_data[BreakoutLTR559.LUX], 2),
      'proximity': round(ltr_data[BreakoutLTR559.PROXIMITY], 2),
      'noise_level': round(noise_vpp, 3),
      'pm1_0': pm1_0,
      'pm2_5': pm2_5,
      'pm10': pm10
    }

