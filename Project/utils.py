from datetime import timedelta

def get_week_range(date):
    """Return the week range as Sunday (start) to Saturday (end)."""
    # Python weekday(): Monday=0 ... Sunday=6
    # To get the Sunday of the current week:
    sunday = date - timedelta(days=(date.weekday() + 1) % 7)
    saturday = sunday + timedelta(days=6)
    return sunday, saturday


from django_redis import get_redis_connection

redis_conn = get_redis_connection("default")

def get_active_timer(user_id):
    task_id = redis_conn.get(f"active_timer:{user_id}")
    start_time = redis_conn.get(f"timer_start:{user_id}")
    return task_id, start_time

def set_active_timer(user_id, task_id, start_time):
    redis_conn.set(f"active_timer:{user_id}", task_id)
    redis_conn.set(f"timer_start:{user_id}", start_time.isoformat())

def clear_active_timer(user_id):
    redis_conn.delete(f"active_timer:{user_id}")
    redis_conn.delete(f"timer_start:{user_id}")


def format_seconds(seconds):
    """Convert seconds to formatted time object with breakdown"""
    if not isinstance(seconds, (int, float)):
        return {
            "hours": 0,
            "minutes": 0,
            "seconds": 0,
            "formatted": "00:00:00"
        }
    
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": secs,
        "formatted": f"{hours:02d}:{minutes:02d}:{secs:02d}"
    }
