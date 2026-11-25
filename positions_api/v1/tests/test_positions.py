from http import HTTPStatus
from uuid import uuid4

import pytest


POSITIONS = "/Positions"


@pytest.fixture
def position_payload():
    return {"positionTitle": f"Архитектор ПО {uuid4().hex}"}


@pytest.fixture
def create_position(api_client, auth_header):
    created_ids = []

    def create(payload):
        response = api_client.post(POSITIONS, json=payload, headers=auth_header)
        position = response.json().get("position") if response.status_code == HTTPStatus.CREATED else None
        if position is not None:
            created_ids.append(position["positionId"])
        return response

    yield create

    for position_id in created_ids:
        response = api_client.delete(f"{POSITIONS}/{position_id}", headers=auth_header)
        assert response.status_code in (HTTPStatus.OK, HTTPStatus.NOT_FOUND)


@pytest.fixture
def position(create_position, position_payload):
    response = create_position(position_payload)
    assert response.status_code == HTTPStatus.CREATED, response.text
    return response.json()["position"]


def assert_validation_error(response):
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    body = response.json()
    assert body["success"] is False
    assert isinstance(body["errors"], list) and body["errors"]
    assert all(isinstance(error, str) and error for error in body["errors"])


def test_get_positions_list(api_client):
    response = api_client.get(POSITIONS)
    assert response.status_code == HTTPStatus.OK
    positions = response.json()
    assert isinstance(positions, list) and positions
    for item in positions:
        assert type(item["positionId"]) is int
        assert isinstance(item["positionTitle"], str) and item["positionTitle"]


def test_get_position_by_id(api_client):
    response = api_client.get(f"{POSITIONS}/1")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["positionId"] == 1
    assert isinstance(response.json()["positionTitle"], str)


def test_get_position_by_uncorrect_id(api_client):
    response = api_client.get(f"{POSITIONS}/99999")
    assert response.status_code == HTTPStatus.NOT_FOUND
    body = response.json()
    assert body.get("success") is False, body
    assert body["message"] == "Должность не найдена"


def test_post_position_by_admin(create_position, position_payload):
    response = create_position(position_payload)
    assert response.status_code == HTTPStatus.CREATED, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Должность добавлена"
    assert type(body["position"]["positionId"]) is int
    assert body["position"]["positionId"] > 0
    assert body["position"]["positionTitle"] == position_payload["positionTitle"]


def test_post_position_unauthorized(api_client, position_payload):
    response = api_client.post(POSITIONS, json=position_payload)
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text


def test_post_position_forbidden(api_client, position_payload, auth_header_employee):
    response = api_client.post(POSITIONS, json=position_payload, headers=auth_header_employee)
    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    listing = api_client.get(POSITIONS)
    assert listing.status_code == HTTPStatus.OK
    assert all(item["positionTitle"] != position_payload["positionTitle"] for item in listing.json())


def test_post_position_duplicate(api_client, auth_header, position):
    response = api_client.post(
        POSITIONS, json={"positionTitle": position["positionTitle"]}, headers=auth_header
    )
    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert "уже существует" in response.json()["message"].lower()


def test_post_position_empty_title(create_position):
    assert_validation_error(create_position({"positionTitle": ""}))


def test_post_position_long_title(create_position):
    title = f"{uuid4().hex:А<101}"
    assert_validation_error(create_position({"positionTitle": title}))


