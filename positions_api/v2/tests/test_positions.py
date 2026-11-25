from http import HTTPStatus
from uuid import uuid4

import httpx
import pytest


PATH = "/Positions"
EXISTING_PATH = f"{PATH}/1"
MISSING_PATH = f"{PATH}/99999"


def check(response, expected):
    assert response.status_code == expected, response.text
    return response.json()


def payload(title):
    return {"positionTitle": title}


@pytest.fixture
def new_title():
    return f"Аналитик {uuid4().hex}"


@pytest.fixture
def admin(api_client, auth_header):
    with httpx.Client(
        base_url=api_client.base_url, headers=auth_header, timeout=api_client.timeout, trust_env=False
    ) as client:
        yield client


@pytest.fixture
def employee(api_client, auth_header_employee):
    with httpx.Client(
        base_url=api_client.base_url, headers=auth_header_employee, timeout=api_client.timeout, trust_env=False
    ) as client:
        yield client


@pytest.fixture
def submit(admin):
    temporary_paths = []

    def post(title):
        response = admin.post(PATH, json=payload(title))
        if response.status_code == HTTPStatus.CREATED:
            position_id = response.json()["position"]["positionId"]
            temporary_paths.append(f"{PATH}/{position_id}")
        return response

    yield post

    for path in temporary_paths:
        response = admin.delete(path)
        assert response.status_code in (HTTPStatus.OK, HTTPStatus.NOT_FOUND), response.text


@pytest.fixture
def record(submit, new_title):
    return check(submit(new_title), HTTPStatus.CREATED)["position"]


def url(record):
    return f"{PATH}/{record['positionId']}"


def read(api_client, path):
    return check(api_client.get(path), HTTPStatus.OK)


def test_get_positions_list(api_client):
    records = read(api_client, PATH)
    assert isinstance(records, list) and records
    assert all(type(item["positionId"]) is int and isinstance(item["positionTitle"], str)
               for item in records)


def test_get_position_by_id(api_client):
    result = read(api_client, EXISTING_PATH)
    assert result["positionId"] == 1 and result["positionTitle"]


def test_get_position_by_uncorrect_id(api_client):
    result = check(api_client.get(MISSING_PATH), HTTPStatus.NOT_FOUND)
    assert result == {"message": "Должность не найдена"}


def test_post_position_by_admin(submit, new_title):
    result = check(submit(new_title), HTTPStatus.CREATED)
    assert result["success"] is True
    assert result["message"] == "Должность добавлена"
    assert type(result["position"]["positionId"]) is int
    assert result["position"]["positionId"] > 0
    assert result["position"]["positionTitle"] == new_title


def test_post_position_unauthorized(api_client, new_title):
    response = api_client.post(PATH, json=payload(new_title))
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text


def test_post_position_forbidden(api_client, employee, new_title):
    response = employee.post(PATH, json=payload(new_title))
    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    titles = {item["positionTitle"] for item in read(api_client, PATH)}
    assert new_title not in titles


def test_post_position_duplicate(submit, record):
    result = check(submit(record["positionTitle"]), HTTPStatus.CONFLICT)
    assert "уже существует" in result["message"]


def invalid_title(response):
    result = check(response, HTTPStatus.UNPROCESSABLE_ENTITY)
    assert result["success"] is False
    assert isinstance(result["errors"], list) and result["errors"]


def test_post_position_empty_title(submit):
    invalid_title(submit(""))


def test_post_position_long_title(api_client, submit, new_title):
    title = new_title.ljust(101, "я")
    created = check(submit(title), HTTPStatus.CREATED)
    assert created["success"] is True
    position = created["position"]
    assert read(api_client, url(position)) == position == {
        "positionId": position["positionId"],
        "positionTitle": title,
    }


def test_post_position_invalid_json(admin):
    response = admin.post(PATH, headers={"Content-Type": "application/json"}, content="{")
    invalid_title(response)


def test_post_position_unsupported_media_type(admin, new_title):
    response = admin.post(PATH, headers={"Content-Type": "text/plain"}, content=new_title)
    assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE, response.text


def test_put_position_by_admin(api_client, admin, record):
    new_title = f"Старший {record['positionTitle']}"
    result = check(admin.put(url(record), json=payload(new_title)), HTTPStatus.OK)
    assert result["success"] is True
    expected = record | payload(new_title)
    assert result["position"] == read(api_client, url(record)) == expected


def test_put_position_uncorrect_id(admin, new_title):
    response = admin.put(MISSING_PATH, json=payload(new_title))
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


def test_put_position_forbidden(api_client, employee, new_title):
    original = read(api_client, EXISTING_PATH)
    response = employee.put(EXISTING_PATH, json=payload(new_title))
    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert read(api_client, EXISTING_PATH) == original


def test_put_position_unauthorized(api_client, new_title):
    response = api_client.put(EXISTING_PATH, json=payload(new_title))
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text


def test_put_position_duplicate(api_client, admin, record):
    title = read(api_client, EXISTING_PATH)["positionTitle"]
    result = check(admin.put(url(record), json=payload(title)), HTTPStatus.CONFLICT)
    assert "уже существует" in result["message"]
    assert read(api_client, url(record)) == record


def test_put_position_empty_title(api_client, admin, record):
    invalid_title(admin.put(url(record), json=payload("")))
    assert read(api_client, url(record)) == record


def test_delete_position_by_admin(api_client, admin, record):
    result = check(admin.delete(url(record)), HTTPStatus.OK)
    assert result["success"] is True
    assert result["message"] == f"Должность '{record['positionTitle']}' удалена"
    assert api_client.get(url(record)).status_code == HTTPStatus.NOT_FOUND


def test_delete_position_in_use(api_client, admin):
    result = check(admin.delete(EXISTING_PATH), HTTPStatus.CONFLICT)
    assert "закреплена за сотрудником" in result["message"]
    assert read(api_client, EXISTING_PATH)["positionId"] == 1


def test_delete_position_uncorrect_id(admin):
    response = admin.delete(MISSING_PATH)
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


def test_delete_position_unauthorized(api_client, record):
    response = api_client.delete(url(record))
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    assert read(api_client, url(record)) == record


def test_delete_position_forbidden(api_client, employee, record):
    response = employee.delete(url(record))
    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert read(api_client, url(record)) == record


def test_positions_crud_e2e(api_client, admin, submit, new_title):
    created = check(submit(new_title), HTTPStatus.CREATED)
    assert created["success"] is True
    record = created["position"]
    assert record["positionTitle"] == new_title
    path = url(record)

    title = f"Ведущий {new_title}"
    updated = check(admin.put(path, json=payload(title)), HTTPStatus.OK)
    assert updated["success"] is True
    assert updated["position"] == read(api_client, path) == record | payload(title)

    deleted = check(admin.delete(path), HTTPStatus.OK)
    assert deleted == {"success": True, "message": f"Должность '{title}' удалена"}
    assert api_client.get(path).status_code == HTTPStatus.NOT_FOUND


def test_delete_position_twice(api_client, admin, record):
    check(admin.delete(url(record)), HTTPStatus.OK)
    assert admin.delete(url(record)).status_code == HTTPStatus.NOT_FOUND
    assert api_client.get(url(record)).status_code == HTTPStatus.NOT_FOUND
