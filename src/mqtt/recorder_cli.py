"""CLI del registrador MQTT → SQLite."""

import argparse
import logging
import os
from threading import Event

from ..persistence import ExperimentManager, MeasurementRepository, SQLiteDatabase, initialize_schema
from .client import MqttClient
from .config import MqttSettings
from .recorder import MqttTelemetryRecorder


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarda telemetría MQTT válida en SQLite")
    parser.add_argument("--experiment-id", type=int, required=True)
    parser.add_argument("--node-id", default=os.getenv("MQTT_NODE_ID", "secador_01"))
    parser.add_argument("--topic-filter", default=os.getenv("MQTT_TELEMETRY_TOPIC", "secado/+/telemetria"))
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    database = SQLiteDatabase()
    initialize_schema(database)
    recorder = MqttTelemetryRecorder(
        MqttClient(MqttSettings.from_env()),
        MeasurementRepository(database),
        ExperimentManager(database),
        {args.node_id: args.experiment_id},
    )
    try:
        recorder.start(args.topic_filter)
        logging.info("Registrador activo; escuchando %s para %s", args.topic_filter, args.node_id)
        Event().wait()
    except KeyboardInterrupt:
        logging.info("Deteniendo registrador")
    finally:
        recorder.stop()


if __name__ == "__main__":
    main()
