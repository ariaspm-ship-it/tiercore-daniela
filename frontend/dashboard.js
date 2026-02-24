// DANIELA - Dashboard Frontend v1.0

// Estado global
let socket;
let chart;
let historyData = [];
let alerts = [];

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
  console.log('🚀 Iniciando Daniela dashboard...');
    
  // Conectar a API
  fetchData();
    
  // Actualizar cada 5 segundos
  setInterval(fetchData, 5000);
    
  // Inicializar gráfica
  initChart();
});

// Obtener datos de la API
async function fetchData() {
  try {
    // Datos del UPS
    const upsRes = await fetch('http://localhost:8000/api/v1/ups/ups-01');
    const upsData = await upsRes.json();
    updateUPSDisplay(upsData);
        
    // Alertas
    const alertsRes = await fetch('http://localhost:8000/api/v1/alerts');
    const alertsData = await alertsRes.json();
    updateAlerts(alertsData.alerts);
        
    // Predicciones
    const predRes = await fetch('http://localhost:8000/api/v1/predictions');
    const predData = await predRes.json();
    updatePredictions(predData);
        
    // Actualizar histórico
    updateHistory(upsData.data);
        
  } catch (error) {
    console.log('Usando datos simulados...');
    updateSimulatedData();
  }
}

// Actualizar display del UPS
function updateUPSDisplay(data) {
  const d = data.data || {};
    
  // Valores básicos
  document.getElementById('load-value').textContent = d.ups_load?.toFixed(1) + '%' || '0%';
  document.getElementById('load-bar').style.width = (d.ups_load || 0) + '%';
    
  document.getElementById('battery-value').textContent = d.battery_charge?.toFixed(1) + '%' || '0%';
  document.getElementById('battery-bar').style.width = (d.battery_charge || 0) + '%';
    
  document.getElementById('temperature').textContent = (d.temperature?.toFixed(1) || '--') + '°C';
    
  const runtime = d.runtime_remaining || 0;
  document.getElementById('runtime').textContent = Math.round(runtime / 60) + 'min';
    
  document.getElementById('input-voltage').textContent = (d.input_voltage?.toFixed(1) || '--') + 'V';
  document.getElementById('battery-voltage').textContent = (d.battery_voltage?.toFixed(1) || '--') + 'V';
    
  // Salud batería (calculada)
  const health = calculateHealth(d);
  document.getElementById('health-value').textContent = health + '%';
  document.getElementById('health-bar').style.width = health + '%';
}

// Calcular salud batería
function calculateHealth(data) {
  if (!data.battery_charge) return 95;
    
  // Fórmula simple: carga actual + factor temperatura + factor edad
  let health = data.battery_charge;
    
  if (data.temperature > 28) {
    health -= (data.temperature - 28) * 2;
  }
    
  return Math.max(0, Math.min(100, Math.round(health)));
}

// Actualizar alertas
function updateAlerts(newAlerts) {
  const alertsList = document.getElementById('alerts-list');
  alerts = newAlerts;
    
  if (alerts.length === 0) {
    alertsList.innerHTML = '<div class="alert" style="background: #0d1b2b">✅ No hay alertas activas</div>';
    return;
  }
    
  alertsList.innerHTML = alerts.map(alert => `
    <div class="alert ${alert.severity}">
      <strong>${alert.severity.toUpperCase()}</strong><br>
      ${alert.text}<br>
      <small>${new Date(alert.timestamp).toLocaleString()}</small>
    </div>
  `).join('');
}

// Actualizar predicciones IA
function updatePredictions(pred) {
  const predDiv = document.getElementById('predictions');
  if (!pred || Object.keys(pred).length === 0) {
    predDiv.innerHTML = '<p>Analizando datos para predicciones...</p>';
    return;
  }
    
  const iaMsg = document.getElementById('ia-message');
    
  if (pred.failure_probability > 0.2) {
    iaMsg.textContent = `⚠️ Probabilidad de fallo del ${Math.round(pred.failure_probability * 100)}% en próximos días. Recomiendo revisión.`;
  } else if (pred.trend === 'up' && pred.predicted_load > 80) {
    iaMsg.textContent = `📈 Tendencia de carga al alza. Posible expansión necesaria.`;
  } else {
    iaMsg.textContent = `✅ Todo estable. Próximo mantenimiento estimado en ${pred.next_maintenance_days || 90} días.`;
  }
    
  predDiv.innerHTML = `
    <div>Tendencia: ${pred.trend === 'up' ? '📈' : '📉'}</div>
    <div>Carga prevista: ${pred.predicted_load?.toFixed(1) || '--'}%</div>
    <div>Riesgo fallo: ${Math.round((pred.failure_probability || 0) * 100)}%</div>
  `;
}

