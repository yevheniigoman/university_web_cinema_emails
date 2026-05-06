import os
import sys
import json
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass
import pika
from pika.adapters.blocking_connection import BlockingChannel

import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


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
    user_email: str


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
    return TicketDto(show, seat, purchased_at=body_dict["purchasedAt"],
                     user_email=body_dict.get("userEmail", "zelinskyi.andrii@lll.kpi.ua"))


def build_email_html(ticket: TicketDto) -> str:
    movie = ticket.show.movie
    return f"""
    <html><body style="font-family: Arial, sans-serif; color: #333;">
      <h2>Ваш квиток придбано!</h2>
      <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
        <tr><td><b>Фільм</b></td><td>{movie.title}</td></tr>
        <tr><td><b>Опис</b></td><td>{movie.description}</td></tr>
        <tr><td><b>Тривалість</b></td><td>{movie.minutes} хв</td></tr>
        <tr><td><b>Початок сеансу</b></td><td>{ticket.show.start_time.strftime("%d.%m.%Y %H:%M")}</td></tr>
        <tr><td><b>Ціна</b></td><td>{ticket.show.price} грн</td></tr>
        <tr><td><b>Ряд / Місце</b></td><td>{ticket.seat.row} / {ticket.seat.place}</td></tr>
        <tr><td><b>Придбано</b></td><td>{ticket.purchased_at}</td></tr>
      </table>
      <p>Дякуємо за покупку! Приємного перегляду!</p>
    </body></html>
    """


def send_email(channel: BlockingChannel, method, properties, body: bytes) -> None:
    ticket = parse_message_body(body.decode())

    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Квиток на фільм «{ticket.show.movie.title}»"
    msg["From"] = smtp_user
    msg["To"] = ticket.user_email
    msg.attach(MIMEText(build_email_html(ticket), "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, ticket.user_email, msg.as_string())

    print(f"[✓] Email надіслано на {ticket.user_email}")
    channel.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    username = os.environ.get("RABBITMQ_DEFAULT_USER", "guest")
    password = os.environ.get("RABBITMQ_DEFAULT_PASS", "guest")
    credentials = pika.PlainCredentials(username, password)
    conn_params = pika.ConnectionParameters(host="rabbitmq", credentials=credentials)

    # Чекаємо поки RabbitMQ підніметься
    while True:
        try:
            conn = pika.BlockingConnection(conn_params)
            break
        except Exception as e:
            print(f"RabbitMQ недоступний, чекаємо 5 секунд... ({e})")
            time.sleep(5)

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
