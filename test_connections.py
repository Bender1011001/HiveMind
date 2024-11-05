import pymongo
import pika
import sys

def test_mongodb():
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017/")
        db = client.admin
        server_info = db.command("serverStatus")
        print("MongoDB connection successful")
        client.close()
        return True
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return False

def test_rabbitmq():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        print("RabbitMQ connection successful")
        connection.close()
        return True
    except Exception as e:
        print(f"RabbitMQ connection failed: {e}")
        return False

if __name__ == "__main__":
    mongodb_ok = test_mongodb()
    rabbitmq_ok = test_rabbitmq()
    
    if mongodb_ok and rabbitmq_ok:
        print("\nAll connections successful!")
        sys.exit(0)
    else:
        print("\nSome connections failed!")
        sys.exit(1)
