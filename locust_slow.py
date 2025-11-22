import requests
from locust import HttpUser, task, constant, events
from locust.exception import StopUser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# === 1. CONFIGURACIÓN ===
TARGET_IP = "104.248.215.179"
LOGIN_URL = f"http://{TARGET_IP}:5002/api/login"

CREDENTIALS = {
    "login": "carlos.gómez@heartguard.com", 
    "password": "123"
}

# Datos reales extraídos de tu backup SQL
TEST_DATA = {
    "patient_id": "7199cd3d-47ce-409f-89d5-9d01ca82fd08",
    "appointment_id": "db61d072-67ef-4cad-b396-6f86d13187df"
}

class SlowUser(HttpUser):
    abstract = True
    token = None
    
    def on_start(self):
        # Configurar el cliente para NO mantener conexiones vivas (evita el error 10054)
        self.client.keep_alive = False
        adapter = HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1))
        self.client.mount("http://", adapter)
        self.client.mount("https://", adapter)

        try:
            # Login con timeout alto
            res = requests.post(LOGIN_URL, json=CREDENTIALS, headers={"Connection": "close"}, timeout=10)
            if res.status_code == 200:
                self.token = res.json().get("access_token")
            else:
                print(f"Login Error: {res.status_code}")
                raise StopUser()
        except Exception as e:
            print(f"Login Exception: {e}")
            raise StopUser()

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Connection": "close" # OBLIGATORIO: Cierra el socket tras cada uso
        }

# === 2. MICROSERVICIOS (SECUENCIALES) ===

class ServiceAppointments(SlowUser):
    host = f"http://{TARGET_IP}:5001"
    # Espera constante de 3 segundos para dejar respirar al servidor
    wait_time = constant(3) 
    
    @task
    def get_appointment(self):
        if self.token: 
            self.client.get(f"/api/appointments/{TEST_DATA['appointment_id']}", headers=self.get_headers())

class ServiceMedicalHistory(SlowUser):
    host = f"http://{TARGET_IP}:5004"
    wait_time = constant(3)
    
    @task
    def get_history(self):
        if self.token: 
            self.client.get(f"/api/medical-history?patient_id={TEST_DATA['patient_id']}", headers=self.get_headers())

class ServicePatients(SlowUser):
    host = f"http://{TARGET_IP}:5005"
    wait_time = constant(3)
    
    @task
    def get_profile(self):
        if self.token: 
            self.client.get(f"/api/patients/{TEST_DATA['patient_id']}", headers=self.get_headers())

class ServiceVitals(SlowUser):
    host = f"http://{TARGET_IP}:5006"
    wait_time = constant(3)
    
    @task
    def get_vitals(self):
        if self.token: 
            self.client.get("/api/vitals", params={"patient_id": TEST_DATA['patient_id'], "range_hours": 24}, headers=self.get_headers())