from equipment import Coil, Equipment, Register, WritableRegister, sine


CRAH = Equipment(
    name="CRAH Unit",
    unit_id=2,
    zero_based=True,
    reverse_word_order=True,
    coils=[
        Coil(0, "Unit enabled", True),
        Coil(1, "Fan running", True),
        Coil(2, "Cooling active", True),
        Coil(3, "Common alarm"),
        Coil(4, "Dirty filter alarm"),
        Coil(5, "High return temperature alarm"),
        Coil(6, "Low supply temperature alarm"),
        Coil(7, "Fan fault"),
    ],
    writable_holding_registers=[
        WritableRegister(2, "Supply Air Temperature Setpoint", 58.0),
    ],
    holding_registers=[
        Register(0, "Fan Speed Command", sine(amplitude=5.0, period=60.0, offset=72.0)),
    ],
    input_registers=[
        Register(0, "Return Air Temperature", sine(amplitude=1.5, period=45.0, offset=78.0)),
        Register(2, "Supply Air Temperature", sine(amplitude=1.0, period=40.0, offset=58.0)),
        Register(4, "Return Air Humidity", sine(amplitude=2.0, period=55.0, offset=45.0)),
        Register(6, "Supply Air Humidity", sine(amplitude=2.0, period=50.0, offset=52.0)),
        Register(8, "Static Pressure", sine(amplitude=0.08, period=30.0, offset=1.5)),
        Register(10, "Fan Speed Feedback", sine(amplitude=4.8, period=60.0, offset=71.5)),
        Register(12, "Cooling Demand", sine(amplitude=8.0, period=70.0, offset=65.0)),
        Register(14, "CHW Valve Position", sine(amplitude=7.5, period=70.0, offset=64.0)),
        Register(16, "Entering CHW Temperature", sine(amplitude=0.7, period=65.0, offset=44.0)),
        Register(18, "Leaving CHW Temperature", sine(amplitude=1.0, period=65.0, offset=54.0)),
        Register(20, "Filter Differential Pressure", sine(amplitude=0.02, period=35.0, offset=0.35)),
        Register(22, "Cooling Capacity", sine(amplitude=10.0, period=70.0, offset=85.0)),
        Register(24, "Electrical Power", sine(amplitude=2.5, period=60.0, offset=22.0)),
    ],
)