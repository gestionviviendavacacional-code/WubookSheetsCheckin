import asyncio
import json
import logging
from playwright.async_api import async_playwright
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WUBOOK_BASE_URL = "https://wubook.net"

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health():
    """Health check"""
    return {'status': 'ok', 'message': 'WuBook Checkin Service is running'}, 200

@app.route('/update_wubook_checkin', methods=['POST', 'OPTIONS'])
def update_wubook_checkin():
    """HTTP Cloud Run endpoint para actualizar check-in en WuBook"""
    
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        
        human_id = data.get('human_id')
        check_in_time = data.get('check_in_time')
        username = data.get('username', 'Anna')
        password = data.get('password', '123456789')
        
        if not all([human_id, check_in_time]):
            return {'success': False, 'error': 'Parámetros faltantes: human_id, check_in_time'}, 400
        
        logger.info(f"\n📋 Procesando: {human_id} - {check_in_time}")
        
        result = asyncio.run(process_checkin(human_id, check_in_time, username, password))
        
        return result, (200 if result['success'] else 400)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {'success': False, 'error': str(e)}, 500

async def process_checkin(human_id: str, check_in_time: str, username: str, password: str) -> dict:
    """Procesa el check-in en WuBook"""
    
    try:
        async with async_playwright() as p:
            logger.info("🚀 Lanzando navegador...")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # 1️⃣ LOGIN
            logger.info(f"🔐 Login: {username}")
            await page.goto(f"{WUBOOK_BASE_URL}/ysnp/login")
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_url("**/zks/**", timeout=15000)
            logger.info("   ✓ Login exitoso")
            
            # 2️⃣ NAVEGAR A RESERVA
            logger.info(f"📋 Navegando a reserva: {human_id}")
            await page.goto(f"{WUBOOK_BASE_URL}/zks/rsrvs/rsrv/{human_id}/", wait_until="networkidle")
            await asyncio.sleep(1)
            logger.info("   ✓ Página cargada")
            
            # 3️⃣ ABRIR EDITOR DE COMENTARIOS
            logger.info("✏️ Abriendo editor de comentarios")
            edit_btn = page.locator('button.js_remark_edit_btn')
            
            try:
                if await edit_btn.is_visible(timeout=3000):
                    await edit_btn.click()
                    logger.info("   ✓ Botón editar clickeado")
                else:
                    logger.info("   ⚠️  Botón editar no visible, intentando agregar nuevo...")
                    add_btn = page.locator('button:has-text("+")')
                    await add_btn.click()
                    logger.info("   ✓ Botón + clickeado")
            except:
                logger.info("   ⚠️  Error al hacer click, continuando...")
            
            # 4️⃣ ESPERAR MODAL
            logger.info("⏳ Esperando modal...")
            await page.wait_for_selector('.js_new_remark_dialog', timeout=10000)
            logger.info("   ✓ Modal abierto")
            
            # 5️⃣ RELLENAR COMENTARIO
            logger.info("✍️ Rellenando comentario")
            textarea = page.locator('textarea.js_newremark_text')
            current = await textarea.input_value()
            logger.info(f"   Contenido actual: '{current}'")
            
            # Limpiar patrones basura
            patterns_to_remove = [
                "OTA Remarks: ** THIS RESERVATION HAS BEEN PRE-PAID **",
                "BOOKING NOTE : Payment charge is EUR",
                "OTA Remarks: Customer preferred language:",
                "You have a booker that would like free parking."
            ]
            
            cleaned_text = current
            for pattern in patterns_to_remove:
                cleaned_text = cleaned_text.replace(pattern, "")
            
            cleaned_text = cleaned_text.strip()
            logger.info(f"   Contenido limpio: '{cleaned_text}'")
            
            # Preparar nuevo comentario
            new_comment = f"Checkin ➡️ {check_in_time}"
            
            if cleaned_text:
                final_comment = f"{cleaned_text}\n{new_comment}"
            else:
                final_comment = new_comment
            
            logger.info(f"   Comentario final: '{final_comment}'")
            
            # Limpiar y rellenar
            await textarea.clear()
            await textarea.fill(final_comment)
            logger.info("   ✓ Textarea rellenado")
            
            # 6️⃣ CLICK GUARDAR
            logger.info("💾 Guardando")
            save_btn = page.locator('button.ks_button_new_rsrv_remark')
            await save_btn.click()
            logger.info("   ✓ Click Guardar realizado")
            
            # 7️⃣ ESPERAR CIERRE DEL MODAL
            logger.info("⏳ Esperando cierre del modal")
            await page.wait_for_selector('.js_new_remark_dialog', state='hidden', timeout=5000)
            logger.info("   ✓ Modal cerrado")
            
            # CERRAR NAVEGADOR
            await browser.close()
            logger.info("✅ Navegador cerrado")
            
            logger.info(f"✅ CHECK-IN ACTUALIZADO: {human_id} - {check_in_time}")
            
            return {
                'success': True,
                'message': f'Check-in ➡️ {check_in_time} escrito en WuBook',
                'human_id': human_id,
                'check_in_time': check_in_time
            }
            
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'human_id': human_id,
            'check_in_time': check_in_time
        }

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
