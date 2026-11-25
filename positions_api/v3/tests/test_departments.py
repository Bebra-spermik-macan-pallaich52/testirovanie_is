from http import HTTPStatus
from faker import Faker
fake=Faker("ru-RU")

def test_get_departments_list(api_client):
    resp = api_client.get("/Departments")
    assert resp.status_code == HTTPStatus.OK
    assert isinstance(resp.json(), list)
    body = resp.json()[0]
    assert "id" in body
    assert "departmentName" in body

def test_get_department_by_id(api_client,generate_id_department):

    id=generate_id_department
    resp = api_client.get(f"/Departments/{id}")

    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert "id" in body
    assert body["id"]==id

def test_get_department_by_uncorrect_id(api_client,generate_uncorrect_id_department):

    id=generate_uncorrect_id_department
    resp = api_client.get(f"/Departments/{id}")

    assert resp.status_code == HTTPStatus.NOT_FOUND
    body = resp.json()
    assert body["success"] is False
    assert "message" in body
    assert body["message"]=="Отдел не найден"

def test_get_department_by_real_name(api_client,find_department_name):

    department_name=find_department_name
    resp = api_client.get(f"/Departments/search?query={department_name}")

    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body[0]["departmentName"]==department_name


def test_get_department_by_department_name(api_client,generate_department_name):

    department_name=generate_department_name
    resp = api_client.get(f"/Departments/search?query={department_name}")

    assert resp.status_code == HTTPStatus.NOT_FOUND
    body = resp.json()
    assert body["success"] is False
    assert "message" in body
    assert "не найдены" in body["message"]

def test_post_department_403_error(api_client,real_employee_id,auth_header_employee):

    data ={
    "departmentName":  fake.unique.word(),
    "headId": real_employee_id
    }

    resp = api_client.post("/Departments", json=data,headers=auth_header_employee)

    assert resp.status_code == HTTPStatus.FORBIDDEN



def test_post_department_unauthorize(api_client,real_employee_id):

    data ={
    "departmentName":  fake.unique.word(),
    "headId": real_employee_id
    }

    resp = api_client.post("/Departments", json=data)

    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_post_department_by_admin(api_client,auth_header,department_payload):

    data =department_payload

    resp = api_client.post("/Departments", json=data,headers=auth_header)

    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body["success"] is True
    assert body["message"]=="Отдел создан"
    result_data= body["department"]
    assert "id" in result_data
    assert result_data["departmentName"]==data["departmentName"]
    assert result_data["headId"]==data["headId"]
    id=result_data["id"]
    resp = api_client.delete(f"/Departments/{id}",headers=auth_header)
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body["success"] is True
    assert "удалён" in body["message"]


def test_delete_department_unauthorized(api_client,generate_id_department):

    id=generate_id_department
    resp = api_client.delete(f"/Departments/{id}")
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_delete_department_fobidden(api_client,create_department,auth_header_employee):

    id=create_department["id"]
    resp = api_client.delete(f"/Departments/{id}",headers=auth_header_employee)

    assert resp.status_code == HTTPStatus.FORBIDDEN


def test_delete_department_by_id(api_client,create_department,auth_header):

    id=create_department["id"]

    resp = api_client.delete(f"/Departments/{id}",headers=auth_header)

    assert resp.status_code == HTTPStatus.OK