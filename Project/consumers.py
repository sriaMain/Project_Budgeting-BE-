
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
import jwt

from accounts.models import Account
from Project.models import TaskTimerLog
from .redis_utils import (
    get_active_timer,
    set_active_timer,
    clear_active_timer
)
from .utils import format_seconds


class TaskTimerConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        query_string = self.scope["query_string"].decode()
        token = None

        if "token=" in query_string:
            token = query_string.split("token=")[-1].split("&")[0]

        if not token:
            await self.close(code=4001)
            return

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            self.user = await Account.objects.aget(id=user_id)
        except Exception:
            await self.close(code=4001)
            return

        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Guard: disconnect can fire even if connect failed early
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Override to handle both text and binary frames"""
        if text_data:
            await super().receive(text_data=text_data)
        # Ignore binary/ping/pong frames silently

    async def timer_event(self, event):
        """Handle timer_event messages from the channel layer"""
        await self.send_json(event.get("data", event))

    async def receive_json(self, content, **kwargs):
        action = content.get("action")

        if action == "start":
            await self.start_timer(content)

        elif action == "pause":
            await self.pause_timer()


    async def start_timer(self, content):
        task_id, start_time = get_active_timer(self.user.id)

        if task_id:
            await self.send_json({
                "status": "already_running",
                "running_task_id": int(task_id),
                "started_at": start_time.decode(),
                "running": True,
            })
            return

        new_task_id = int(content.get("task_id"))
        now = timezone.now()

        set_active_timer(self.user.id, new_task_id, now)

        total_seconds = await self.get_previous_seconds(new_task_id)

        await self.send_json({
            "event": "TIMER_STARTED",
            "task_id": new_task_id,
            "total_seconds": total_seconds,
            "session_seconds": 0,
            "formatted_time": format_seconds(total_seconds),
            "running": True,
            "started_at": now.isoformat(),
        })



    async def pause_timer(self):
        task_id, start_time = get_active_timer(self.user.id)

        if not task_id or not start_time:
            await self.send_json({
                "status": "not_running",
                "running": False
            })
            return

        task_id = int(task_id)
        start_time = timezone.datetime.fromisoformat(start_time.decode())
        end_time = timezone.now()

        session_seconds = int((end_time - start_time).total_seconds())

        await sync_to_async(TaskTimerLog.objects.create)(
            task_id=task_id,
            user=self.user,
            start_time=start_time,
            end_time=end_time,
            is_active=False
        )

        clear_active_timer(self.user.id)

        total_seconds = await self.get_previous_seconds(task_id)

        await self.send_json({
            "event": "TIMER_PAUSED",
            "task_id": task_id,
            "total_seconds": total_seconds,
            "session_seconds": session_seconds,
            "formatted_time": format_seconds(total_seconds),
            "running": False,
            "started_at": None,
        })



    async def get_previous_seconds(self, task_id):
        logs = await sync_to_async(list)(
            TaskTimerLog.objects.filter(
                task_id=task_id,
                user=self.user,
                is_active=False
            )
        )

        return sum(
            int((log.end_time - log.start_time).total_seconds())
            for log in logs
            if log.start_time and log.end_time
        )
