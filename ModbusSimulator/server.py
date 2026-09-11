import asyncio
import threading
import time

from pymodbus.datastore import ModbusServerContext
from pymodbus.server import StartAsyncTcpServer

from crah import CRAH
from power_meter import POWER_METER
from ths import THS


# Import a new equipment definition above, then add it to this list.
EQUIPMENT = [POWER_METER, CRAH, THS]
STEP_SECONDS = 0.5


def build_context() -> ModbusServerContext:
    slaves = {equipment.unit_id: equipment.make_context() for equipment in EQUIPMENT}
    if len(slaves) != len(EQUIPMENT):
        raise ValueError("Each equipment definition must have a unique unit_id")
    return ModbusServerContext(slaves=slaves, single=False)


def simulation_loop(context: ModbusServerContext) -> None:
    elapsed = 0.0

    while True:
        for equipment in EQUIPMENT:
            equipment.update(context[equipment.unit_id], elapsed)

        elapsed += STEP_SECONDS
        time.sleep(STEP_SECONDS)


async def main() -> None:
    context = build_context()
    simulation = threading.Thread(
        target=simulation_loop,
        args=(context,),
        daemon=True,
    )
    simulation.start()

    print("=" * 55)
    print("  Modbus Simulator")
    for equipment in EQUIPMENT:
        print(f"  Unit {equipment.unit_id}: {equipment.name} (port 502)")
    print("=" * 55)

    await StartAsyncTcpServer(context=context, address=("0.0.0.0", 502))


if __name__ == "__main__":
    asyncio.run(main())