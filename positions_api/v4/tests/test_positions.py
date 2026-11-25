from http import HTTPStatus
from functools import partial
from uuid import uuid4

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
    return f"Инженер {uuid4().hex}"


class RoleClient:
    def __init__(self, client, headers):
        self.headers = headers
        self.post = partial(client.post, headers=headers)
        self.put = partial(client.put, headers=headers)
        self.delete = partial(client.delete, headers=headers)

    def post_raw(self, content, content_type):
        headers = self.headers | {"Content-Type": content_type}
        return self.post(PATH, headers=headers, content=content)


@pytest.fixture
def admin(api_client, auth_header):
    return RoleClient(api_client, auth_header)


@pytest.fixture
def employee(api_client, auth_header_employee):
    return RoleClient(api_client, auth_header_employee)


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


def invalid_title(response):
    result = check(response, HTTPStatus.UNPROCESSABLE_ENTITY)
    assert result["success"] is False
    assert isinstance(result["errors"], list) and result["errors"]


class TestReadPositions:
    def test_get_positions_list(self, api_client):
        records = read(api_client, PATH)
        assert isinstance(records, list) and records
        for record in records:
            assert type(record["positionId"]) is int
            assert isinstance(record["positionTitle"], str)
            assert record["positionTitle"]

    def test_get_position_by_id(self, api_client):
        result = read(api_client, EXISTING_PATH)
        assert result["positionId"] == 1 and result["positionTitle"]

    def test_get_position_by_uncorrect_id(self, api_client):
        result = check(api_client.get(MISSING_PATH), HTTPStatus.NOT_FOUND)
        assert result == {"message": "Должность не найдена"}


class TestCreatePosition:
    def test_post_position_by_admin(self, submit, new_title):
        result = check(submit(new_title), HTTPStatus.CREATED)
        assert result["success"] is True
        assert result["message"] == "Должность добавлена"
        assert type(result["position"]["positionId"]) is int
        assert result["position"]["positionId"] > 0
        assert result["position"]["positionTitle"] == new_title

    def test_post_position_unauthorized(self, api_client, new_title):
        response = api_client.post(PATH, json=payload(new_title))
        assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text

    def test_post_position_forbidden(self, api_client, employee, new_title):
        response = employee.post(PATH, json=payload(new_title))
        assert response.status_code == HTTPStatus.FORBIDDEN, response.text
        assert not any(item["positionTitle"] == new_title for item in read(api_client, PATH))

    def test_post_position_duplicate(self, submit, record):
        result = check(submit(record["positionTitle"]), HTTPStatus.CONFLICT)
        assert "уже существует" in result["message"]

    def test_post_position_empty_title(self, submit):
        invalid_title(submit(""))

    def test_post_position_long_title(self, api_client, submit, new_title):
        title = new_title.ljust(101, "я")
        result = check(submit(title), HTTPStatus.CREATED)
        assert result["success"] is True
        position = result["position"]
        assert position["positionTitle"] == title
        assert read(api_client, url(position)) == position

    def test_post_position_invalid_json(self, admin):
        response = admin.post_raw('{"positionTitle":', "application/json")
        invalid_title(response)

    def test_post_position_unsupported_media_type(self, admin, new_title):
        response = admin.post_raw(new_title, "text/plain")
        assert response.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE, response.text


class TestUpdatePosition:
    def test_put_position_by_admin(self, api_client, admin, record):
        new_title = f"Старший {record['positionTitle']}"
        result = check(admin.put(url(record), json=payload(new_title)), HTTPStatus.OK)
        assert result["success"] is True
        expected = record | payload(new_title)
        assert result["position"] == expected
        assert read(api_client, url(record)) == expected

    def test_put_position_uncorrect_id(self, admin, new_title):
        response = admin.put(MISSING_PATH, json=payload(new_title))
        assert response.status_code == HTTPStatus.NOT_FOUND, response.text

    def test_put_position_forbidden(self, api_client, employee, new_title):
        original = read(api_client, EXISTING_PATH)
        response = employee.put(EXISTING_PATH, json=payload(new_title))
        assert response.status_code == HTTPStatus.FORBIDDEN, response.text
        assert read(api_client, EXISTING_PATH) == original

    def test_put_position_unauthorized(self, api_client, new_title):
        response = api_client.put(EXISTING_PATH, json=payload(new_title))
        assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text

    def test_put_position_duplicate(self, api_client, admin, record):
        title = read(api_client, EXISTING_PATH)["positionTitle"]
        result = check(admin.put(url(record), json=payload(title)), HTTPStatus.CONFLICT)
        assert "уже существует" in result["message"]
        assert read(api_client, url(record)) == record

    def test_put_position_empty_title(self, api_client, admin, record):
        invalid_title(admin.put(url(record), json=payload("")))
        assert read(api_client, url(record)) == record


class TestDeletePosition:
    def test_delete_position_by_admin(self, api_client, admin, record):
        result = check(admin.delete(url(record)), HTTPStatus.OK)
        assert result["success"] is True
        assert result["message"] == f"Должность '{record['positionTitle']}' удалена"
        assert api_client.get(url(record)).status_code == HTTPStatus.NOT_FOUND

    def test_delete_position_in_use(self, api_client, admin):
        result = check(admin.delete(EXISTING_PATH), HTTPStatus.CONFLICT)
        assert "закреплена за сотрудником" in result["message"]
        assert read(api_client, EXISTING_PATH)["positionId"] == 1

    def test_delete_position_uncorrect_id(self, admin):
        response = admin.delete(MISSING_PATH)
        assert response.status_code == HTTPStatus.NOT_FOUND, response.text

    def test_delete_position_unauthorized(self, api_client, record):
        response = api_client.delete(url(record))
        assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text
        assert read(api_client, url(record)) == record

    def test_delete_position_forbidden(self, api_client, employee, record):
        response = employee.delete(url(record))
        assert response.status_code == HTTPStatus.FORBIDDEN, response.text
        assert read(api_client, url(record)) == record

    def test_delete_position_twice(self, api_client, admin, record):
        check(admin.delete(url(record)), HTTPStatus.OK)
        assert admin.delete(url(record)).status_code == HTTPStatus.NOT_FOUND
        assert api_client.get(url(record)).status_code == HTTPStatus.NOT_FOUND


class TestPositionLifecycle:
    def test_positions_crud_e2e(self, api_client, admin, submit, new_title):
        response = check(submit(new_title), HTTPStatus.CREATED)
        assert response["success"] is True
        position = response["position"]
        assert position["positionTitle"] == new_title
        path = url(position)

        updated_title = f"Ведущий {new_title}"
        expected = position | payload(updated_title)
        response = check(admin.put(path, json=payload(updated_title)), HTTPStatus.OK)
        assert response["success"] is True
        assert response["position"] == expected
        assert read(api_client, path) == expected

        response = check(admin.delete(path), HTTPStatus.OK)
        assert response["success"] is True
        assert response["message"] == f"Должность '{updated_title}' удалена"
        assert api_client.get(path).status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.parametrize("delete", [False, True], ids=["created", "deleted"])
    def test_position_list_reflects_changes(self, api_client, admin, record, delete):
        if delete:
            check(admin.delete(url(record)), HTTPStatus.OK)
        positions = read(api_client, PATH)
        listed_ids = {position["positionId"] for position in positions}
        assert (record["positionId"] in listed_ids) is (not delete)
