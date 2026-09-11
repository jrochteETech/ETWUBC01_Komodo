from equipment import Coil, Equipment, Register, linear, sine


POWER_METER = Equipment(
    name="Three-phase Power Meter",
    unit_id=1,
    zero_based=False,
    coils=[
        Coil(1, "Meter healthy", True),
    ],
    input_registers=[
        Register(1, "Voltage L1", sine(amplitude=2.0, period=12.0, offset=277.0)),
        Register(3, "Voltage L2", sine(amplitude=1.8, period=13.0, offset=277.5)),
        Register(5, "Voltage L3", sine(amplitude=2.2, period=11.0, offset=276.5)),
        Register(7, "Current L1", sine(amplitude=3.5, period=18.0, offset=42.0)),
        Register(9, "Current L2", sine(amplitude=3.0, period=20.0, offset=40.0)),
        Register(11, "Current L3", sine(amplitude=4.0, period=22.0, offset=44.0)),
        Register(13, "Active Power", sine(amplitude=3.0, period=20.0, offset=33.7)),
        Register(15, "Reactive Power", sine(amplitude=1.0, period=24.0, offset=9.1)),
        Register(17, "Apparent Power", sine(amplitude=3.1, period=20.0, offset=34.9)),
        Register(19, "Power Factor", sine(amplitude=0.015, period=30.0, offset=0.965)),
        Register(21, "Frequency", sine(amplitude=0.04, period=15.0, offset=60.0)),
        Register(23, "Energy Import", linear(duration=86400.0, start=250.0, end=1059.0)),
        Register(25, "Voltage L1-L2", sine(amplitude=3.0, period=12.5, offset=480.0)),
        Register(27, "Voltage L2-L3", sine(amplitude=3.2, period=13.5, offset=480.5)),
        Register(29, "Voltage L3-L1", sine(amplitude=3.1, period=11.5, offset=479.5)),
    ],
)