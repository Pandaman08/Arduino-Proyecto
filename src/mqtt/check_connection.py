"""Comprobación explícita de EMQX: conexión, publicación y suscripción."""

import argparse
from datetime import datetime, timezone
import json
import logging
from threading import Event

from .client import MqttClient, MqttConnectionError
from .config import MqttSettings
from .topics import MqttTopics


def main() -> int:
    parser = argparse.ArgumentParser(description="Comprueba MQTT/WSS contra el broker configurado")
    parser.add_argument("--node-id", default="secador_01")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--publish-test", action="store_true", help="Publica solo en secado/<node>/test")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    settings = MqttSettings.from_env()
    if not settings.credentials_configured:
        logging.warning("MQTT_USERNAME/MQTT_PASSWORD no están configurados; se intentará conexión anónima y el broker puede rechazarla.")
    received = Event()
    client = MqttClient(settings)
    topics = MqttTopics(args.node_id)
    client.subscribe(topics.test, lambda *_args: received.set(), qos=1)
    try:
        status = client.start(wait_timeout=args.timeout)
        logging.info("Conexión verificada: %s", status.broker)
        if args.publish_test:
            payload = json.dumps({"node_id": args.node_id, "timestamp": datetime.now(timezone.utc).isoformat(), "test": True, "simulado": True, "version": "1.0"})
            client.publish(topics.test, payload, qos=1)
            logging.info("Publicación de prueba enviada a %s", topics.test)
            if received.wait(args.timeout):
                logging.info("Suscripción verificada: se recibió el mensaje de prueba")
            else:
                logging.warning("Publicación verificada, pero no se recibió eco en la suscripción")
        client.stop()
        return 0
    except MqttConnectionError as error:
        logging.error("Conexión MQTT no verificada: %s", error)
        client.stop()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
