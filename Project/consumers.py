from channels.generic.websocket import AsyncJsonWebsocketConsumer
import jwt
from django.conf import settings
from accounts.models import Account

class TaskTimerConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        # Extract token from query string
        query_string = self.scope['query_string'].decode()
        token = None
        if 'token=' in query_string:
            token = query_string.split('token=')[-1].split('&')[0]
        user = None

        if token:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                user_id = payload.get("user_id")
                user = await Account.objects.aget(id=user_id)
            except Exception as e:
                print(f"JWT error: {e}")

        if not user:
            await self.close(code=4001)
            return

        self.user = user
        self.group_name = f"user_{self.user.id}"
        print(f"WebSocket connect: user={self.user}, group_name={self.group_name}")
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

    async def timer_event(self, event):
        print(f"WebSocket timer_event: group_name={self.group_name}, event={event}")
        await self.send_json(event["data"])
