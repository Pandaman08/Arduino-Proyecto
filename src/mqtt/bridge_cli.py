"""CLI del puente Arduino Nano ↔ EMQX."""

import argparse
import logging
import os

from ..config import DEFAULT_BAUDRATE
from ..persistence import ExperimentManager, MeasurementRepository, SQLiteDatabase, initialize_schema
from ..hardware.serial_manager import SerialManager
from .bridge import SerialMqttBridge
from .client import MqttClient
from .config import MqttSettings


def main() -> None:
    parser = argparse.ArgumentParser(description="Puente Arduino Nano USB/Serial hacia EMQX MQTT")
    parser.add_argument("--port", default=os.getenv("SERIAL_PORT", "/dev/ttyUSB0"))
    parser.add_argument("--baudrate", type=int, default=int(os.getenv("SERIAL_BAUDRATE", DEFAULT_BAUDRATE)))
    parser.add_argument("--node-id", default=os.getenv("MQTT_NODE_ID", "secador_01"))
    parser.add_argument("--experiment-id", type=int, default=int(os.getenv("EXPERIMENT_ID", "0")) or None)
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    database = SQLiteDatabase()
    initialize_schema(database)
    bridge = SerialMqttBridge(
        serial_manager=SerialManager(args.port, args.baudrate),
        mqtt_client=MqttClient(MqttSettings.from_env()),
        node_id=args.node_id,
        measurement_repository=MeasurementRepository(database) if args.experiment_id else None,
        experiment_manager=ExperimentManager(database) if args.experiment_id else None,
        experiment_id=args.experiment_id,
    )
    try:
        bridge.start()
        bridge.run_forever()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Deteniendo puente")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
