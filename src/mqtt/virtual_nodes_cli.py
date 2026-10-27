"""CLI de los cuatro nodos virtuales sim1..sim4."""

import argparse
import logging
import os

from .client import MqttClient
from .config import MqttSettings
from .virtual_nodes import VirtualNode, VirtualNodePublisher, default_virtual_nodes


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica telemetría simulada en sim1..sim4")
    parser.add_argument("--interval", type=float, default=float(os.getenv("SIM_INTERVAL_SECONDS", "2")))
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    publisher = VirtualNodePublisher(MqttClient(MqttSettings.from_env()), default_virtual_nodes())
    try:
        publisher.start()
        publisher.run_forever(args.interval)
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Deteniendo nodos virtuales")
    finally:
        publisher.stop()


if __name__ == "__main__":
    main()
