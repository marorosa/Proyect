import sys

with open('autenticacion/autenticacion.py', 'rb') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if b'Solicitud enviada con exito' in line:
        lines[i] = b'            self.solicitud_mensaje = f"\xE2\x9C\x85 Solicitud enviada con exito. Radicado: {radicado_generado}"\r\n'
        # Add the clear script calls right after
        lines.insert(i+3, b'            yield rx.clear_selected_files("upload_solicitud")\r\n')
        lines.insert(i+4, b'            yield rx.call_script("if(window.__pqrsClear) window.__pqrsClear();")\r\n')
        break

for i, line in enumerate(lines):
    if b'Error guardando solicitud' in line:
        lines.insert(i+1, b'            yield rx.clear_selected_files("upload_solicitud")\r\n')
        lines.insert(i+2, b'            yield rx.call_script("if(window.__pqrsClear) window.__pqrsClear();")\r\n')
        break

for i, line in enumerate(lines):
    if b'color:#ef4444;font-size:14px;padding:2px 6px;" data-i="' in line:
        lines[i] = b'                    \'color:#ef4444;font-size:14px;padding:2px 6px;" data-i="\'+i+\'">\xE2\x9C\x96</button>\';\r\n'
        break

with open('autenticacion/autenticacion.py', 'wb') as f:
    f.writelines(lines)
