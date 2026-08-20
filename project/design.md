# Diseño del agente

## Estado

### Definición formal

Represento una situación física mediante

```text
s = <z, b, P, GK, GT, GM, D, Pa, St>
```

- `z`: zona actual del robot.
- `b`: batería restante.
- `P`: multiconjunto canónico de objetos que lleva el robot. Cada elemento se representa como `(tipo, nombre)`, donde `tipo` es `key`, `tool` o `material`.
- `GK`: conjunto canónico `(id, zona)` de llaves que siguen en el suelo.
- `GT`: conjunto canónico `(id, zona)` de herramientas que siguen en el suelo.
- `GM`: conjunto canónico `(tipo, zona, cantidad)` de materiales en el suelo.
- `D`: estado de cada puerta.
- `Pa`: estado de cada panel.
- `St`: estado de cada estación.

El estado no contiene información de la historia de búsqueda.

### Por qué cada variable es necesaria

La posición `z` determina qué corredores, objetos e interacciones están disponibles. La batería `b` es necesaria porque una misma configuración con distinta energía puede tener distintas acciones legales: un movimiento puede ser posible en una y no en otra.

La carga `P` es necesaria por tres motivos: determina la capacidad disponible, permite abrir puertas y reparar paneles, y cambia cuando se recogen, consumen o sueltan objetos. La posición de los objetos `GK`, `GT` y `GM` también pertenece al estado porque `DROP` puede mover un objeto de una zona a otra.

Los estados de puertas, paneles y estaciones son permanentes cambios del mundo y condicionan acciones futuras. Una puerta abierta cambia la conectividad; un panel reparado habilita una estación; una estación en línea puede ser requisito de otra.

### Qué información se deriva y NO se almacena

No almaceno peso total, capacidad, batería máxima, costos de acciones, grafo de corredores ni requisitos de paneles/estaciones. Son constantes del escenario o se calculan a partir de él y del estado.

Tampoco almaceno `energy_spent`: es exactamente el costo acumulado `g(n)` del nodo. Guardarlo en el estado mezclaría situación física con historia.

### Qué pertenece al historial de búsqueda y no al estado físico

Cada nodo contiene `state`, `g`, `parent` y `action`. `g` dice cuánto costó llegar; `parent` permite reconstruir el plan; `action` registra la transición usada. Ninguno describe por sí mismo la situación física actual.

Esto permite que dos caminos diferentes lleguen al mismo estado y que Graph Search los compare mediante CLOSED/dominancia.

### Cuándo dos configuraciones son el mismo estado

Los elementos equivalentes se representan sin identificadores artificiales. En particular, los materiales son un tipo con cantidad, no individuos `FUSE1`, `FUSE2`, etc. Los conjuntos se ordenan antes de formar el estado hashable. Así, dos configuraciones físicamente iguales tienen exactamente la misma representación.

### Relevancia: objetos que ya no cambian el futuro

El mundo tiene cambios monotónicos: una puerta no se vuelve a cerrar, un panel reparado no vuelve a dañarse y una estación activada no vuelve a apagarse. Por eso una llave cuya puerta ya está abierta, una herramienta cuyos paneles ya están reparados o un material que ya no puede consumirse son objetos muertos.

El generador no crea estados de reubicación arbitraria. Un `DROP` de un objeto ya muerto se permite porque ese objeto ya no puede afectar ninguna acción futura. Si un objeto todavía es relevante, solo se permite soltarlo cuando su zona de origen es la zona actual; en ese caso puede recuperarse posteriormente sin introducir un desplazamiento adicional para recuperar el objeto. No se generan colocaciones de objetos relevantes en zonas arbitrarias. Esta restricción elimina las permutaciones de inventario que no aportan información nueva al problema de búsqueda.

## Acciones

| Acción | Precondiciones | Efectos | Costo |
|---|---|---|---:|
| `MOVE(z,z')` | corredor entre zonas, puerta abierta si existe, batería suficiente | cambia `z`, consume batería | costo oficial del corredor |
| `PICKUP(x)` | `x` está en la zona, capacidad suficiente, batería suficiente | quita `x` del suelo y lo añade a `P` | `pickup` |
| `DROP(x)` | `x` está en `P`, batería suficiente | quita `x` de `P` y lo deja en `z` | `drop` |
| `OPEN_DOOR(d)` | robot junto a la puerta, llave correspondiente en `P` | puerta pasa a `OPEN` | `interact` |
| `REPAIR(p,m)` | zona del panel, herramienta y material requeridos en `P` | panel pasa a `OK`, consume material | `interact` |
| `ACTIVATE(st)` | zona correcta y requisitos satisfechos | estación pasa a `ONLINE` | `interact` |
| `RECHARGE(c)` | robot junto al cargador y batería no máxima | batería vuelve a máxima | `recharge` |

Todas las acciones que consumen batería exigen `b >= costo`.

