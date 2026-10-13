# Guía de usuario — Production Insight

Para supervisores, coordinadores e ingenieros de proceso.

Production Insight revisa los datos de producción, scrap y paros de tus líneas y te dice **qué investigar primero y por qué**. No reemplaza tu criterio: te ayuda a decidir por dónde empezar.

---

## 1. En resumen

1. Prepara dos archivos, en **Excel (.xlsx) o CSV**: **producción** y **paros**.
2. Abre el dashboard y carga **primero producción, después paros**.
3. En **Revisar por** elige día, semana o mes (por defecto, el último día con datos) y mira el **tablero de líneas**: las placas ámbar tienen alertas.
4. Abre la pestaña **Alertas** y empieza por la **prioridad 1**.
5. Revisa **Dónde investigar** en la ficha de la alerta y ve al piso.

---

## 2. Abrir el dashboard

En una terminal, dentro de la carpeta del proyecto:

```powershell
.venv\Scripts\activate
streamlit run app.py
```

Se abre el navegador en `http://localhost:8501`. Para cerrarlo, presiona `Ctrl + C` en la terminal.

---

## 3. Preparar los archivos

Puedes usar **Excel (.xlsx)** o **CSV**. La primera fila lleva los nombres de las columnas, exactamente como aparecen abajo.

- **Excel (.xlsx):** se lee la **primera hoja**. Las fechas pueden ser fechas de Excel (con cualquier formato de celda) y los números, números normales: el sistema los convierte solo.
- **CSV:** en Excel, *Guardar como → CSV UTF-8*. Las fechas deben ir como `AAAA-MM-DD`.
- **.xls** (Excel 97-2003) no se acepta: ábrelo en Excel y guárdalo como .xlsx.

### Archivo de producción

Una fila por **fecha + línea + turno + producto**. Si en un turno hubo cambio de modelo, van dos filas: una por producto.

| Columna | Qué poner | Ejemplo |
|---|---|---|
| `date` | Fecha en formato AAAA-MM-DD | `2026-09-30` |
| `line` | Línea, tal como está en la lista de líneas | `L1` |
| `shift` | Turno: 1, 2 o 3 | `2` |
| `product` | Producto, tal como está en la lista de productos | `Producto A` |
| `production_quantity` | Piezas procesadas en el turno, **incluyendo** el scrap | `1250` |
| `scrap_quantity` | Piezas de scrap | `42` |

```text
date,line,shift,product,production_quantity,scrap_quantity
2026-09-30,L1,1,Producto A,600,20
2026-09-30,L1,1,Producto B,550,31
```

### Archivo de paros

Una fila por **cada evento de paro**. Un turno puede tener varios.

| Columna | Qué poner | Ejemplo |
|---|---|---|
| `date`, `line`, `shift` | Igual que en producción | `2026-09-30`, `L1`, `1` |
| `product` | El producto que corría cuando ocurrió el paro | `Producto A` |
| `downtime_minutes` | Minutos del evento, número entero mayor que 0 | `35` |
| `downtime_reason` | Causa, tal como está en la lista de causas | `Falla de máquina` |

**Cambio de modelo:** el paro de `Ajuste / Cambio de modelo` se registra con el **producto que entra**.

### Causas de paro

| Causa | Tipo | Cuándo usarla |
|---|---|---|
| Falla de máquina | No programado | Cualquier falla, incluido el mantenimiento correctivo |
| Falta de material | No programado | La línea paró por no tener material |
| Problema de calidad | No programado | Paro para contener o corregir un problema de calidad |
| Ajuste / Cambio de modelo | No programado | Cambio de producto o ajuste de la línea |
| Mantenimiento | **Programado** | Mantenimiento **preventivo** planeado |
| Paro programado | **Programado** | Juntas, limpieza, capacitación |
| Otro | No programado | Lo que no encaje en las anteriores |

Los paros **programados** se muestran aparte y **no generan alertas**: son tiempo planeado, no pérdida.

---

## 4. Cargar los datos

En la barra lateral, **en este orden**:

1. **1. Producción (CSV o Excel)** → selecciona el archivo → **Cargar producción**.
2. **2. Paros (CSV o Excel)** → selecciona el archivo → **Cargar paros**.

El orden importa: cada paro debe corresponder a un registro de producción. Si cargas paros antes, se rechazan.

### Qué pasa si vuelves a cargar un archivo

El sistema **reemplaza el turno completo**: si un archivo trae el turno 2 de L1 del 30-sep, se borra lo que había de ese turno y se guarda lo nuevo. Los turnos que no vienen en el archivo no se tocan.

Esto sirve para **corregir** datos: corrige el archivo y vuelve a cargarlo.

### Leer el resultado de la carga

Después de cargar verás:

- **Filas leídas, guardadas y rechazadas.**
- **Turnos nuevos / reemplazados / rechazados.**
- Una **tabla de errores**, con la fila de Excel, la columna, el valor y el motivo.
- El botón **Descargar errores (CSV)**, para corregir el archivo con la lista a la mano.

