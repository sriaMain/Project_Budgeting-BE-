
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import jwt
from django.conf import settings
from accounts.models import Account
from .redis_utils import get_active_timer, set_active_timer

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

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action == "start":
            # Check if a timer is already running for this user
            task_id, start_time = get_active_timer(self.user.id)
            if task_id:
                # There is already a running timer
                await self.send_json({
                    "status": "already_running",
                    "message": "Another timer is already running.",
                    "running_task_id": task_id.decode() if hasattr(task_id, 'decode') else str(task_id),
                    "started_at": start_time.decode() if hasattr(start_time, 'decode') else str(start_time),
                })
                return
            # No timer running, start a new one
            new_task_id = content.get("task_id")
            from datetime import datetime
            now = datetime.utcnow()
            set_active_timer(self.user.id, new_task_id, now)
            await self.send_json({
                "status": "started",
                "message": f"Timer started for task {new_task_id}.",
                "task_id": new_task_id,
                "started_at": now.isoformat() + "Z",
            })
