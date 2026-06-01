import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import capsolver
import re
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

CODIGO_ESTADO = {
    "030": "Acuse de recibo de la factura electronica de venta",
    "031": "Reclamo de la factura electronica de venta",
    "032": "Recibo del bien o prestacion del servicio",
    "033": "Aceptacion expresa de la factura electronica de venta",
    "034": "Aceptacion tacita de la factura electronica de venta",
    "040": "Recibida por el cliente - Pagada",
    "041": "Refacturacion",
    "Sin eventos": "No tiene eventos asociados"
}

capsolver.api_key = os.getenv("CAPSOLVER_API_KEY", "")
if not capsolver.api_key:
    print("⚠️  ADVERTENCIA: CAPSOLVER_API_KEY no configurada")

ARCHIVO_ENTRADA = "REVISION_CUFES_2025_134_1.xlsx"
ARCHIVO_SALIDA = "REVISION_CUFES_2025_134_1_con_Estado.xlsx"

def archivo_existe(nombre_archivo):
    return os.path.isfile(nombre_archivo)

def cargar_cufes(nombre_archivo):
    try:
        df = pd.read_excel(nombre_archivo)
        if 'CUFE/CUDE' not in df.columns:
            raise ValueError("Columna 'CUFE/CUDE' no encontrada")
        print(f"✓ {len(df)} CUFEs cargados\n")
        return df
    except Exception as e:
        print(f"✗ Error cargando archivo: {e}")
        raise

def resolver_captcha_turnstile(driver, site_key):
    """Resuelve Cloudflare Turnstile usando Capsolver"""
    try:
        url_actual = driver.current_url
        
        solucion = capsolver.solve({
            "type": "AntiTurnstileTaskProxyLess",
            "websiteURL": url_actual,
            "websiteKey": site_key,
        })
        
        token = None
        if solucion:
            if "token" in solucion:
                token = solucion["token"]
            elif "solution" in solucion and isinstance(solucion["solution"], dict):
                token = solucion["solution"].get("token")
        
        return token
        
    except Exception as e:
        print(f"   ✗ Error resolviendo captcha: {e}")
        return None

def inyectar_token_turnstile(driver, token):
    """Inyecta el token de Turnstile en la página"""
    try:
        time.sleep(2)
        
        resultado = driver.execute_script("""
            const token = arguments[0];
            let success = false;
            
            // Buscar inputs/textareas de respuesta
            const selectors = [
                'input[name*="cf-turnstile-response"]',
                'textarea[name*="cf-turnstile-response"]',
                'input[name="cf-turnstile-response"]',
                'textarea[name="cf-turnstile-response"]'
            ];
            
            for (const selector of selectors) {
                const elements = document.querySelectorAll(selector);
                if (elements.length > 0) {
                    elements.forEach(el => {
                        el.value = token;
                        success = true;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    });
                }
            }
            
            // Buscar callbacks del widget
            const widgets = document.querySelectorAll('[data-sitekey]');
            widgets.forEach((widget) => {
                const callbackName = widget.getAttribute('data-callback');
                if (callbackName && typeof window[callbackName] === 'function') {
                    try {
                        window[callbackName](token);
                        success = true;
                    } catch(e) {}
                }
                
                // Buscar en formularios asociados
                const form = widget.closest('form');
                if (form) {
                    const formInputs = form.querySelectorAll('input[name*="turnstile"], textarea[name*="turnstile"]');
                    formInputs.forEach(input => {
                        input.value = token;
                        success = true;
                    });
                }
            });
            
            // Inyección por ID
            const byId = document.getElementById('cf-turnstile-response');
            if (byId) {
                byId.value = token;
                success = true;
            }
            
            return success;
        """, token)
        
        return resultado
            
    except Exception as e:
        print(f"   ✗ Error inyectando token: {e}")
        return False

def verificar_captcha_resuelto(driver, max_intentos=10):
    """Verifica si el captcha fue resuelto"""
    for intento in range(max_intentos):
        try:
            tiene_token = driver.execute_script("""
                const inputs = document.querySelectorAll('input[name*="turnstile-response"], textarea[name*="turnstile-response"]');
                for (const input of inputs) {
                    if (input.value && input.value.length > 100) {
                        return true;
                    }
                }
                return false;
            """)
            
            captcha_visible = driver.execute_script("""
                const iframes = document.querySelectorAll('iframe[src*="challenges.cloudflare.com"]');
                for (const iframe of iframes) {
                    if (iframe.offsetParent !== null) {
                        return true;
                    }
                }
                return false;
            """)
            
            if tiene_token and not captcha_visible:
                return True
            
            time.sleep(1)
            
        except:
            pass
    
    return False

