# CufeBuscador

> Verificador automático de CUFEs en el portal de la DIAN

---

## ¿Qué hace este script?

**CufeBuscador** es un script de Python que lee un archivo Excel con una lista de CUFEs (Código Único de Facturación Electrónica), consulta cada uno en el portal oficial de la DIAN (`catalogo-vpfe.dian.gov.co`) y devuelve un nuevo archivo Excel con el estado de cada factura electrónica.

En Colombia, toda transacción comercial genera una factura electrónica identificada por su CUFE. Este código permite verificar ante la DIAN si la factura ha sido recibida, aceptada, reclamada o pagada por el cliente.

---

## Requisitos

### Software

| Requisito | Versión mínima | Notas |
|---|---|---|
| Python | 3.9+ | Recomendado 3.11 |
| Google Chrome | Cualquier versión reciente | Debe estar instalado en el sistema |
| ChromeDriver | Compatible con Chrome instalado | Se gestiona automáticamente con `webdriver-manager` |

### Dependencias Python

```bash
pip install pandas selenium capsolver python-dotenv openpyxl
```

### Clave de API

El script utiliza **Capsolver** para resolver el CAPTCHA Cloudflare Turnstile que protege el portal de la DIAN. Se requiere una cuenta activa en [capsolver.com](https://capsolver.com) con saldo disponible.

> **IMPORTANTE:** Sin una API key válida de Capsolver, el script no puede superar el CAPTCHA y no procesará ningún CUFE.

---

## Configuración

### Archivo `.env`

Cree un archivo llamado `.env` en la misma carpeta del script con el siguiente contenido:

```
CAPSOLVER_API_KEY=tu_clave_aqui
```

> **IMPORTANTE:** Nunca comparta ni suba el archivo `.env` a repositorios públicos.

### Archivo de entrada

El archivo Excel de entrada debe tener exactamente esta estructura:

| Columna requerida | Descripción |
|---|---|
| `CUFE/CUDE` | Código único de la factura electrónica (96 caracteres hexadecimales) |
| Otras columnas | Se conservan intactas en el archivo de salida |

El nombre del archivo de entrada está definido en el script:

```python
ARCHIVO_ENTRADA = "REVISION_CUFES_2025_134_1.xlsx"
```

---

## Cómo ejecutarlo

1. Asegúrese de tener el archivo `.env` con la API key configurada.
2. Coloque el archivo Excel de entrada en la misma carpeta que el script.
3. Ejecute el script desde la terminal:

```bash
python CufeBuscador.py
```

4. El script mostrará el progreso en consola para cada CUFE procesado.
5. Al finalizar, se generará el archivo de salida en la misma carpeta.

### Salida esperada en consola

```
✓ 150 CUFEs cargados

🚀 Iniciando procesamiento de facturas...

[1/150] Procesando: a1b2c3d4...
   → Resolviendo captcha...
   ✓ Captcha resuelto
   → Ingresando CUFE...
   ✓ Código: 034 | Estado: Aceptacion tacita de la factura electronica de venta

[2/150] Procesando: e5f6g7h8...
   ...

============================================================
✓ Proceso completado exitosamente
✓ Archivo guardado: REVISION_CUFES_2025_134_1_con_Estado.xlsx
✓ Total procesados: 150
============================================================
```

---

## Archivo de salida

El script genera un nuevo archivo Excel con el mismo contenido del archivo de entrada más dos columnas adicionales al final:

| Columna nueva | Descripción | Ejemplo |
|---|---|---|
| `Código Evento` | Código numérico del último evento registrado | `034` |
| `Estado de factura` | Descripción legible del estado | Aceptacion tacita de la factura electronica de venta |

### Códigos de estado posibles

| Código | Significado |
|---|---|
| `030` | Acuse de recibo de la factura electrónica de venta |
| `031` | Reclamo de la factura electrónica de venta |
| `032` | Recibo del bien o prestación del servicio |
| `033` | Aceptación expresa de la factura electrónica de venta |
| `034` | Aceptación tácita de la factura electrónica de venta |
| `040` | Recibida por el cliente - Pagada |
| `041` | Refacturación |
| `Sin eventos` | La factura no tiene eventos asociados en la DIAN |
| `Error` | No fue posible consultar el CUFE (ver consola para detalles) |

---

## Errores frecuentes

**`CAPSOLVER_API_KEY` no configurada**

```
IMPORTANTE: CAPSOLVER_API_KEY no configurada
El script continuará pero no podrá resolver el CAPTCHA.
```

Solución: Verifique que el archivo `.env` existe y contiene la clave correcta.

---

**Columna `CUFE/CUDE` no encontrada**

El archivo Excel no tiene una columna con ese nombre exacto. Verifique que el encabezado sea `CUFE/CUDE` (respetando mayúsculas, la barra y la tilde).

---

**El script se detiene sin procesar**

Puede deberse a que la DIAN cambió la estructura de su portal. Revise si el ID del campo de búsqueda sigue siendo `DocumentKey` y si el selector del CAPTCHA (`[data-sitekey]`) sigue presente.

---

## Notas importantes

- El script usa Chrome en modo **headless** (sin ventana visible). Chrome debe estar instalado en el sistema.
- Cada consulta tarda entre **8 y 15 segundos** por el tiempo de resolución del CAPTCHA. Para 150 CUFEs el proceso puede tardar entre 20 y 40 minutos.
- El uso de Capsolver tiene **costo por cada CAPTCHA resuelto**. Consulta el precio vigente en [capsolver.com](https://capsolver.com).
- Este script está diseñado para **uso interno** y no debe exponerse como servicio público.