// Actualizar histórico y gráfica
function updateHistory(data) {
  if (!data) return;
    
  historyData.push({
    time: new Date().toLocaleTimeString(),
    load: data.ups_load || 0,
    temp: data.temperature || 0
  });
    
  if (historyData.length > 50) {
    historyData.shift();
  }
    
  if (chart) {
    chart.data.labels = historyData.map(d => d.time);
    chart.data.datasets[0].data = historyData.map(d => d.load);
    chart.data.datasets[1].data = historyData.map(d => d.temp);
    chart.update();
  }
}

// Inicializar gráfica
function initChart() {
  const ctx = document.getElementById('load-chart').getContext('2d');
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Carga (%)',
          data: [],
          borderColor: '#00b8d9',
          backgroundColor: 'rgba(0, 184, 217, 0.1)',
          tension: 0.4
        },
        {
          label: 'Temperatura (°C)',
          data: [],
          borderColor: '#ff9800',
          backgroundColor: 'rgba(255, 152, 0, 0.1)',
          tension: 0.4,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: { beginAtZero: true, max: 100, grid: { color: '#1e2f44' } },
        y1: { position: 'right', max: 50, grid: { display: false } }
      },
      plugins: { legend: { labels: { color: '#fff' } } }
    }
  });
}

// Datos simulados (para pruebas sin UPS)
function updateSimulatedData() {
  const simData = {
    data: {
      ups_load: 35 + Math.random() * 10,
      battery_charge: 92 + Math.random() * 5,
      temperature: 23 + Math.random() * 3,
      runtime_remaining: 1500 + Math.random() * 300,
      input_voltage: 220 + Math.random() * 5,
      battery_voltage: 12.5 + Math.random() * 0.5
    }
  };
  updateUPSDisplay(simData);
  updateHistory(simData.data);
    
  // Simular alertas periódicas
  if (Math.random() > 0.8) {
    updateAlerts([{
      severity: 'medium',
      text: 'Simulación: Temperatura ligeramente elevada',
      timestamp: new Date().toISOString()
    }]);
  }
    
  updatePredictions({
    trend: Math.random() > 0.5 ? 'up' : 'down',
    predicted_load: 40 + Math.random() * 20,
    failure_probability: Math.random() * 0.3,
    next_maintenance_days: 30 + Math.random() * 60
  });
}

// Modal baterías
function showBatteryForm() {
  document.getElementById('battery-modal').style.display = 'block';
  document.getElementById('change-date').valueAsDate = new Date();
}

function closeModal() {
  document.getElementById('battery-modal').style.display = 'none';
}

// Formulario registro baterías
document.getElementById('battery-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
    
  const data = {
    ups_id: 'ups-01',
    change_date: document.getElementById('change-date').value,
    battery_type: document.getElementById('battery-type').value,
    notes: document.getElementById('notes').value
  };
    
  try {
    await fetch('http://localhost:8000/api/v1/battery/replaced', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
        
    alert('✅ Cambio registrado correctamente');
    closeModal();
        
    // Actualizar historial
    const historyDiv = document.getElementById('battery-history');
    historyDiv.innerHTML = `
      <div class="alert" style="background: #0d1b2b">
        📅 Último cambio: ${data.change_date} (${data.battery_type})
      </div>
    `;
        
  } catch (error) {
    alert('Error al registrar: ' + error.message);
  }
});

// Cerrar modal al hacer clic fuera
window.onclick = (event) => {
  const modal = document.getElementById('battery-modal');
  if (event.target === modal) {
    modal.style.display = 'none';
  }
};