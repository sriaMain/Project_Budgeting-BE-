from django.urls import path
from .consumers import TaskTimerConsumer

websocket_urlpatterns = [
    path("ws/timer/", TaskTimerConsumer.as_asgi()),
]
