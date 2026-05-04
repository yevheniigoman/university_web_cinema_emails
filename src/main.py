import os
import sys
import json
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass
import pika
from pika.adapters.blocking_connection import BlockingChannel


@dataclass
class MovieDto:
    title: str
    description: str
    minutes: int
    genre_id: int

@dataclass
class ShowDto:
    movie: MovieDto
    start_time: datetime
    price: Decimal

@dataclass
class SeatDto:
    row: int
    place: int

@dataclass
class TicketDto:
    show: ShowDto
    seat: SeatDto
    purchased_at: datetime


def parse_message_body(body: str) -> TicketDto:
    body_dict = json.loads(body)

    show_dict = body_dict["show"]
    movie_dict = show_dict["movie"]
    movie = MovieDto(
        movie_dict["title"],
        movie_dict["description"],
        movie_dict["minutes"],
        movie_dict["genreId"]
    )
    start_time = datetime.fromisoformat(show_dict["startTime"])
    show = ShowDto(movie, start_time, show_dict["price"])

    seat_dict = body_dict["seat"]
    seat = SeatDto(seat_dict["row"], seat_dict["place"])
    return TicketDto(show, seat, body_dict["purchasedAt"])


def send_email(channel: BlockingChannel, method, properties, body: bytes) -> None:
    ticket = parse_message_body(body.decode())
    with open("logs.txt", "w") as file:
        file.write(str(ticket))
    channel.basic_ack(delivery_tag=method.delivery_tag)

def main() -> None:
    username = os.environ.get("RABBITMQ_DEFAULT_USER", "guest")
    password = os.environ.get("RABBITMQ_DEFAULT_PASS", "guest")

    credentials = pika.PlainCredentials(username, password)
    conn_params = pika.ConnectionParameters(host="rabbitmq", credentials=credentials)
    conn = pika.BlockingConnection(conn_params)
    channel = conn.channel()
    channel.queue_declare(queue="tickets", durable=True)
    channel.basic_consume(queue="tickets", on_message_callback=send_email)

    print("Waiting for messages. To exit press Ctrl+C")
    channel.start_consuming()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)