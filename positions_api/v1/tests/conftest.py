import pytest
import httpx
from http import HTTPStatus
from random import  random,choice
from faker import Faker
fake=Faker("ru-RU")

BASE_URL = "http://localhost:5000"

@pytest.fixture(scope="session")
def api_client():
    with httpx.Client(base_url=BASE_URL, timeout=30.0, trust_env=False) as client:
        yield client


@pytest.fixture()
def generate_id_department(api_client):
    resp = api_client.get("/Departments")
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    return choice(body)["id"]

@pytest.fixture()
def generate_uncorrect_id_department(api_client):
    resp = api_client.get("/Departments")
    body = resp.json()
    result=[]
    for item in body:
        result.append(int(item["id"]))
    ind=max(result)+1
    return ind

@pytest.fixture() 
def find_department_name(api_client):
    resp = api_client.get("/Departments")
    body = resp.json()    
    return choice(body)["departmentName"]

@pytest.fixture() 
def generate_department_name(api_client):
    return fake.unique.word()
    
@pytest.fixture(scope="session") 
def auth_token(api_client):
    data={
        "email": "ivanov@company.com",
        "password": "Admin123!"
        }
    resp=api_client.post("/Auth/login",json=data)
    assert resp.status_code == HTTPStatus.OK
    token = resp.json()["token"]
    return token 

@pytest.fixture(scope="session") 
def generate_user_data(api_client):
    data={
            "email": fake.ascii_company_email(),
            "password": fake.profile["password"]
            }
    return data

@pytest.fixture(scope="function") 
def auth_token_employee(api_client):
    data={
        "email": "petrova@company.com",
        "password": "User123!"
        }
    resp=api_client.post("/Auth/login",json=data)
    assert resp.status_code == HTTPStatus.OK
    token = resp.json()["token"]
    assert "role" in resp.json()
    assert "employeeId" in resp.json()
    return token 



@pytest.fixture(scope="function")
def authenticated_client( auth_token):
    with httpx.Client(
        base_url=BASE_URL,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as client:
        yield client


@pytest.fixture(scope="function")
def auth_header(auth_token):
    return {"Authorization":f"Bearer {auth_token}"}

@pytest.fixture(scope="function")
def auth_header_employee(auth_token_employee):
    return {"Authorization":f"Bearer {auth_token_employee}"}

@pytest.fixture
def real_employee_id(api_client,auth_header):
    resp = api_client.get("/Employees",headers=auth_header)
    assert resp.status_code == HTTPStatus.OK
    employees = resp.json()
    return choice(employees)["id"] 

@pytest.fixture
def department_payload(real_employee_id):
    data ={
    "departmentName":  fake.unique.word(),
    "headId": real_employee_id
    }
    return data

@pytest.fixture
def create_department(api_client, department_payload, auth_header):
    response = api_client.post("/Departments", json=department_payload, headers=auth_header)
    assert response.status_code == HTTPStatus.CREATED
    department = response.json()["department"]
    yield department
    cleanup = api_client.delete(f"/Departments/{department['id']}", headers=auth_header)
    assert cleanup.status_code in (HTTPStatus.OK, HTTPStatus.NOT_FOUND)
