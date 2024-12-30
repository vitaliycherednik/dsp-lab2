import os
import time
import json
import pika
import uuid
from flask import Flask, request, jsonify
import logging


app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
service_name = os.getenv('SERVICE_NAME', 'service1')
logger = logging.getLogger(service_name)

class RabbitMQClient:
    def __init__(self):
        self.host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
        self.connection = None
        self.channel = None
        self.callback_queue = None
        self.responses = {}
        self.connect()

    def connect(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.host)
        )
        self.channel = self.connection.channel()

        # Оголошення черги з пріоритетами
        self.channel.queue_declare(
            queue='calculation_queue',
            arguments={'x-max-priority': 10}
        )

        # Створення callback черги для request-reply паттерну
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True
        )

    def on_response(self, ch, method, props, body):
        self.responses[props.correlation_id] = body

    def call(self, numbers, priority=0):
        correlation_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key='calculation_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=correlation_id,
                priority=priority
            ),
            body=json.dumps(numbers)
        )

        while correlation_id not in self.responses:
            self.connection.process_data_events()
        return json.loads(self.responses.pop(correlation_id))

rabbitmq_client = RabbitMQClient()

# Асинхронний запит
@app.route('/calculate/async', methods=['POST'])
def calculate_async():
    start_time = time.time()
    data = request.json

    # Перевірка наявності обох чисел
    num1 = data.get('num1')
    num2 = data.get('num2')
    if num1 is None or num2 is None:
        return jsonify({'error': 'Потрібно надати обидва числа (num1 та num2)'}), 400

    numbers = [num1, num2]
    priority = data.get('priority', 0)

    # Відправка асинхронного запиту
    result = rabbitmq_client.call(numbers, priority)

    execution_time = time.time() - start_time
    logger.info(f'[{service_name}] Async request completed in {execution_time:.4f} seconds')

    return jsonify({
        'result': result['result'],
        'calculation_time': result['calculation_time'],
        'request_time': execution_time
    })

# Синхронний запит
@app.route('/calculate/sync', methods=['POST'])
def calculate_sync():
    start_time = time.time()
    data = request.json

    # Перевірка наявності обох чисел
    num1 = data.get('num1')
    num2 = data.get('num2')
    if num1 is None or num2 is None:
        return jsonify({'error': 'Потрібно надати обидва числа (num1 та num2)'}), 400

    result = num1 + num2

    execution_time = time.time() - start_time
    logger.info(f'Sync request completed in {execution_time:.4f} seconds')

    return jsonify({
        'result': result,
        'request_time': execution_time
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
