import datetime
import json
import zoneinfo
from enum import Enum
from typing import List

from dateutil import relativedelta
from dateutil.parser import parse
from fastapi import FastAPI
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from handler.agents_for_bedrock import AgentsForBedrock
from mangum import Mangum
from pydantic import BaseModel, Field

app = FastAPI()

calendar_id = ""

zone_name = "Asia/Tokyo"
timezone = zoneinfo.ZoneInfo(zone_name)


def get_googpeapi_service():
    import boto3

    ssm_client = boto3.client("ssm")
    parameter_name = "/hotel-booking-agents/token.json"
    token = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
    token = token["Parameter"]["Value"]

    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    creds = None
    creds = Credentials.from_authorized_user_info(json.loads(token), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            ssm_client.put_parameter(
                Name=parameter_name, Value=creds.to_json(), Overwrite=True
            )

    return build("calendar", "v3", credentials=creds)


service = get_googpeapi_service()


class reserve_req(BaseModel):
    reservation_holder: str = Field(description="予約する人の名前")
    checkin: datetime.date | str = Field(description="チェックイン日")
    checkout: datetime.date | str = Field(description="チェックアウト日")


class reserve_res(BaseModel):
    reserve_id: str = Field(description="予約ID")
    reservation_holder: str = Field(description="予約した人の名前")
    checkin: datetime.date = Field(description="チェックイン日")
    checkout: datetime.date = Field(description="チェックアウト日")


@app.post("/reserve", description="予約を行うAPI")
def reserve(request: reserve_req) -> reserve_res:
    now = datetime.datetime.now(timezone)
    checkin = parse(request.checkin)
    checkout = parse(request.checkout)

    # 2023/12/28に1/1をパースすると、2023/1/1になるので、2024/1/1になるように調整
    if checkin.astimezone(timezone) < now:
        checkin = checkin + relativedelta.relativedelta(years=1)
    if checkout.astimezone(timezone) < now:
        checkout = checkout + relativedelta.relativedelta(years=1)

    checkin = datetime.datetime(
        checkin.year, checkin.month, checkin.day, 18, 0, 0, tzinfo=timezone
    )

    checkout = datetime.datetime(
        checkout.year, checkout.month, checkout.day, 10, 0, 0, tzinfo=timezone
    )

    description = {"reservation_holder": request.reservation_holder}

    event = {
        "summary": "hotel booking (Agents for Amazon Bedrock)",
        "description": json.dumps(description, ensure_ascii=False),
        "start": {
            "dateTime": checkin.isoformat(),
            "timeZone": zone_name,
        },
        "end": {
            "dateTime": checkout.isoformat(),
            "timeZone": zone_name,
        },
    }

    event = service.events().insert(calendarId=calendar_id, body=event).execute()

    return reserve_res(
        reserve_id=event["id"],
        reservation_holder=request.reservation_holder,
        checkin=datetime.datetime.strptime(
            event["start"]["dateTime"], "%Y-%m-%dT%H:%M:%S%z"
        ).date(),
        checkout=datetime.datetime.strptime(
            event["end"]["dateTime"], "%Y-%m-%dT%H:%M:%S%z"
        ).date(),
    )


class is_vacancy_req(BaseModel):
    checkin: datetime.date | str = Field(description="チェックイン日")
    checkout: datetime.date | str = Field(description="チェックアウト日")


@app.post("/is_vacancy", description="予約可能かどうかを判定するAPI")
def is_vacancy(request: is_vacancy_req) -> bool:
    now = datetime.datetime.now(timezone)
    checkin = parse(request.checkin)
    checkout = parse(request.checkout)

    # 2023/12/28に1/1をパースすると、2023/1/1になるので、2024/1/1になるように調整
    if checkin.astimezone(timezone) < now:
        checkin = checkin + relativedelta.relativedelta(years=1)
    if checkout.astimezone(timezone) < now:
        checkout = checkout + relativedelta.relativedelta(years=1)

    checkin = datetime.datetime(
        checkin.year, checkin.month, checkin.day, 18, 0, 0, tzinfo=timezone
    )

    checkout = datetime.datetime(
        checkout.year, checkout.month, checkout.day, 10, 0, 0, tzinfo=timezone
    )

    events = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=checkin.isoformat(),
            timeMax=checkout.isoformat(),
        )
        .execute()
    )

    return len(events["items"]) == 0


