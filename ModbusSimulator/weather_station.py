from equipment import Coil, Equipment, Register, dew_point_fahrenheit, linear, sine


TEMPERATURE = sine(amplitude=12.0, period=240.0, offset=70.0)
HUMIDITY = sine(amplitude=-15.0, period=240.0, offset=60.0)


WEATHER_STATION = Equipment(
    name="Outdoor Weather Station",
    unit_id=4,
    coils=[
        Coil(0, "Station healthy", True),
    ],
    input_registers=[
        Register(0, "Outdoor Temperature", TEMPERATURE),
        Register(2, "Relative Humidity", HUMIDITY),
        Register(4, "Wind Speed", sine(amplitude=5.0, period=45.0, offset=8.0)),
        Register(6, "Wind Direction", linear(duration=180.0, start=0.0, end=360.0)),
        Register(8, "Dew Point", dew_point_fahrenheit(TEMPERATURE, HUMIDITY)),
    ],
)