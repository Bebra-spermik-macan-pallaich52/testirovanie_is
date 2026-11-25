from uuid import uuid4

import pytest


PATH = "/Positions"
INITIAL_ID = 1
UNKNOWN_ID = 99999


def endpoint(position_id=None):
    return PATH if position_id is None else f"{PATH}/{position_id}"


def expect_status(response, status):
    assert response.status_code == status, response.text
    return response


def get_position(client, position_id):
    return expect_status(client.get(endpoint(position_id)), 200).json()


def assert_validation(response):
    body = expect_status(response, 422).json()
    assert body["success"] is False
    assert isinstance(body["errors"], list) and body["errors"]


@pytest.fixture
def title():
    return f"Тестировщик {uuid4().hex}"


@pytest.fixture
def admin_request(api_client, auth_header):
    position_ids = []

    def request(method, position_id=None, **options):
        extra_headers = options.pop("headers", {})
        response = api_client.request(
            method, endpoint(position_id), headers=auth_header | extra_headers, **options
        )
        if method == "POST" and response.status_code == 201:
            position_ids.append(response.json()["position"]["positionId"])
        return response

    yield request

    for position_id in position_ids:
        response = api_client.delete(endpoint(position_id), headers=auth_header)
        assert response.status_code in (200, 404), response.text


@pytest.fixture
def created_position(admin_request, title):
    response = admin_request("POST", json={"positionTitle": title})
    return expect_status(response, 201).json()["position"]


def test_get_positions_list(api_client):
    data = expect_status(api_client.get(PATH), 200).json()
    assert isinstance(data, list) and data
    for position in data:
        assert {"positionId", "positionTitle"} <= position.keys()
        assert type(position["positionId"]) is int
        assert isinstance(position["positionTitle"], str)


def test_get_position_by_id(api_client):
    position = get_position(api_client, INITIAL_ID)
    assert position["positionId"] == INITIAL_ID
    assert isinstance(position["positionTitle"], str)


def test_get_position_by_uncorrect_id(api_client):
    response = expect_status(api_client.get(endpoint(UNKNOWN_ID)), 404)
    assert response.json() == {"success": False, "message": "Должность не найдена"}


def test_post_position_by_admin(admin_request, title):
    response = admin_request("POST", json={"positionTitle": title})
    body = expect_status(response, 201).json()
    assert body["success"] is True
    assert body["message"] == "Должность добавлена"
    assert type(body["position"]["positionId"]) is int
    assert body["position"]["positionId"] > 0
    assert body["position"]["positionTitle"] == title


def test_post_position_unauthorized(api_client, title):
    expect_status(api_client.post(PATH, json={"positionTitle": title}), 401)


def test_post_position_forbidden(api_client, auth_header_employee, title):
    response = api_client.post(PATH, headers=auth_header_employee, json={"positionTitle": title})
    expect_status(response, 403)
    positions = expect_status(api_client.get(PATH), 200).json()
    assert title not in [item["positionTitle"] for item in positions]


def test_post_position_duplicate(api_client, admin_request):
    position = get_position(api_client, INITIAL_ID)
    response = admin_request("POST", json={"positionTitle": position["positionTitle"]})
    assert "уже существует" in expect_status(response, 409).json()["message"]


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"positionTitle": ""}, id="empty-title"),
        pytest.param({"positionTitle": "   "}, id="whitespace-title"),
        pytest.param({}, id="missing-title"),
    ],
)
def test_post_position_empty_title(admin_request, body):
    assert_validation(admin_request("POST", json=body))


def test_post_position_long_title(admin_request, title):
    assert_validation(admin_request("POST", json={"positionTitle": title.ljust(101, "я")}))


def test_post_position_invalid_json(admin_request):
    response = admin_request("POST", headers={"Content-Type": "application/json"}, content='{"')
    expect_status(response, 400)


