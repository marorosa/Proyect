import reflex, inspect
print('reflex file:', reflex.__file__)
print('App attrs:', [a for a in dir(reflex.App) if 'route' in a or 'url' in a or 'static' in a])
print('reflex attrs:', [a for a in dir(reflex) if 'route' in a or 'static' in a])
