# Emergency Control — Parcial de Fundamentos de IA

Proyecto completo del parcial: agente UCS, API FastAPI, simulador y frontend React/Vite.

## Estructura

```text
project/
├── backend/
│   ├── src/
│   └── tests/
├── frontend/
├── scenarios/
│   └── scenario.json
├── design.md
├── pyproject.toml
└── README.md
```

## 1. Backend

Abrir una terminal:

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Instalar:

```bash
pip install -r requirements.txt
```

Ejecutar pruebas desde `project`:

```bash
cd ..
pytest -q
```

Iniciar servidor:

```bash
cd backend
uvicorn src.main:app --reload
```

Backend: `http://127.0.0.1:8000`

## 2. Frontend

En otra terminal:

```bash
cd frontend
npm install
npm run dev
```

Abrir la URL mostrada por Vite, normalmente `http://localhost:5173`.

## 3. Probar una misión

1. Mantener el backend ejecutándose.
2. Abrir el frontend.
3. Cargar el escenario de `scenarios/scenario.json` mediante la interfaz.
4. Ejecutar **Solve** para solicitar el plan al endpoint `POST /api/solve`.
5. Ejecutar el plan en la simulación.
6. Verificar posición, batería, progreso, acciones, costo acumulado y estado final.

## 4. Interpretar el resultado

`solution_found: true` indica que el agente encontró un plan válido. `total_cost` es la suma de los costos oficiales de sus pasos. `solution_found: false` y `steps: []` indican que no encontró una solución dentro del espacio explorado.

El agente toma del escenario el mapa, costos, recursos, batería, puertas, paneles, estaciones y objetivo; no selecciona una secuencia especial por el identificador de una instancia.

## 5. Decisiones de IA

La formalización completa del estado, acciones, transición, meta, costo, UCS, dominancia de batería y restricción de `DROP` está documentada en `design.md`.