def obtener_codigos_evento_por_tag(driver):
    """Busca códigos de evento en la página de la DIAN"""
    codigos_validos = ['030', '031', '032', '033', '034']
    
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        texto_pagina = driver.find_element(By.TAG_NAME, "body").text
        
        # Verificar mensaje sin eventos
        mensajes_sin_eventos = [
            "No tiene eventos asociados",
            "No hay eventos asociados",
            "Sin eventos asociados"
        ]
        
        for mensaje in mensajes_sin_eventos:
            if mensaje in texto_pagina:
                return "Sin eventos", CODIGO_ESTADO["Sin eventos"]
        
        # Buscar códigos
        codigos_encontrados = []
        for codigo in codigos_validos:
            patron = r'\b' + codigo + r'\b'
            if re.search(patron, texto_pagina):
                codigos_encontrados.append(codigo)
        
        if codigos_encontrados:
            codigo_mayor = max(codigos_encontrados)
            estado = CODIGO_ESTADO.get(codigo_mayor, "Código desconocido")
            return codigo_mayor, estado
        
        return "Sin eventos", CODIGO_ESTADO["Sin eventos"]
        
    except Exception as e:
        print(f"   ✗ Error buscando códigos: {e}")
        return "Error", "Error en búsqueda"

def procesar_facturas():
    """Función principal que procesa las facturas"""
    
    if not archivo_existe(ARCHIVO_ENTRADA):
        print(f"✗ Archivo '{ARCHIVO_ENTRADA}' no encontrado")
        return

    df = cargar_cufes(ARCHIVO_ENTRADA)

    # Configurar Chrome
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    print("🚀 Iniciando procesamiento de facturas...\n")
    driver = webdriver.Chrome(options=options)
    
    # Ocultar detección de Selenium
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    })

    codigos_evento = []
    estados_factura = []
    errores_count = 0

    for idx, cufe in enumerate(df['CUFE/CUDE'], 1):
        print(f"[{idx}/{len(df)}] Procesando: {cufe}")
        
        try:
            driver.get("https://catalogo-vpfe.dian.gov.co/User/SearchDocument")
            time.sleep(3)

            # Resolver captcha si existe
            captcha_elements = driver.find_elements(By.CSS_SELECTOR, '[data-sitekey]')
            
            if captcha_elements:
                site_key = captcha_elements[0].get_attribute('data-sitekey')
                print(f"   → Resolviendo captcha...")
                
                token = resolver_captcha_turnstile(driver, site_key)
                
                if token:
                    print(f"   ✓ Captcha resuelto")
                    
                    if inyectar_token_turnstile(driver, token):
                        time.sleep(2)
                        
                        # Simular click en widget
                        try:
                            driver.execute_script("""
                                const widget = document.querySelector('[data-sitekey]');
                                if (widget) widget.click();
                            """)
                            time.sleep(1)
                        except:
                            pass
                        
                        verificar_captcha_resuelto(driver)
                else:
                    print(f"   ✗ Error obteniendo token")

            # Ingresar CUFE
            print(f"   → Ingresando CUFE...")
            time.sleep(2)
            
            campo_cufe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'DocumentKey'))
            )
            
            campo_cufe.clear()
            campo_cufe.send_keys(str(cufe))
            
            try:
                campo_cufe.send_keys(Keys.RETURN)
            except:
                try:
                    submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]')
                    submit_btn.click()
                except:
                    driver.execute_script("document.querySelector('form').submit();")
            
            # Esperar resultados
            time.sleep(4)

            # Buscar códigos
            codigo_evento, estado = obtener_codigos_evento_por_tag(driver)
            codigos_evento.append(codigo_evento)
            estados_factura.append(estado)

            print(f"   ✓ Código: {codigo_evento} | Estado: {estado}\n")
            
        except Exception as e:
            print(f"   ✗ ERROR: {e}\n")
            codigos_evento.append("Error")
            estados_factura.append(f"Error: {str(e)[:50]}")
            errores_count += 1

    driver.quit()
    
    # Guardar resultados
    df['Código Evento'] = codigos_evento
    df['Estado de factura'] = estados_factura
    
    try:
        df.to_excel(ARCHIVO_SALIDA, index=False)
        print(f"{'='*60}")
        print(f"✓ Proceso completado exitosamente")
        print(f"✓ Archivo guardado: {ARCHIVO_SALIDA}")
        print(f"✓ Total procesados: {len(df)}")
        if errores_count > 0:
            print(f"⚠️  Errores encontrados: {errores_count}")
        print(f"{'='*60}")
    except Exception as e:
        print(f"✗ Error guardando archivo: {e}")

if __name__ == "__main__":
    procesar_facturas()