from enviro import logging
from enviro.constants import *
import urequests
import config
import time


def log_destination():
    logging.info(
        f"> uploading cached readings to Adafruit.io: {config.adafruit_io_username}"
    )

def check_group_exists_or_create():
    url = f"http://io.adafruit.com/api/v2/{config.adafruit_io_username}/groups"
    headers = {
        "X-AIO-Key": config.adafruit_io_key,
        "Content-Type": "application/json",
    }
    payload = {
        "name": config.adafruit_io_group_name,
    }
    logging.debug(f"creating group using url {url} with payload:\n{payload}")
    try:
        result = urequests.post(url, json=payload, headers=headers)
        error_message = ""
        try:
            error_message = result.json()["error"]  # an array of errors
            if "Name has already been taken" in error_message or "Key has already been taken" in error_message:
                logging.info(f"Group with key '{config.adafruit_io_group_name}' already exists")
                return False
            if not error_message in ("", None, []):
                logging.error(
                    f"An error occurred with the group creation request: {error_message}"
                )
                return False
        except (TypeError, KeyError, ValueError) as ve:
            logging.warn(f"found issue creating group: {ve}")
        
        result.close()
        logging.info(f"Group '{config.adafruit_io_group_name}' created and saved to config")
        return True
    except Exception as exc:
        import sys, io

        buf = io.StringIO()
        sys.print_exception(exc, buf)
        logging.debug(f"  - an exception occurred when creating group.", buf.getvalue())
        return False


def fetch_time(synch_with_rtc=True, timeout=15, retry=True):
    timestamp = None
    try:
        # People might like to use tzinfo related things in RTC and datetime, but everything UTC for now
        url = f"http://io.adafruit.com/api/v2/{config.adafruit_io_username}/integrations/time/struct?tz=UTC"
        headers = {
            "X-AIO-Key": config.adafruit_io_key,
            "Content-Type": "application/json",
        }

        try:
            result = urequests.get(url, headers=headers, timeout=timeout)

            error_message = ""
            try:
                timestamp = result.json()
                # e.g.
                # {
                #   "year": 2019,
                #   "mon": 12,
                #   "mday": 2,
                #   "hour": 18,
                #   "min": 20,
                #   "sec": 37,
                #   "wday": 3,
                #   "yday": 336,
                #   "isdst": 0
                # }
                error_message = timestamp["error"]
                if error_message != "":
                    logging.error(
                        f"An error occurred with the time service request: {error_message}"
                    )
            except (TypeError, KeyError):
                pass

            result.close()

            if result.status_code != 200:
                logging.debug(
                    f"  - fetch issue '{error_message}' ({result.status_code} - {result.reason.decode('utf-8')}):"
                )
                logging.debug(f" {url} returned {timestamp}")
                # todo: if throttled or ignored or other error then wait 3seconds and try again
                if retry:
                    time.sleep(3)
                    return fetch_time(synch_with_rtc, timeout, retry=False)

        except Exception as exc:
            import sys, io

            buf = io.StringIO()
            sys.print_exception(exc, buf)
            logging.debug(
                f"  - an exception occurred when fetching time from Adafruit.io: {buf.getvalue()}"
            )
            return None

    except Exception as exc:
        import sys, io

        buf = io.StringIO()
        sys.print_exception(exc, buf)
        logging.debug(
            f"  - an exception occurred when fetching time from Adafruit.io: {buf.getvalue()}"
        )
        return None
    logging.debug(f"timestamp:{timestamp}")
    # if requested set the machines RTC to the fetched timestamp
    if synch_with_rtc:
        import machine

        machine.RTC().datetime(
            (
                timestamp["year"],
                timestamp["mon"],
                timestamp["mday"],
                timestamp["wday"],
                timestamp["hour"],
                timestamp["min"],
                timestamp["sec"],
                0,  # subseconds
            )
        )

    # return a localtime formatted timestamp
    return time.gmtime(
        time.mktime(
            (
                timestamp["year"],
                timestamp["mon"],
                timestamp["mday"],
                timestamp["hour"],
                timestamp["min"],
                timestamp["sec"],
                timestamp["wday"],
                timestamp["yday"],
            )
        )
    )


def upload_reading(reading):
    group_name = config.adafruit_io_group_name
    username = config.adafruit_io_username

    # create adafruit.io payload format
    payload = {"created_at": reading["timestamp"], "feeds": []}

    # add all the sensor readings
    nickname = config.nickname
    for key, value in reading["readings"].items():
        key = key.replace("_", "-")
        payload["feeds"].append({"key": f"{nickname}-{key}", "value": value})

    # send the payload
    headers = {"X-AIO-Key": config.adafruit_io_key, "Content-Type": "application/json"}
    url = f"http://io.adafruit.com/api/v2/{username}/groups/{group_name}/data"

    try:
        result = urequests.post(url, json=payload, headers=headers)

        error_message = ""
        try:
            error_message = result.json()["error"]
        except (TypeError, KeyError):
            pass
        except(ValueError, OSError) as esc:
            logging.debug(f"  - upload issue '{esc}' - response text: '{result.text}'")
            return UPLOAD_FAILED

        result.close()
        if result.status_code == 429:
            return UPLOAD_RATE_LIMITED

        if result.status_code == 200:
            return UPLOAD_SUCCESS

        if result.status_code in (400, 404):  # bad request / group not found
            if error_message.find("not found - There is no feed with the key"):
                logging.debug(
                    f"  - upload issue '{error_message}' - Possibly missing group '{group_name}' - will attempt to create it"
                )
                try:
                    if check_group_exists_or_create():
                        return upload_reading(reading)
                    else:
                        return UPLOAD_FAILED
                except Exception as exc:
                    logging.debug(
                        f"  - an exception occurred when creating group.", exc
                    )
                    logging.debug(
                        f"  - original upload issue '{error_message}' (HTTP Status 404 - {result.reason.decode('utf-8')}\n  - Original URL:{url})"
                    )
            return UPLOAD_FAILED

        if result.status_code == 422:
            if error_message.find("data created_at may not be in the future") == 0:
                return UPLOAD_LOST_SYNC

            logging.debug(
                f"  - upload issue '{error_message}' - You may have run out of feeds to upload data to"
            )
            return UPLOAD_SKIP_FILE

        logging.debug(
            f"  - upload issue '{error_message}' ({result.status_code} - {result.reason.decode('utf-8')})"
        )

    except Exception as exc:
        import sys, io

        buf = io.StringIO()
        sys.print_exception(exc, buf)
        logging.debug(f"  - an exception occurred when uploading.", buf.getvalue())

    return UPLOAD_FAILED
