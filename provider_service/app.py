import os
import time
import json
import pika
from flask import Flask
import logging

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
service_name = os.getenv('SERVICE_NAME', 'service2')
logger = logging.getLogger(service_name)

class RabbitMQServer:
    def __init__(self):
        self.host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
        self.connection = None
        self.channel = None
        self.connect()

    def connect(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.host)
        )
        self.channel = self.connection.channel()

        self.channel.queue_declare(
            queue='calculation_queue',
            arguments={'x-max-priority': 10}
        )

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue='calculation_queue',
            on_message_callback=self.process_request
        )

    def process_request(self, ch, method, props, body):
        start_time = time.time()

        # Отримання та додавання двох чисел
        numbers = json.loads(body)
        if len(numbers) != 2:
            result = {'error': 'Потрібно надати рівно два числа'}
        else:
            result = numbers[0] + numbers[1]

        calculation_time = time.time() - start_time
        logger.info(f'[{service_name}] Calculation completed in {calculation_time:.4f} seconds')

        # Відправка відповіді
        ch.basic_publish(
            exchange='',
            routing_key=props.reply_to,
            properties=pika.BasicProperties(
                correlation_id=props.correlation_id
            ),
            body=json.dumps({
                'result': result,
                'calculation_time': calculation_time
            })
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def run(self):
        print("Starting RabbitMQ consumer...")
        self.channel.start_consuming()

if __name__ == '__main__':
    server = RabbitMQServer()
    server.run()
