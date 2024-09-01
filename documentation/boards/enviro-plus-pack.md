
# Pico Enviro+ Pack

A fully featured environmental monitoring / citizen science add-on for Raspberry Pi Pico and Pico W. It has a built-in colour 1.54" LCD screen and is jam-packed with sensors!

## Readings

|Name|Parameter|Unit|Symbol|Example|
|---|---|---|---|---|
|Temperature|`temperature`|Celsius|°C|`22.11`|
|Humidity|`humidity`|percent|%|`55.42`|
|Air Pressure|`pressure`|hectopascals|hPa|`997.16`|
|Gas Resistance|`gas_resistance`|ohms|Ω|`36551`|
|Light Level|`light_level`|lux|lx|`35`|
|Ambient Noise|`ambient_noise`|decibels|dB|`30`|
|*PM1|`pm1`|micrograms per cubic metre|µg/m³|`9`|
|*PM2.5|`pm2_5`|micrograms per cubic metre|µg/m³|`4`|
|*PM10|`pm10`|micrograms per cubic metre|µg/m³|`2`|

## On-board Devices

- BME688 4-in-1 temperature, pressure, humidity, and gas sensor. [View datasheet](https://cdn.shopify.com/s/files/1/0174/1800/files/bst-bme688-ds000.pdf?v=1620834794)
- LTR-559 light and proximity sensor. [View datasheet](https://www.mouser.co.uk/datasheet/2/239/Lite-On_LTR-559ALS-01_DS_V1-239345.pdf)
- MEMS microphone. [View datasheet](https://www.invensense.com/products/microphones/ics-43434/)
- 1.54" 240x240 IPS LCD (connected via SPI).
- Connector for *optional PMS5003 Particulate sensor [View datasheet](http://www.aqmd.gov/docs/default-source/aq-spec/resources-page/plantower-pms5003-manual_v2-3.pdf)

## Power

The Pico Enviro+ Pack is powered directly through the Raspberry Pi Pico via the USB connector. There are no external power connectors.

## Additional Information

The Pico Enviro+ Pack is designed to plug into the back of a Raspberry Pi Pico or Pico W, with pre-soldered socket headers for easy attachment. It features a connector for particulate matter (PM) sensor (sold separately), enhancing its capabilities for air quality monitoring.
