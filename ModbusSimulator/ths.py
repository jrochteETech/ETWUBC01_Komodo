from equipment import Coil, Equipment, Register, sine


THS = Equipment(
    name="THS Gateway",
    unit_id=3,
    zero_based=True,
    reverse_word_order=False,
    datastore_size=256,
    coils=[
        Coil(0, "Sensor enabled", True),
        Coil(1, "Battery Low"),

        Coil(100, "Sensor enabled", True),
        Coil(101, "Battery Low"),

        Coil(200, "Sensor enabled", True),
        Coil(201, "Battery Low"),
    ],
    holding_registers=[
        Register(0, "Battery Low Setpoint", sine(amplitude=5.0, period=60.0, offset=3.2)),

        Register(100, "Battery Low Setpoint", sine(amplitude=5.0, period=60.0, offset=3.2)),

        Register(200, "Battery Low Setpoint", sine(amplitude=5.0, period=60.0, offset=3.2)),
    ],
    input_registers=[
        Register(0, "Temperature", sine(amplitude=1.5, period=45.0, offset=70.0)),
        Register(2, "Humidity", sine(amplitude=1.0, period=40.0, offset=52.0)),
        Register(4, "Battery Voltage", sine(amplitude=0.5, period=55.0, offset=3.5)),
        Register(6, "Signal Strength", sine(amplitude=10.0, period=50.0, offset=75.0)),

        Register(100, "Temperature", sine(amplitude=1.5, period=45.0, offset=71.0)),
        Register(102, "Humidity", sine(amplitude=1.0, period=40.0, offset=52.5)),
        Register(104, "Battery Voltage", sine(amplitude=0.5, period=55.0, offset=3.6)),
        Register(106, "Signal Strength", sine(amplitude=10.0, period=50.0, offset=80.0)),

        Register(200, "Temperature", sine(amplitude=1.5, period=45.0, offset=72.0)),
        Register(202, "Humidity", sine(amplitude=1.0, period=40.0, offset=53.0)),
        Register(204, "Battery Voltage", sine(amplitude=0.5, period=55.0, offset=3.7)),
        Register(206, "Signal Strength", sine(amplitude=10.0, period=50.0, offset=85.0)),
    ],
)