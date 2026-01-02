

from django_redis import get_redis_connection

redis_conn = get_redis_connection("default")

ENV_PREFIX = "budgeting"  # Change this if you want a different namespace

def has_active_timer(user_id):
    """
    Returns True ONLY if timer is currently RUNNING
    """
    return redis_conn.exists(f"{ENV_PREFIX}:timer_start:{user_id}")

def set_active_timer(user_id, task_id, start_time):
    redis_conn.set(f"{ENV_PREFIX}:active_timer:{user_id}", task_id)
    redis_conn.set(f"{ENV_PREFIX}:timer_start:{user_id}", start_time.isoformat())

def clear_active_timer(user_id):
    redis_conn.delete(f"{ENV_PREFIX}:active_timer:{user_id}")
    redis_conn.delete(f"{ENV_PREFIX}:timer_start:{user_id}")

def get_active_timer(user_id):
    task_id = redis_conn.get(f"{ENV_PREFIX}:active_timer:{user_id}")
    start_time = redis_conn.get(f"{ENV_PREFIX}:timer_start:{user_id}")
    return task_id, start_time

def seconds_to_hms(total_seconds: int) -> dict:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
        "formatted": f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    }