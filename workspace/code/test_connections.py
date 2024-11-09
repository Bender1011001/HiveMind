import pika
import pymongo
import sys

def test_mongodb():
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017/")
        db = client.admin
        server_info = db.command("serverStatus")
        print("✓ MongoDB connection successful")
        return True
    except Exception as e:
        print("✗ MongoDB connection failed:", str(e))
        return False

def test_rabbitmq():
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='localhost', port=5672)
        )
        channel = connection.channel()
        print("✓ RabbitMQ connection successful")
        connection.close()
        return True
    except Exception as e:
        print("✗ RabbitMQ connection failed:", str(e))
        return False

if __name__ == "__main__":
    mongodb_ok = test_mongodb()
    rabbitmq_ok = test_rabbitmq()

    if not (mongodb_ok and rabbitmq_ok):
        sys.exit(1)
