# ai/chiller_optimizer.py
# Optimizador de chillers RTAG con IA

import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from core.config import Config
from core.logger import ai_logger
from devices.chiller import Chiller


@dataclass
class OptimizacionResult:
    """Resultado de la optimización de un chiller"""
    chiller_id: str
    cop_actual: float
    cop_objetivo: float
    ahorro_potencial_kw: float
    ahorro_potencial_euro_dia: float
    recomendacion: str
    confianza: float
    timestamp: datetime


class ChillerOptimizer:
    """
    Optimizador de chillers RTAG usando:
    - Modelo de eficiencia basado en histórico
    - Predicción de demanda por hora/clima/ocupación
    - Algoritmo de secuenciación óptima
    - Detección de degradación (>8%)
    """

    def __init__(self):
        self.modelos = {}
        self.historial_optimizaciones = []
        self.precio_kwh = getattr(Config, 'PRECIO_KWH', 0.25)
        self.cop_minimo = 3.5
        self.umbral_degradacion = 0.08

        try:
            from sklearn.linear_model import LinearRegression  # noqa: F401
            self.ML_AVAILABLE = True
            ai_logger.info("✅ scikit-learn disponible para modelos ML")
        except ImportError:
            self.ML_AVAILABLE = False
            ai_logger.warning("⚠️ scikit-learn no disponible, usando regresión numpy")

        ai_logger.info(f"🚀 Optimizador de chillers inicializado (precio={self.precio_kwh}€/kWh)")

    def _regresion_numpy(self, X, y):
        X = np.array(X)
        y = np.array(y)
        X_with_intercept = np.c_[np.ones(X.shape[0]), X]

        try:
            theta = np.linalg.pinv(X_with_intercept.T @ X_with_intercept) @ X_with_intercept.T @ y
            return theta[1:], theta[0]
        except Exception:
            return np.zeros(X.shape[1]), np.mean(y)

    def entrenar_modelo_chiller(self, chiller: Chiller) -> Optional[Dict]:
        if not chiller.history or len(chiller.history) < 50:
            ai_logger.warning(
                f"Chiller {chiller.id}: histórico insuficiente ({len(chiller.history) if chiller.history else 0})"
            )
            return None

        X = []
        y = []

        for lectura in chiller.history:
            if not lectura.cop or lectura.cop <= 0:
                continue

            hora = lectura.timestamp.hour
            dia_semana = lectura.timestamp.weekday()
            temp_ext = 25 + np.sin(hora / 24 * 2 * np.pi) * 5 + np.random.normal(0, 1)
            carga = (lectura.cooling_kw / 500) * 100 if lectura.cooling_kw else 50

            X.append([hora, temp_ext, carga, dia_semana])
            y.append(lectura.cop)

        if len(X) < 30:
            return None

        if self.ML_AVAILABLE:
            from sklearn.linear_model import LinearRegression
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            model = LinearRegression()
            model.fit(X_scaled, y)

            self.modelos[chiller.id] = {
                'model': model,
                'scaler': scaler,
                'fecha_entrenamiento': datetime.now(),
                'precision': model.score(X_scaled, y),
                'tipo': 'sklearn'
            }

            ai_logger.info(f"✅ Modelo sklearn entrenado para {chiller.id} (R²={model.score(X_scaled, y):.3f})")

        else:
            coeficientes, intercepto = self._regresion_numpy(X, y)

            self.modelos[chiller.id] = {
                'coeficientes': coeficientes.tolist() if hasattr(coeficientes, 'tolist') else coeficientes,
                'intercepto': float(intercepto),
                'fecha_entrenamiento': datetime.now(),
                'tipo': 'numpy'
            }

            ai_logger.info(f"✅ Modelo numpy entrenado para {chiller.id}")

        return self.modelos[chiller.id]

    def predecir_cop(self, chiller_id: str, hora: int, temp_ext: float, carga: float) -> float:
        if chiller_id not in self.modelos:
            return 4.0

        modelo = self.modelos[chiller_id]

        if modelo['tipo'] == 'sklearn':
            X = np.array([[hora, temp_ext, carga, 2]])
            X_scaled = modelo['scaler'].transform(X)
            return float(modelo['model'].predict(X_scaled)[0])

        coef = modelo['coeficientes']
        intercepto = modelo['intercepto']
        return float(intercepto + coef[0] * hora + coef[1] * temp_ext + coef[2] * carga)

    def predecir_demanda(self, hora: int, temp_exterior: float, ocupacion: float = 1.0) -> float:
        base = 200

        if 12 <= hora <= 16:
            factor_hora = 1.8
        elif 8 <= hora <= 11 or 17 <= hora <= 20:
            factor_hora = 1.4
        elif 21 <= hora <= 23:
            factor_hora = 1.1
        else:
            factor_hora = 0.6

        factor_temp = 1.0 + max(0, (temp_exterior - 25) * 0.05)
        factor_ocup = ocupacion

        demanda = base * factor_hora * factor_temp * factor_ocup
        return round(demanda, 1)

    def calcular_secuencia_optima(self, demanda: float, chillers: List[Chiller]) -> List[bool]:
        if len(chillers) != 3:
            return [True, False, False]

        cops = []
        for chiller in chillers:
            if chiller.last_data and chiller.last_data.cop:
                cops.append((chiller.id, chiller.last_data.cop))
            else:
                cop_pred = self.predecir_cop(chiller.id, datetime.now().hour, 28, 50)
                cops.append((chiller.id, cop_pred))

        cops.sort(key=lambda x: x[1], reverse=True)

        if demanda < 200:
            return [ch.id == cops[0][0] for ch in chillers]
        if demanda < 400:
            return [ch.id in [cops[0][0], cops[1][0]] for ch in chillers]
        return [True, True, True]

    def detectar_degradacion(self, chiller: Chiller) -> Dict:
        if len(chiller.history) < 100:
            return {"degradado": False, "confianza": 0, "degradacion_pct": 0}

        cutoff = datetime.now() - timedelta(days=7)

        cop_reciente = [
            d.cop for d in chiller.history
            if d.cop and d.timestamp >= cutoff
        ]

        cop_historico = [
            d.cop for d in chiller.history
            if d.cop and d.timestamp < cutoff
        ]

        if not cop_reciente or not cop_historico:
            return {"degradado": False, "confianza": 0, "degradacion_pct": 0}

        media_reciente = float(np.mean(cop_reciente))
        media_historica = float(np.mean(cop_historico))

        if chiller.id in self.modelos:
            hora_media = float(np.mean([d.timestamp.hour for d in chiller.history[-50:]]))
            cop_esperado = self.predecir_cop(chiller.id, hora_media, 28, 50)
        else:
            cop_esperado = media_historica * 1.02

        degradacion = (cop_esperado - media_reciente) / cop_esperado

        if degradacion > self.umbral_degradacion:
            confianza = min(0.95, 0.5 + degradacion)
            return {
                "degradado": True,
                "degradacion_pct": round(degradacion * 100, 1),
                "cop_actual": round(media_reciente, 2),
                "cop_esperado": round(cop_esperado, 2),
                "confianza": round(confianza, 2)
            }

        return {
            "degradado": False,
            "degradacion_pct": round(degradacion * 100, 1),
            "cop_actual": round(media_reciente, 2),
            "cop_esperado": round(cop_esperado, 2),
            "confianza": 0
        }

    def calcular_ahorro_potencial(self, chiller: Chiller, cop_objetivo: float) -> Tuple[float, float]:
        if not chiller.last_data or not chiller.last_data.power_kw:
            return (0, 0)

        cop_actual = chiller.last_data.cop or 3.5
        if cop_actual >= cop_objetivo:
            return (0, 0)

        power_actual = chiller.last_data.power_kw
        cooling = chiller.last_data.cooling_kw
        if cooling == 0 or not cooling:
            cooling = power_actual * cop_actual

        power_objetivo = cooling / cop_objetivo

        ahorro_kw = power_actual - power_objetivo
        ahorro_euro_dia = ahorro_kw * 24 * self.precio_kwh

        return (round(ahorro_kw, 1), round(ahorro_euro_dia, 1))

    def optimizar(self, chillers: List[Chiller], temp_exterior: float, ocupacion: float = 1.0) -> List[OptimizacionResult]:
        resultados = []
        ahora = datetime.now()

        hora = ahora.hour
        demanda = self.predecir_demanda(hora, temp_exterior, ocupacion)
        secuencia = self.calcular_secuencia_optima(demanda, chillers)

        for i, chiller in enumerate(chillers):
            if chiller.id not in self.modelos:
                self.entrenar_modelo_chiller(chiller)

            degradacion = self.detectar_degradacion(chiller)

            if degradacion["degradado"]:
                cop_objetivo = degradacion["cop_esperado"]
            else:
                cop_objetivo = self.predecir_cop(chiller.id, hora, temp_exterior, 50)

            ahorro_kw, ahorro_euro = self.calcular_ahorro_potencial(chiller, cop_objetivo)

            if degradacion["degradado"]:
                recomendacion = (
                    f"Chiller {chiller.id} presenta degradación del {degradacion['degradacion_pct']}%. "
                    f"COP actual: {degradacion['cop_actual']:.2f} (esperado: {degradacion['cop_esperado']:.2f}). "
                    "Programar mantenimiento."
                )
            elif secuencia[i]:
                recomendacion = f"Chiller {chiller.id} operando normalmente. Mantener secuencia actual."
            else:
                recomendacion = f"Chiller {chiller.id} en standby. Listo para entrar según demanda."

            if ahorro_euro > 10:
                recomendacion += f" Ajustando parámetros podría ahorrar {ahorro_euro:.0f}€/día."

            resultado = OptimizacionResult(
                chiller_id=chiller.id,
                cop_actual=(chiller.last_data.cop if (chiller.last_data and chiller.last_data.cop is not None) else 0.0),
                cop_objetivo=round(cop_objetivo, 2),
                ahorro_potencial_kw=ahorro_kw,
                ahorro_potencial_euro_dia=ahorro_euro,
                recomendacion=recomendacion,
                confianza=degradacion["confianza"] if degradacion["degradado"] else 0.8,
                timestamp=ahora
            )

            resultados.append(resultado)

            ai_logger.info(
                f"{chiller.id}: COP={resultado.cop_actual:.2f} | "
                f"Ahorro={ahorro_euro}€/dia | {recomendacion[:60]}..."
            )

        self.historial_optimizaciones.append({
            'timestamp': ahora,
            'demanda': demanda,
            'resultados': [r.__dict__ for r in resultados]
        })

        return resultados

    def get_estadisticas_globales(self, chillers: List[Chiller]) -> Dict:
        if not chillers:
            return {}

        cops = [c.last_data.cop for c in chillers if c.last_data and c.last_data.cop]
        potencias = [c.last_data.power_kw for c in chillers if c.last_data]
        degradados = [self.detectar_degradacion(c) for c in chillers]

        ahorro_total = sum(
            self.calcular_ahorro_potencial(c, 4.0)[1]
            for c in chillers
        )

        return {
            'num_chillers': len(chillers),
            'cop_medio': round(float(np.mean(cops)), 2) if cops else 0,
            'cop_max': round(float(max(cops)), 2) if cops else 0,
            'cop_min': round(float(min(cops)), 2) if cops else 0,
            'potencia_total_kw': round(float(sum(potencias)), 1) if potencias else 0,
            'ahorro_potencial_diario_euro': round(float(ahorro_total), 0),
            'chillers_degradados': sum(1 for d in degradados if d['degradado']),
            'timestamp': datetime.now().isoformat()
        }