@app.get("/get_today", description="処理当日の日付が取得できます")
def get_today() -> str:
    now = datetime.datetime.now(timezone)
    return now.strftime("%Y/%m/%d")


class get_my_reservation_req(BaseModel):
    reservation_holder: str = Field(description="予約した人の名前")


class get_my_reservation_res(BaseModel):
    reservations: List[reserve_res] = Field(description="予約した人の予約情報")


@app.post("/get_my_reservation", description="自分の予約を取得するAPI")
def get_my_reservation(request: get_my_reservation_req) -> get_my_reservation_res:
    reservation_holder = request.reservation_holder

    events = (
        service.events()
        .list(
            calendarId=calendar_id,
            q=f'"reservation_holder": "{reservation_holder}"',
        )
        .execute()
    )

    return {
        "reservations": list(
            map(
                lambda x: reserve_res(
                    reserve_id=x["id"],
                    reservation_holder=request.reservation_holder,
                    checkin=datetime.datetime.strptime(
                        x["start"]["dateTime"], "%Y-%m-%dT%H:%M:%S%z"
                    ).date(),
                    checkout=datetime.datetime.strptime(
                        x["end"]["dateTime"], "%Y-%m-%dT%H:%M:%S%z"
                    ).date(),
                ),
                events["items"],
            )
        )
    }


class update_type_enum(str, Enum):
    update = "update"
    delete = "delete"


class update_reservation_req(BaseModel):
    update_type: update_type_enum = Field(description="更新する予約の種類（updateかdelete）")
    reserve_id: str = Field(description="予約ID")
    reserve_info: reserve_req = Field(
        description="更新する予約の情報。update_typeがupdateの場合は必須。deleteの場合は不要", default=None
    )


@app.post("/update_reservation", description="予約を更新するAPI")
def update_reservation(request: update_reservation_req):
    if request.update_type == update_type_enum.update:
        now = datetime.datetime.now(timezone)
        checkin = parse(request.reserve_info.checkin)
        checkout = parse(request.reserve_info.checkout)

        # 2023/12/28に1/1をパースすると、2023/1/1になるので、2024/1/1になるように調整
        if checkin.astimezone(timezone) < now:
            checkin = checkin + relativedelta.relativedelta(years=1)
        if checkout.astimezone(timezone) < now:
            checkout = checkout + relativedelta.relativedelta(years=1)

        checkin = datetime.datetime(
            checkin.year, checkin.month, checkin.day, 18, 0, 0, tzinfo=timezone
        )

        checkout = datetime.datetime(
            checkout.year, checkout.month, checkout.day, 10, 0, 0, tzinfo=timezone
        )

        description = {"reservation_holder": request.reserve_info.reservation_holder}

        event = {
            "summary": "hotel booking (Agents for Amazon Bedrock)",
            "description": json.dumps(description, ensure_ascii=False),
            "start": {
                "dateTime": checkin.isoformat(),
                "timeZone": zone_name,
            },
            "end": {
                "dateTime": checkout.isoformat(),
                "timeZone": zone_name,
            },
        }

        event = (
            service.events()
            .update(calendarId=calendar_id, eventId=request.reserve_id, body=event)
            .execute()
        )

        return reserve_res(
            reserve_id=event["id"],
            reservation_holder=request.reserve_info.reservation_holder,
            checkin=datetime.datetime.strptime(
                event["start"]["dateTime"], "%Y-%m-%dT%H:%M:%S%z"
            ).date(),
            checkout=datetime.datetime.strptime(
                event["end"]["dateTime"], "%Y-%m-%dT%H:%M:%S%z"
            ).date(),
        )

    elif request.update_type == update_type_enum.delete:
        return (
            service.events()
            .delete(calendarId=calendar_id, eventId=request.reserve_id)
            .execute()
        )


lambda_handler = Mangum(app, custom_handlers=[AgentsForBedrock], lifespan="off")
