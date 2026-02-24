# core/database.py
# Sistema de base de datos con TimescaleDB para series temporales

from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, Boolean, JSON, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timedelta
import os
from contextlib import contextmanager

from core.config import Config
from core.logger import main_logger

Base = declarative_base()

# ============================================
# MODELOS
# ============================================

class LecturaHabitacion(Base):
    """Modelo para lecturas de habitaciones (TimescaleDB optimizado)"""
    __tablename__ = 'lecturas_habitacion'
    __table_args__ = (
        Index('idx_habitacion_tiempo', 'room_id', 'timestamp'),
        Index('idx_edificio_tiempo', 'edificio', 'timestamp'),
    )
    
    id = Column(Integer, primary_key=True)
    room_id = Column(String(10), nullable=False, index=True)
    edificio = Column(String(1), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Métricas
    electricity_kwh = Column(Float)
    water_cold_m3 = Column(Float)
    water_hot_m3 = Column(Float)
    fc_kwh = Column(Float)
    return_temp = Column(Float)
    fuga_detectada = Column(Boolean, default=False)
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(20), default='simulador')  # 'simulador', 'bacnet', 'manual'


class LecturaChiller(Base):
    """Modelo para lecturas de chillers"""
    __tablename__ = 'lecturas_chiller'
    __table_args__ = (
        Index('idx_chiller_tiempo', 'chiller_id', 'timestamp'),
    )
    
    id = Column(Integer, primary_key=True)
    chiller_id = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    temp_supply = Column(Float)
    temp_return = Column(Float)
    power_kw = Column(Float)
    cooling_kw = Column(Float)
    cop = Column(Float)
    compressor_status = Column(Integer)
    alarm = Column(Boolean)
    flow_m3h = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class LecturaPanel(Base):
    """Modelo para lecturas de paneles eléctricos"""
    __tablename__ = 'lecturas_panel'
    
    id = Column(Integer, primary_key=True)
    panel_id = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    voltage = Column(Float)
    current = Column(Float)
    power_kw = Column(Float)
    frequency = Column(Float)
    breaker_status = Column(Integer)
    alarm = Column(Boolean)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class Alerta(Base):
    """Modelo para alertas generadas"""
    __tablename__ = 'alertas'
    
    id = Column(Integer, primary_key=True)
    alerta_id = Column(String(50), unique=True, index=True)
    tipo = Column(String(20))  # 'fuga', 'chiller', 'panel', 'mantenimiento'
    severidad = Column(String(10))  # 'baja', 'media', 'alta', 'critica'
    dispositivo_id = Column(String(20), index=True)
    mensaje = Column(String(500))
    recomendacion = Column(String(500))
    datos = Column(JSONB)  # Datos adicionales en formato JSON
    timestamp = Column(DateTime, index=True)
    leida = Column(Boolean, default=False)
    resuelta = Column(Boolean, default=False)
    fecha_resolucion = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class ConsumoDiario(Base):
    """Modelo para consumos diarios agregados (reporting)"""
    __tablename__ = 'consumo_diario'
    
    id = Column(Integer, primary_key=True)
    fecha = Column(DateTime, nullable=False, index=True)
    edificio = Column(String(1), index=True)
    dispositivo_id = Column(String(20), index=True)
    tipo = Column(String(20))  # 'habitacion', 'chiller', 'panel', 'villa'
    
    electricity_kwh = Column(Float, default=0)
    water_m3 = Column(Float, default=0)
    coste_electricidad = Column(Float, default=0)
    coste_agua = Column(Float, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_consumo_fecha_tipo', 'fecha', 'tipo'),
    )


# ============================================
# GESTOR DE BASE DE DATOS
# ============================================