### `Applicable` interno vs legalidad del contrato

El simulador define qué operaciones son legalmente ejecutables, pero el generador de búsqueda puede usar un subconjunto sound. No genero `DROP` arbitrariamente en todas las zonas.

Genero `DROP` solo cuando la carga está llena y hay una razón de capacidad para liberar espacio. Un objeto muerto puede soltarse en cualquier zona porque ya no afecta ninguna acción futura. Un objeto todavía relevante solo puede soltarse en su zona de origen, de modo que volver a recogerlo no requiere una nueva ruta hacia otra zona. No genero `DROP` para reubicar objetos relevantes entre zonas arbitrarias, porque eso solo multiplica configuraciones de suelo y carga sin crear una ventaja de transporte que no pueda obtenerse manteniendo el objeto o recuperándolo desde su origen.

## Modelo de transición

```text
s --a--> s'
```

si `a` es aplicable y la batería permite pagar su costo. La transición es determinista.

`MOVE` cambia la zona y batería; `PICKUP`/`DROP` cambian carga y suelo; `OPEN_DOOR`, `REPAIR` y `ACTIVATE` cambian el entorno persistente; `RECHARGE` cambia la batería.

Después de cada transición los componentes se vuelven a representar en forma canónica: listas ordenadas y materiales agregados por `(tipo,zona)`.

## Prueba de meta

```text
Goal(s) <=> para todo st en goal.stations_online:
             St[st] = ONLINE
```

La meta se comprueba sobre el estado final del mundo. Las puertas y paneles son medios para alcanzar las estaciones, no requisitos finales salvo que la propia especificación de la misión los incluya.

## Función de costo

```text
g(n) = suma de los costos oficiales de las acciones del camino de la raíz a n
```

Se usan los costos del escenario: corredores, `pickup`, `drop`, `interact` y `recharge`. Minimizar el número de pasos no equivale a minimizar costo porque los corredores tienen costos diferentes; por ejemplo, un movimiento puede costar 3 y otro 12.

## Estrategia de búsqueda

Uso **Uniform Cost Search (UCS)** porque el objetivo es encontrar un plan de costo mínimo y todos los costos de transición son positivos en el escenario.

UCS mantiene una cola de prioridad ordenada por `g(n)`. Siempre expande primero el nodo con menor costo acumulado. La prueba de meta se hace al **extraer** el nodo de OPEN, no al generarlo. Con costos no negativos/positivos, esto garantiza que el primer objetivo extraído tenga costo mínimo.

La implementación es Graph Search: los estados se canonicalizan y se mantiene una frontera de dominancia por configuración física. Un estado con el mismo mundo y menor/equal costo pero mayor/equal batería domina a otro, porque cualquier continuación legal del dominado también puede ejecutarse desde el dominante y no costará más.

UCS es completo en este problema finito cuando existe solución y los costos tienen una cota positiva. Es óptimo bajo los mismos supuestos. Su tiempo y memoria son exponenciales en el peor caso; aquí el peligro no es solo el grado del mapa, sino la cantidad de configuraciones producidas por `PICKUP`/`DROP`.

Las garantías se rompen si aparecen costos negativos, si se cambia la representación y dos estados iguales dejan de compararse como iguales, o si la implementación deja de procesar OPEN hasta encontrar la meta mínima.

### Batería como recurso

La batería sí forma parte del estado. No obstante, no es necesario conservar todas las rutas a una misma configuración física. Para cada configuración guardo pares `(costo,batería)` no dominados.

Si A y B tienen el mismo mundo físico y

```text
cost(A) <= cost(B)  y  battery(A) >= battery(B)
```

B está dominado. Cualquier continuación que B pueda ejecutar también puede ejecutarse desde A y A llega con no mayor costo y no menor energía. Por ello B se descarta sin perder el óptimo.

## Formulación y tamaño del espacio

1. Cinco zonas no implican cinco estados. La combinación de zona, batería, puertas, paneles, estaciones, objetos en suelo y carga produce muchas configuraciones. Con varios objetos distinguibles, las permutaciones de dónde quedaron pueden multiplicar el espacio rápidamente.
2. `DROP` es especialmente peligroso porque, si se genera sin criterio, permite colocar cada objeto cargado en cualquiera de las zonas visitables. El algoritmo termina buscando permutaciones que no aportan nada.
3. Las podas principales son: representación canónica de materiales equivalentes; no generar drops arbitrarios; descartar objetos muertos; y dominancia `(costo,batería)` para una misma configuración física. Todas son sound porque eliminan rutas que no pueden mejorar un plan futuro.
4. Aumentar artificialmente la capacidad no resuelve el problema general y cambia las propiedades del escenario. Ignorar batería tampoco es correcto porque puede producir planes que el simulador no puede ejecutar. Reducir estaciones o corredores también cambiaría el problema, en lugar de resolverlo.
