import pytz
from datetime import datetime

class Helpers:
  def convert_to_indian_standard_time(self, dt: datetime) -> datetime:
    return dt.astimezone(pytz.timezone('Asia/Kolkata'))

  def convert_to_utc(self, dt: datetime) -> datetime:
    return dt.astimezone(pytz.timezone('UTC'))

  def get_current_ist_for_db(self) -> datetime:
    """
    Returns current time in IST but as a naive datetime (no timezone info)
    for storage in database columns defined as TIMESTAMP WITHOUT TIME ZONE
    """
    ist_time = datetime.utcnow().astimezone(pytz.timezone('Asia/Kolkata'))
    return ist_time.replace(tzinfo=None)  # Strip timezone info for DB storage

helpers = Helpers()