class Database:
    """Gestor de base de datos con soporte TimescaleDB"""
    
    def __init__(self):
        self.engine = None
        self.Session = None
        self._connect()
    
    def _connect(self):
        """Conecta a la base de datos"""
        db_url = Config.DATABASE_URL
        
        # Configurar según tipo de BD
        if 'sqlite' in db_url:
            self.engine = create_engine(
                db_url, 
                echo=False,
                connect_args={'check_same_thread': False}
            )
        else:
            # Para PostgreSQL con TimescaleDB
            self.engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600
            )
        
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        main_logger.info(f"✅ Conectado a BD: {db_url}")
    
    def create_tables(self):
        """Crea las tablas si no existen"""
        Base.metadata.create_all(self.engine)
        
        # Si es TimescaleDB, crear hypertables
        if 'postgresql' in Config.DATABASE_URL:
            with self.engine.connect() as conn:
                # Crear hypertables para series temporales
                conn.execute(
                    "SELECT create_hypertable('lecturas_habitacion', 'timestamp', if_not_exists => TRUE);"
                )
                conn.execute(
                    "SELECT create_hypertable('lecturas_chiller', 'timestamp', if_not_exists => TRUE);"
                )
                conn.execute(
                    "SELECT create_hypertable('lecturas_panel', 'timestamp', if_not_exists => TRUE);"
                )
                conn.commit()
        
        main_logger.info("✅ Tablas creadas/verificadas")
    
    @contextmanager
    def session_scope(self):
        """Contexto para sesiones de BD"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            main_logger.error(f"Error en BD: {e}")
            raise
        finally:
            session.close()
    
    # ========================================
    # MÉTODOS PARA HABITACIONES
    # ========================================
    
    def save_lectura_habitacion(self, room_id, edificio, data):
        """Guarda una lectura de habitación"""
        with self.session_scope() as session:
            lectura = LecturaHabitacion(
                room_id=room_id,
                edificio=edificio,
                timestamp=data.timestamp,
                electricity_kwh=data.electricity_kwh,
                water_cold_m3=data.water_cold_m3,
                water_hot_m3=data.water_hot_m3,
                fc_kwh=data.fc_kwh,
                return_temp=data.return_temp,
                fuga_detectada=data.fuga_detectada,
                source='simulador'
            )
            session.add(lectura)
    
    def get_historico_habitacion(self, room_id, days=30):
        """Recupera histórico de una habitación"""
        with self.session_scope() as session:
            desde = datetime.now() - timedelta(days=days)
            return session.query(LecturaHabitacion).filter(
                LecturaHabitacion.room_id == room_id,
                LecturaHabitacion.timestamp >= desde
            ).order_by(LecturaHabitacion.timestamp).all()
    
    def get_ultimas_lecturas_habitacion(self, room_id, limit=100):
        """Últimas lecturas de una habitación"""
        with self.session_scope() as session:
            return session.query(LecturaHabitacion).filter(
                LecturaHabitacion.room_id == room_id
            ).order_by(LecturaHabitacion.timestamp.desc()).limit(limit).all()
    
    # ========================================
    # MÉTODOS PARA CHILLERS
    # ========================================
    
    def save_lectura_chiller(self, chiller_id, data):
        """Guarda una lectura de chiller"""
        with self.session_scope() as session:
            lectura = LecturaChiller(
                chiller_id=chiller_id,
                timestamp=data.timestamp,
                temp_supply=data.temp_supply,
                temp_return=data.temp_return,
                power_kw=data.power_kw,
                cooling_kw=data.cooling_kw,
                cop=data.cop,
                compressor_status=data.compressor_status,
                alarm=data.alarm,
                flow_m3h=data.flow_m3h
            )
            session.add(lectura)
    
    def get_historico_chiller(self, chiller_id, days=30):
        """Recupera histórico de un chiller"""
        with self.session_scope() as session:
            desde = datetime.now() - timedelta(days=days)
            return session.query(LecturaChiller).filter(
                LecturaChiller.chiller_id == chiller_id,
                LecturaChiller.timestamp >= desde
            ).order_by(LecturaChiller.timestamp).all()
    
    # ========================================
    # MÉTODOS PARA ALERTAS
    # ========================================
    
    def save_alerta(self, alerta):
        """Guarda una alerta"""
        with self.session_scope() as session:
            # Verificar si ya existe (últimas 24h)
            existe = session.query(Alerta).filter(
                Alerta.alerta_id == alerta['alerta_id']
            ).first()
            
            if not existe:
                nueva = Alerta(
                    alerta_id=alerta['alerta_id'],
                    tipo=alerta.get('tipo', 'general'),
                    severidad=alerta.get('severidad', 'media'),
                    dispositivo_id=alerta.get('dispositivo_id', ''),
                    mensaje=alerta.get('mensaje', ''),
                    recomendacion=alerta.get('recomendacion', ''),
                    datos=alerta.get('datos', {}),
                    timestamp=alerta.get('timestamp', datetime.now())
                )
                session.add(nueva)
                return True
        return False
    
    def get_alertas_activas(self, limit=50):
        """Obtiene alertas no resueltas"""
        with self.session_scope() as session:
            return session.query(Alerta).filter(
                Alerta.resuelta == False
            ).order_by(Alerta.timestamp.desc()).limit(limit).all()
    
    def resolver_alerta(self, alerta_id):
        """Marca una alerta como resuelta"""
        with self.session_scope() as session:
            alerta = session.query(Alerta).filter(
                Alerta.alerta_id == alerta_id
            ).first()
            if alerta:
                alerta.resuelta = True
                alerta.fecha_resolucion = datetime.now()
                return True
        return False
    
    # ========================================
    # MÉTODOS DE AGREGACIÓN
    # ========================================
    
    def get_consumo_diario_edificio(self, edificio, fecha):
        """Obtiene consumo diario de un edificio"""
        with self.session_scope() as session:
            inicio = datetime(fecha.year, fecha.month, fecha.day)
            fin = inicio + timedelta(days=1)
            
            lecturas = session.query(LecturaHabitacion).filter(
                LecturaHabitacion.edificio == edificio,
                LecturaHabitacion.timestamp >= inicio,
                LecturaHabitacion.timestamp < fin
            ).all()
            
            total_elec = sum(l.electricity_kwh for l in lecturas)
            total_agua = sum(l.water_cold_m3 for l in lecturas)
            
            return {
                'fecha': fecha.isoformat(),
                'edificio': edificio,
                'electricidad_kwh': round(total_elec, 1),
                'agua_m3': round(total_agua, 1),
                'num_lecturas': len(lecturas)
            }
    
    def get_top_consumidores(self, edificio=None, limit=10):
        """Obtiene las habitaciones con mayor consumo"""
        with self.session_scope() as session:
            query = session.query(
                LecturaHabitacion.room_id,
                LecturaHabitacion.edificio,
                func.avg(LecturaHabitacion.electricity_kwh).label('avg_elec'),
                func.avg(LecturaHabitacion.water_cold_m3).label('avg_agua')
            )
            
            if edificio:
                query = query.filter(LecturaHabitacion.edificio == edificio)
            
            query = query.group_by(
                LecturaHabitacion.room_id, 
                LecturaHabitacion.edificio
            ).order_by(
                func.avg(LecturaHabitacion.electricity_kwh).desc()
            ).limit(limit)
            
            return query.all()
    
    def cleanup_old_data(self, days=365):
        """Elimina datos antiguos (opcional)"""
        with self.session_scope() as session:
            limite = datetime.now() - timedelta(days=days)
            
            # Eliminar lecturas antiguas
            session.query(LecturaHabitacion).filter(
                LecturaHabitacion.timestamp < limite
            ).delete()
            
            session.query(LecturaChiller).filter(
                LecturaChiller.timestamp < limite
            ).delete()
            
            main_logger.info(f"🧹 Limpieza completada: datos anteriores a {limite}")

# Instancia global
db = Database()