**Si una fila de un turno tiene error, no se guarda ninguna fila de ese turno** y se conserva lo que ya había. Así no quedan turnos a medias.

### Errores comunes y cómo corregirlos

| Mensaje | Qué significa | Cómo corregirlo |
|---|---|---|
| Faltan columnas obligatorias | El archivo no tiene alguna columna o tiene otro nombre | Revisa la primera fila contra la sección 3 (en Excel, de la primera hoja) |
| Los archivos .xls no son compatibles | Formato viejo de Excel | Ábrelo en Excel y guárdalo como .xlsx |
| Fecha inválida; el formato es AAAA-MM-DD | Fecha escrita como `30/09/2026` o una fecha que no existe | Escríbela como `2026-09-30` |
| La fecha es posterior a hoy | Fecha futura | Revisa el año o el mes |
| La línea / el producto / la causa no está en la lista | Valor mal escrito o nuevo | Corrige el texto o agrégalo a la lista (sección 10) |
| Turno inválido; debe ser 1, 2 o 3 | Turno fuera de rango | Corrige el número |
| El scrap es mayor que la producción | El scrap supera las piezas procesadas | Revisa ambos números |
| Registro duplicado en el archivo | Dos filas con la misma fecha, línea, turno y producto | Deja una sola fila con el total |
| Rechazada: el turno … tiene filas inválidas | Esta fila está bien, pero otra del mismo turno no | Corrige la otra fila del turno |
| No existe registro de producción… Cargue primero la producción | Paro sin producción para esa fecha, línea, turno y producto | Carga producción primero, o revisa el producto del paro |
| El turno … suma N min de paro (máximo 480) | Los paros del turno superan las 8 horas | Revisa los minutos de los eventos de ese turno |

---

## 5. Elegir qué revisar: día, semana o mes

Arriba de la barra lateral está **Revisar por**:

| Opción | Qué revisas | Ejemplo |
|---|---|---|
| **Día** | Un día de lunes a sábado | miércoles 30 de septiembre de 2026 |
| **Semana** | De lunes a domingo | Semana del 28-sep al 04-oct |
| **Mes** | El mes completo | septiembre 2026 |

Debajo eliges cuál; la lista va del más reciente al más antiguo. Por defecto se abre en **Día**, con el último día hábil con datos.

Lo que elijas cambia **todo el dashboard**: el tablero de líneas, el Resumen, las Alertas y las pestañas Producción, Calidad y Paros. Solo Calidad de datos revisa siempre todo lo cargado.

- **Día:** responde "¿qué pasó ayer?".
- **Semana:** muestra las alertas de cada día de la semana, con su fecha, y las tendencias día por día. Sirve para la junta semanal y para ver si un problema se repitió.
- **Mes:** muestra las alertas del mes y las tendencias semana por semana.

Cada día se compara solo contra los días **anteriores** a él, como si fuera el último día con datos. Los primeros días cargados (unas dos semanas) aparecen como "Sin evaluar" porque todavía no tienen suficiente historia.

---

## 6. El tablero de líneas

Arriba de las pestañas hay una placa por línea. Muestra el estado del **día evaluado**:

| Placa | Significado |
|---|---|
| ▲ Barra **ámbar**, "N alertas" | La línea tuvo un comportamiento fuera de lo normal. Abajo dice qué y con qué prioridad. |
| ● Barra **verde**, "Normal" | La línea se comportó como de costumbre. |
| ○ Barra **gris**, "Sin evaluar" | No hay datos suficientes para compararla. |

---

## 7. Siempre sabes qué periodo estás viendo

Toda la pantalla usa el periodo elegido en **Revisar por**, y lo dice con palabras:

- Arriba: "Revisión de la semana del 28 de septiembre al 4 de octubre de 2026".
- En las pestañas: "Acumulado de la semana del 28 de septiembre al 4 de octubre de 2026, según los filtros".
- En cada alerta, la fecha exacta: "~115 piezas el 30-sep".

Los filtros de **línea, producto y turno** se aplican encima del periodo.

---

## 8. Qué hacer con una alerta

### Cómo se decide que algo es una alerta

Cada línea se compara **contra su propio historial**: los días hábiles anteriores (lunes a sábado). Si el día evaluado se aleja mucho de lo normal para esa línea, y hacia el lado malo, se genera una alerta.

Se revisan tres cosas por línea:

| Métrica | Alerta cuando… |
|---|---|
| Scrap rate | sube |
| Producción por turno disponible | baja |
| Paro no programado por turno | sube |

"Por turno disponible" significa que los paros **programados** no cuentan como producción perdida: si hubo una junta de 2 horas, el sistema no espera la producción de un turno completo.

### Cómo leer la ficha

