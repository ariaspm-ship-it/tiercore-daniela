#!/usr/bin/env python3
# DANIELA - Motor de IA para predicción y alertas v1.0

import os
import time
import json
import numpy as np
from datetime import datetime, timedelta
from collections import deque
import requests

class IAEngine:
    """Motor de inteligencia artificial para Daniela"""
    
    def __init__(self, use_deepseek=True):
        self.history = deque(maxlen=10080)  # 7 días a 1 minuto
        self.battery_history = deque(maxlen=720)  # 30 días a 1 hora
        self.alert_thresholds = {
            "load_high": 80,  # % carga alta
            "load_low": 10,    # % carga baja
            "temp_high": 28,   # °C temperatura alta
            "battery_low": 30,  # % batería baja
            "runtime_low": 300,  # segundos (5 minutos)
            "degradation_rate": 5  # % pérdida por semana
        }
        
        # Configurar DeepSeek API
        self.use_deepseek = use_deepseek
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "demo-key")
        self.deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        
        # Historial de alertas
        self.alerts = []
        
    def add_reading(self, data):
        """Añade una lectura al historial"""
        timestamp = datetime.now()
        reading = {
            "timestamp": timestamp,
            "load": data.get("ups_load", 0),
            "battery_charge": data.get("battery_charge", 0),
            "battery_voltage": data.get("battery_voltage", 0),
            "temperature": data.get("temperature", 25),
            "runtime": data.get("runtime_remaining", 0),
            "input_voltage": data.get("input_voltage", 220)
        }
        self.history.append(reading)
        
        # Guardar para análisis de batería (cada hora)
        if len(self.history) % 12 == 0:  # Cada minuto? no, mejor condicional
            last_hour = [r for r in self.history if r["timestamp"] > timestamp - timedelta(hours=1)]
            if last_hour:
                avg_charge = np.mean([r["battery_charge"] for r in last_hour])
                self.battery_history.append({
                    "timestamp": timestamp,
                    "avg_charge": avg_charge
                })
        
        return reading
    
    def analyze_battery_degradation(self):
        """Analiza degradación de la batería en el tiempo"""
        if len(self.battery_history) < 24:  # Necesita al menos 24h de datos
            return 0, "insufficient_data"
        
        charges = [b["avg_charge"] for b in self.battery_history]
        
        # Calcular tendencia lineal
        x = np.arange(len(charges))
        try:
            slope = np.polyfit(x, charges, 1)[0]
        except:
            slope = 0
        
        # Pérdida por semana (en %)
        weekly_loss = abs(slope) * 24 * 7
        
        if weekly_loss > self.alert_thresholds["degradation_rate"]:
            return weekly_loss, "high_degradation"
        elif weekly_loss > self.alert_thresholds["degradation_rate"] / 2:
            return weekly_loss, "medium_degradation"
        else:
            return weekly_loss, "normal"
    
    def detect_anomalies(self):
        """Detecta anomalías en tiempo real"""
        if len(self.history) < 10:
            return []
        
        anomalies = []
        last = self.history[-1]
        recent = list(self.history)[-10:]  # últimos 10
        
        # Media y desviación
        loads = [r["load"] for r in recent[:-1]]
        if loads:
            mean_load = np.mean(loads)
            std_load = np.std(loads)
            
            # Pico de carga repentino
            if abs(last["load"] - mean_load) > 3 * std_load and std_load > 0:
                anomalies.append({
                    "type": "load_spike",
                    "value": last["load"],
                    "expected": mean_load,
                    "severity": "high" if abs(last["load"] - mean_load) > 5 * std_load else "medium"
                })
        
        # Temperatura sostenida alta
        temps = [r["temperature"] for r in recent]
        if np.mean(temps) > self.alert_thresholds["temp_high"]:
            anomalies.append({
                "type": "high_temperature_persistent",
                "value": np.mean(temps),
                "threshold": self.alert_thresholds["temp_high"],
                "severity": "medium"
            })
        
        return anomalies
    
    def check_thresholds(self):
        """Comprueba umbrales simples"""
        if not self.history:
            return []
        
        last = self.history[-1]
        alerts = []
        
        # Carga alta
        if last["load"] > self.alert_thresholds["load_high"]:
            alerts.append({
                "type": "high_load",
                "value": last["load"],
                "threshold": self.alert_thresholds["load_high"],
                "severity": "medium"
            })
        
        # Carga baja (posible desconexión)
        if last["load"] < self.alert_thresholds["load_low"]:
            alerts.append({
                "type": "low_load",
                "value": last["load"],
                "threshold": self.alert_thresholds["load_low"],
                "severity": "low"
            })
        
        # Batería baja
        if last["battery_charge"] < self.alert_thresholds["battery_low"]:
            alerts.append({
                "type": "low_battery",
                "value": last["battery_charge"],
                "threshold": self.alert_thresholds["battery_low"],
                "severity": "high"
            })
        
        # Poca autonomía
        if last["runtime"] < self.alert_thresholds["runtime_low"]:
            alerts.append({
                "type": "low_runtime",
                "value": last["runtime"] / 60,  # en minutos
                "threshold": self.alert_thresholds["runtime_low"] / 60,
                "severity": "high"
            })
        
        return alerts
    
    def generate_alert_text(self, alert):
        """Genera texto legible para una alerta usando IA"""
        
        if self.use_deepseek and self.deepseek_api_key != "demo-key":
            try:
                prompt = f"Genera una alerta corta y profesional para un centro de datos sobre: {alert['type']} con valor {alert['value']}. Máximo 20 palabras."
                
                response = requests.post(
                    self.deepseek_url,
                    headers={
                        "Authorization": f"Bearer {self.deepseek_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 50
                    },
                    timeout=5
                )
                
                if response.status_code == 200:
                    return response.json()["choices"][0]["message"]["content"]
            except:
                pass  # Si falla, usar templates
        
        # Templates por defecto
        templates = {
            "high_load": f"⚡ Carga alta: {alert['value']}%. Supervisar expansión.",
            "low_load": f"🔌 Carga baja: {alert['value']}%. Verificar equipos conectados.",
            "low_battery": f"🔋 Batería baja: {alert['value']}%. Riesgo de fallo.",
            "low_runtime": f"⏱️ Autonomía baja: {alert['value']:.0f} min. Revisar baterías.",
            "high_temperature_persistent": f"🌡️ Temperatura alta sostenida: {alert['value']:.0f}°C. Revisar climatización.",
            "load_spike": f"⚠️ Pico de carga: {alert['value']}% (esperado {alert['expected']:.0f}%). Verificar equipos.",
            "battery_degradation": f"🔋 Degradación acelerada: {alert['value']:.1f}%/semana. Programar reemplazo."
        }
        
        return templates.get(alert["type"], f"Alerta: {alert['type']} = {alert['value']}")
    
    def get_predictions(self):
        """Genera predicciones a corto plazo"""
        if len(self.history) < 60:  # Necesita 1h de datos
            return {}
        
        recent = list(self.history)[-60:]
        loads = [r["load"] for r in recent]
        
        # Predicción simple basada en tendencia
        try:
            x = np.arange(len(loads))
            slope = np.polyfit(x, loads, 1)[0]
            predicted_load = loads[-1] + slope * 10  # predicción a 10 pasos
            
            # Probabilidad de fallo (simplificada)
            failure_prob = 0
            if predicted_load > 90:
                failure_prob = 0.3
            elif loads[-1] > 85 and np.std(loads) > 5:
                failure_prob = 0.15
            
            return {
                "predicted_load": predicted_load,
                "trend": "up" if slope > 0 else "down",
                "failure_probability": failure_prob,
                "next_maintenance_days": self._estimate_maintenance()
            }
        except:
            return {}
    
    def _estimate_maintenance(self):
        """Estima días para próximo mantenimiento"""
        if len(self.battery_history) < 48:
            return 90  # valor por defecto
        
        charges = [b["avg_charge"] for b in self.battery_history]
        slope = np.polyfit(np.arange(len(charges)), charges, 1)[0]
        
        if slope >= 0:
            return 90  # estable
        
        # Días hasta llegar a 50%
        days_to_50 = (charges[-1] - 50) / (abs(slope) * 24)
        return max(0, min(365, int(days_to_50)))
    
    def analyze(self):
        """Análisis completo del estado"""
        threshold_alerts = self.check_thresholds()
        anomalies = self.detect_anomalies()
        degradation_rate, deg_status = self.analyze_battery_degradation()
        
        all_alerts = threshold_alerts + anomalies
        
        if deg_status != "normal":
            all_alerts.append({
                "type": "battery_degradation",
                "value": degradation_rate,
                "severity": "high" if deg_status == "high_degradation" else "medium"
            })
        
        # Generar textos para alertas
        for alert in all_alerts:
            alert["text"] = self.generate_alert_text(alert)
            alert["timestamp"] = datetime.now().isoformat()
            self.alerts.append(alert)
        
        # Mantener solo últimas 100 alertas
        self.alerts = self.alerts[-100:]
        
        return {
            "alerts": all_alerts,
            "predictions": self.get_predictions(),
            "degradation_rate": degradation_rate,
            "stats": {
                "avg_load": np.mean([r["load"] for r in list(self.history)[-60:]]) if len(self.history) >= 60 else 0,
                "avg_temp": np.mean([r["temperature"] for r in list(self.history)[-60:]]) if len(self.history) >= 60 else 0,
                "min_runtime": min([r["runtime"] for r in list(self.history)[-60:]]) if len(self.history) >= 60 else 0
            }
        }


# Pruebas
if __name__ == "__main__":
    ia = IAEngine(use_deepseek=False)
    
    # Simular lecturas
    for i in range(100):
        data = {
            "ups_load": 40 + np.sin(i/10) * 10,
            "battery_charge": 95 - i * 0.1,
            "temperature": 24 + np.sin(i/20) * 2,
            "runtime_remaining": 1800 - i * 2
        }
        ia.add_reading(data)
        
        if i % 10 == 0:
            analysis = ia.analyze()
            if analysis["alerts"]:
                for alert in analysis["alerts"]:
                    print(f"🔔 {alert['text']}")
    
    print(f"\n📊 Predicciones: {ia.get_predictions()}")