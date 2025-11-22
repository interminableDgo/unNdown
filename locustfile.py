import requests
from locust import HttpUser, task, constant, LoadTestShape, events
from locust.exception import StopUser

# === 1. CONFIGURACIÓN ===
TARGET_IP = "104.248.215.179"
LOGIN_URL = f"http://{TARGET_IP}:5002/api/login"

CREDENTIALS = {
    "login": "carlos.gómez@heartguard.com", 
    "password": "123"
}

TEST_DATA = {
    "patient_id": "7199cd3d-47ce-409f-89d5-9d01ca82fd08",
    "appointment_id": "db61d072-67ef-4cad-b396-6f86d13187df"
}

# === 2. ESCENARIO RAMP-UP / RAMP-DOWN SUAVE ===
# Ajustado para no matar al servidor de desarrollo Flask
class RampUpAndDown(LoadTestShape):
    stages = [
        {"duration": 30,  "users": 2,  "spawn_rate": 1},  # Calentamiento
        {"duration": 90,  "users": 5,  "spawn_rate": 1},  # Subida suave
        {"duration": 180, "users": 10, "spawn_rate": 1},  # Pico máximo (10 usuarios)
        {"duration": 240, "users": 5,  "spawn_rate": 1},  # Bajada
        {"duration": 300, "users": 0,  "spawn_rate": 1},  # Fin
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None

# === 3. USUARIO AUTENTICADO ===

class AuthenticatedUser(HttpUser):
    abstract = True
    token = None
    
    def on_start(self):
        try:
            # Header Connection: close ayuda a evitar el error 10054 en servidores dev
            headers = {"Connection": "close"} 
            res = requests.post(LOGIN_URL, json=CREDENTIALS, headers=headers, timeout=10)
            
            if res.status_code == 200:
                self.token = res.json().get("access_token")
            else:
                print(f"Login Falló ({res.status_code}). Deteniendo usuario.")
                raise StopUser()
        except Exception as e:
            print(f"Error conexión Login: {e}")
            raise StopUser()

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Connection": "close" # CLAVE: Cerramos conexión tras cada petición
        }

# === 4. MICROSERVICIOS ===

class ServiceAppointments(AuthenticatedUser):
    host = f"http://{TARGET_IP}:5001"
    wait_time = constant(2) # Espera más realista (2 seg)
    @task
    def get_appointment(self):
        if self.token: 
            self.client.get(f"/api/appointments/{TEST_DATA['appointment_id']}", headers=self.get_headers())

class ServiceMedicalHistory(AuthenticatedUser):
    host = f"http://{TARGET_IP}:5004"
    wait_time = constant(2)
    @task
    def get_history(self):
        if self.token: 
            self.client.get(f"/api/medical-history?patient_id={TEST_DATA['patient_id']}", headers=self.get_headers())

class ServicePatients(AuthenticatedUser):
    host = f"http://{TARGET_IP}:5005"
    wait_time = constant(2)
    @task
    def get_profile(self):
        if self.token: 
            self.client.get(f"/api/patients/{TEST_DATA['patient_id']}", headers=self.get_headers())

class ServiceVitals(AuthenticatedUser):
    host = f"http://{TARGET_IP}:5006"
    wait_time = constant(2)
    @task
    def get_vitals(self):
        if self.token: 
            self.client.get("/api/vitals", params={"patient_id": TEST_DATA['patient_id'], "range_hours": 24}, headers=self.get_headers())