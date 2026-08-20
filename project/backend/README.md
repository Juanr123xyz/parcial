# Backend — Emergency Control

Agente genérico de **Uniform Cost Search (UCS)** para Emergency Control.

## Requisitos
- Python 3.10+
- Dependencias de `requirements.txt`

## Instalar

Desde `project/backend`:

```bash
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

Luego:

```bash
pip install -r requirements.txt
```

## Ejecutar pruebas

Desde la carpeta `project`:

```bash
pytest -q
```

## Iniciar API

Desde `project/backend`:

```bash
uvicorn src.main:app --reload
```

La API expone:
- `GET /health`
- `POST /api/solve`

`POST /api/solve` recibe el escenario JSON completo y devuelve:

```json
{
  "solution_found": true,
  "total_cost": 63,
  "steps": [],
  "message": "..."
}
```

Cuando no hay solución:

```json
{
  "solution_found": false,
  "total_cost": 0,
  "steps": [],
  "message": "..."
}
```

## Diseño del agente

- Estado canónico: zona, batería, carga, objetos en suelo, puertas, paneles y estaciones.
- Materiales equivalentes se representan por tipo y cantidad.
- UCS prioriza por costo acumulado `g(n)`.
- La meta se comprueba al extraer el nodo de menor costo de OPEN.
- Se conserva una frontera de etiquetas no dominadas por `(costo, batería)` para una misma configuración física.
- `DROP` se restringe a situaciones donde libera capacidad para recoger un objeto disponible, evitando permutaciones de colocación que no aportan al plan óptimo.
- Los costos, capacidad, batería, mapa, recursos, puertas y objetivo se leen del escenario.

## Frontend

Desde `project/frontend`:

```bash
npm install
npm run dev
```

Abrir la URL que indique Vite, normalmente `http://localhost:5173`.

El frontend llama a `/api/solve`; para desarrollo, Vite debe reenviar `/api` al backend según la configuración incluida.

> `src/demo_plan.py` es únicamente un fixture/manual de referencia para comprobar el simulador y la interfaz. El solver no lo importa ni lo usa para producir la respuesta de `/api/solve`.
