import reflex as rx
print('color_mode attr available:', hasattr(rx, 'color_mode'))
print('color_mode type:', type(getattr(rx, 'color_mode', None)))
print('has use_color_mode:', hasattr(rx, 'use_color_mode'))
print('dir color_mode sample:', dir(rx.color_mode)[:40])