| Parte | Qué te dice |
|---|---|
| **Valor actual** | Cómo estuvo la línea el día evaluado |
| **Línea base** | Lo normal para esa línea, y con cuántos días se calculó |
| **Desviación** | Qué tan lejos de lo normal estuvo |
| **Impacto** | Piezas perdidas ese día y en los últimos 6 días hábiles |
| **Recurrencia** | Cuántos de los últimos 6 días hábiles pasó lo mismo |
| **Dónde investigar** | El producto, la causa o el turno que más pesó: **por dónde empezar** |

"Dónde investigar" señala **dónde mirar primero**, no la causa raíz. La causa la encuentras tú en el piso.

### Cómo se ordenan las alertas

```text
Prioridad = piezas perdidas en los últimos 6 días hábiles × días que se repitió
```

Un problema que **se repite** sube de prioridad, porque probablemente sigue activo. Un problema muy grande de un solo día también puede quedar arriba.

**El puntaje es una ayuda para decidir, no una verdad absoluta.** Si tu experiencia te dice que otra alerta es más urgente, tu criterio manda.

### Pasos sugeridos

1. Empieza por la **prioridad 1**.
2. Lee **Dónde investigar**: producto, causa o turno.
3. Confírmalo en las pestañas:
   - **Calidad → mapa de calor por turno y semana**: ¿es siempre el mismo turno?
   - **Paros → causas de paro**: ¿qué causa domina?
4. Ve al piso con esa pista concreta.

---

## 9. Las pestañas

| Pestaña | Pregunta que responde |
|---|---|
| **Resumen** | ¿Cuál es el problema más importante del periodo? ¿Qué pasó en el periodo? |
| **Alertas** | ¿Qué investigo primero? ¿Por qué se marcó? ¿Falta algo en la evaluación? |
| **Producción** | ¿Qué línea, producto o turno produjo más o menos? |
| **Calidad** | ¿Dónde está el scrap? ¿Está empeorando? ¿Está siempre en el mismo turno? |
| **Paros** | ¿Cuánto paro es pérdida real? ¿Cuáles son las causas principales? ¿Está aumentando? |
| **Calidad de datos** | ¿Puedo confiar en los números? ¿Faltan datos? ¿Qué se cargó y cuándo? |

En las gráficas de tendencia puedes agrupar por **día, semana o mes** con el selector de la barra lateral. Pasa el cursor sobre una barra o un punto para ver el valor exacto.

---

## 10. Mantener las listas

Las listas viven en archivos CSV en `data/master/`. Se editan con Excel o un editor de texto.

| Archivo | Para qué |
|---|---|
| `lines.csv` | Líneas válidas |
| `products.csv` | Productos válidos |
| `downtime_reasons.csv` | Causas de paro y si son programadas (`sí` / `no`) |
| `planned_stops.csv` | Días o turnos en que una línea **no** va a trabajar |

**Agregar un producto, línea o causa:** agrega una fila al archivo correspondiente, con el nombre escrito exactamente como se capturará (mayúsculas y acentos incluidos).

**Días sin programa** (festivos, línea sin plan): agrégalos a `planned_stops.csv` para que no aparezcan como datos faltantes:

```text
date,line,shift,reason
2026-09-16,L3,3,Sin programa
2026-12-25,L1,,Día festivo
```

Si dejas el turno vacío, aplica a **todo el día**.

**Domingos:** el domingo no se espera producción. Si se trabaja tiempo extra, carga los datos normalmente: se cuentan en los indicadores y aparecen como "turnos extra", pero no se usan para calcular lo normal ni generan alertas.

---

## 11. Preguntas frecuentes

**¿Por qué una línea dice "Sin evaluar"?**
Necesita al menos 10 días hábiles de historia para saber qué es normal. Con menos, no se generan alertas para esa línea.

**¿Por qué no salió alerta si el scrap estuvo alto?**
Se compara contra lo normal **de esa misma línea**. Si una línea siempre tiene scrap alto, no es una alerta (es un problema crónico, visible en la pestaña Calidad). Las alertas detectan **cambios**.

**¿Cómo veo las alertas de días anteriores o de toda la semana?**
En **Revisar por** elige Día (y el día) o Semana. Ver sección 5.

**Aparecen "paros sin registro de producción". ¿Qué hago?**
Pasa cuando recargas producción y un producto desaparece de un turno: sus paros se quedan sin registro. Vuelve a cargar el archivo de paros de ese turno.

**¿Cómo borro todo y empiezo de cero?**
Al final de la barra lateral, en **Borrar datos**, abre *Borrar todos los datos cargados*, marca la confirmación y presiona **Borrar todos los datos**. Se borran producción, paros e historial de cargas; las listas de líneas, productos y causas no se tocan. No se puede deshacer.

**¿Puedo probar sin datos reales?**
Sí. Carga `data/sample/production.csv` y después `data/sample/downtime.csv`. Son datos de ejemplo con problemas incluidos a propósito.