def test_post_position_unsupported_media_type(admin_request, title):
    response = admin_request("POST", headers={"Content-Type": "text/plain"}, content=title)
    expect_status(response, 415)


def test_put_position_by_admin(api_client, admin_request, created_position):
    position_id = created_position["positionId"]
    title = f"Главный {created_position['positionTitle']}"
    changed = admin_request("PUT", position_id, json={"positionTitle": title})
    body = expect_status(changed, 200).json()
    assert body["success"] is True
    assert body["position"] == {"positionId": position_id, "positionTitle": title}
    assert get_position(api_client, position_id) == body["position"]


def test_put_position_uncorrect_id(admin_request, title):
    expect_status(admin_request("PUT", UNKNOWN_ID, json={"positionTitle": title}), 404)


def test_put_position_forbidden(api_client, auth_header_employee, title):
    original = get_position(api_client, INITIAL_ID)
    response = api_client.put(
        endpoint(INITIAL_ID), headers=auth_header_employee, json={"positionTitle": title}
    )
    expect_status(response, 403)
    assert get_position(api_client, INITIAL_ID) == original


def test_put_position_unauthorized(api_client, title):
    expect_status(api_client.put(endpoint(INITIAL_ID), json={"positionTitle": title}), 401)


def test_put_position_duplicate(api_client, admin_request, created_position):
    duplicate = get_position(api_client, INITIAL_ID)
    position_id = created_position["positionId"]
    response = admin_request("PUT", position_id, json={"positionTitle": duplicate["positionTitle"]})
    expect_status(response, 409)
    assert get_position(api_client, position_id) == created_position


def test_put_position_empty_title(api_client, admin_request, created_position):
    position_id = created_position["positionId"]
    assert_validation(admin_request("PUT", position_id, json={"positionTitle": ""}))
    assert get_position(api_client, position_id) == created_position


def test_delete_position_by_admin(api_client, admin_request, created_position):
    position_id = created_position["positionId"]
    body = expect_status(admin_request("DELETE", position_id), 200).json()
    assert body["success"] is True
    assert body["message"] == f"Должность '{created_position['positionTitle']}' удалена"
    expect_status(api_client.get(endpoint(position_id)), 404)


def test_delete_position_in_use(api_client, admin_request):
    response = expect_status(admin_request("DELETE", INITIAL_ID), 409)
    assert "закреплена за сотрудником" in response.json()["message"]
    assert get_position(api_client, INITIAL_ID)["positionId"] == INITIAL_ID


def test_delete_position_uncorrect_id(admin_request):
    expect_status(admin_request("DELETE", UNKNOWN_ID), 404)


def test_delete_position_unauthorized(api_client, created_position):
    position_id = created_position["positionId"]
    expect_status(api_client.delete(endpoint(position_id)), 401)
    assert get_position(api_client, position_id) == created_position


def test_delete_position_forbidden(api_client, auth_header_employee, created_position):
    position_id = created_position["positionId"]
    expect_status(api_client.delete(endpoint(position_id), headers=auth_header_employee), 403)
    assert get_position(api_client, position_id) == created_position


def test_positions_crud_e2e(api_client, admin_request, title):
    created = expect_status(admin_request("POST", json={"positionTitle": title}), 201).json()
    assert created["success"] is True
    position_id = created["position"]["positionId"]
    assert created["position"]["positionTitle"] == title

    updated_title = f"Руководитель {title}"
    response = admin_request("PUT", position_id, json={"positionTitle": updated_title})
    updated = expect_status(response, 200).json()
    assert updated["success"] is True
    assert updated["position"] == get_position(api_client, position_id)
    assert updated["position"] == {"positionId": position_id, "positionTitle": updated_title}

    deleted = expect_status(admin_request("DELETE", position_id), 200).json()
    assert deleted["success"] is True
    assert deleted["message"] == f"Должность '{updated_title}' удалена"
    expect_status(api_client.get(endpoint(position_id)), 404)