def test_post_position_invalid_json(api_client, auth_header):
    response = api_client.post(
        POSITIONS, content='{"positionTitle":', headers={**auth_header, "Content-Type": "application/json"}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text


def test_post_position_unsupported_media_type(api_client, auth_header):
    response = api_client.post(
        POSITIONS, content="Название должности", headers={**auth_header, "Content-Type": "text/plain"}
    )
    assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE, response.text


def test_put_position_by_admin(api_client, auth_header, position, position_payload):
    path = f"{POSITIONS}/{position['positionId']}"
    new_title = f"Ведущий {position_payload['positionTitle']}"
    response = api_client.put(path, json={"positionTitle": new_title}, headers=auth_header)
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["success"] is True
    assert body["position"]["positionId"] == position["positionId"]
    assert body["position"]["positionTitle"] == new_title
    current = api_client.get(path)
    assert current.status_code == HTTPStatus.OK
    assert current.json()["positionTitle"] == new_title


def test_put_position_uncorrect_id(api_client, auth_header, position_payload):
    response = api_client.put(f"{POSITIONS}/99999", json=position_payload, headers=auth_header)
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


def test_put_position_forbidden(api_client, auth_header_employee, position_payload):
    path = f"{POSITIONS}/1"
    before = api_client.get(path)
    assert before.status_code == HTTPStatus.OK
    response = api_client.put(path, json=position_payload, headers=auth_header_employee)
    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    after = api_client.get(path)
    assert after.status_code == HTTPStatus.OK
    assert after.json() == before.json()


def test_put_position_unauthorized(api_client, position_payload):
    response = api_client.put(f"{POSITIONS}/1", json=position_payload)
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text


def test_put_position_duplicate(api_client, auth_header, position):
    existing = api_client.get(f"{POSITIONS}/1")
    assert existing.status_code == HTTPStatus.OK
    path = f"{POSITIONS}/{position['positionId']}"
    response = api_client.put(
        path, json={"positionTitle": existing.json()["positionTitle"]}, headers=auth_header
    )
    assert response.status_code == HTTPStatus.CONFLICT, response.text
    current = api_client.get(path)
    assert current.status_code == HTTPStatus.OK
    assert current.json()["positionTitle"] == position["positionTitle"]


def test_put_position_empty_title(api_client, auth_header, position):
    response = api_client.put(
        f"{POSITIONS}/{position['positionId']}", json={"positionTitle": ""}, headers=auth_header
    )
    assert_validation_error(response)


def test_delete_position_by_admin(api_client, auth_header, position):
    path = f"{POSITIONS}/{position['positionId']}"
    response = api_client.delete(path, headers=auth_header)
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["success"] is True
    assert body["message"] == f"Должность '{position['positionTitle']}' удалена"
    assert api_client.get(path).status_code == HTTPStatus.NOT_FOUND


def test_delete_position_in_use(api_client, auth_header):
    path = f"{POSITIONS}/1"
    response = api_client.delete(path, headers=auth_header)
    assert response.status_code == HTTPStatus.CONFLICT, response.text
    assert "закреплена за сотрудником" in response.json()["message"]
    assert api_client.get(path).status_code == HTTPStatus.OK


def test_delete_position_uncorrect_id(api_client, auth_header):
    response = api_client.delete(f"{POSITIONS}/99999", headers=auth_header)
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


def test_delete_position_unauthorized(api_client, position):
    path = f"{POSITIONS}/{position['positionId']}"
    response = api_client.delete(path)
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
    assert api_client.get(path).status_code == HTTPStatus.OK


def test_delete_position_forbidden(api_client, auth_header_employee, position):
    path = f"{POSITIONS}/{position['positionId']}"
    response = api_client.delete(path, headers=auth_header_employee)
    assert response.status_code == HTTPStatus.FORBIDDEN, response.text
    assert api_client.get(path).status_code == HTTPStatus.OK


def test_positions_crud_e2e(api_client, auth_header, create_position, position_payload):
    created = create_position(position_payload)
    assert created.status_code == HTTPStatus.CREATED, created.text
    assert created.json()["success"] is True
    position = created.json()["position"]
    assert position["positionTitle"] == position_payload["positionTitle"]
    path = f"{POSITIONS}/{position['positionId']}"

    new_title = f"Главный {position['positionTitle']}"
    updated = api_client.put(path, json={"positionTitle": new_title}, headers=auth_header)
    assert updated.status_code == HTTPStatus.OK, updated.text
    assert updated.json()["success"] is True
    assert updated.json()["position"]["positionTitle"] == new_title

    current = api_client.get(path)
    assert current.status_code == HTTPStatus.OK
    assert current.json()["positionTitle"] == new_title
    assert current.json()["positionId"] == position["positionId"]

    deleted = api_client.delete(path, headers=auth_header)
    assert deleted.status_code == HTTPStatus.OK, deleted.text
    assert deleted.json()["success"] is True
    assert deleted.json()["message"] == f"Должность '{new_title}' удалена"
    assert api_client.get(path).status_code == HTTPStatus.NOT_FOUND
