import os

ada_path = r"c:\Users\HinojosaDev\Downloads\ADA\Sft1\PQRS-1\autenticacion\autenticacion.py"
p_path = r"c:\Users\HinojosaDev\Downloads\ADA\Sft1\P\PQRS-1\autenticacion\autenticacion.py"

with open(p_path, "r", encoding="utf-8") as f:
    p_content = f.read()

start_str = "def index() -> rx.Component:"
end_str = "def brand_footer() -> rx.Component:\n"
start_idx = p_content.find(start_str)

brand_footer_idx = p_content.find(end_str)
next_def_idx = p_content.find("\ndef ", brand_footer_idx + len(end_str))
if next_def_idx == -1:
    p_block = p_content[start_idx:]
else:
    p_block = p_content[start_idx:next_def_idx]

with open(ada_path, "r", encoding="utf-8") as f:
    ada_content = f.read()

ada_start_idx = ada_content.find(start_str)
ada_brand_footer_idx = ada_content.find(end_str)
ada_next_def_idx = ada_content.find("\ndef ", ada_brand_footer_idx + len(end_str))

if ada_next_def_idx == -1:
    new_ada = ada_content[:ada_start_idx] + p_block
else:
    new_ada = ada_content[:ada_start_idx] + p_block + ada_content[ada_next_def_idx:]

login_str = "def login_page() -> rx.Component:\n    return rx.box(\n"
home_icon_code = """        # Icono desplegable de casa agregado
        rx.box(
            rx.menu.root(
                rx.menu.trigger(
                    rx.icon_button(rx.icon("home", size=24), size="3", variant="soft", color_scheme="blue", radius="full", cursor="pointer")
                ),
                rx.menu.content(
                    rx.menu.item(
                        "Ir al Inicio",
                        on_click=rx.redirect("/"),
                    ),
                    rx.menu.item(
                        "Ir a Registro",
                        on_click=rx.redirect("/registro"),
                    ),
                )
            ),
            position="absolute", top="24px", left="24px", z_index="50"
        ),
"""
new_ada = new_ada.replace(login_str, login_str + home_icon_code)

with open(ada_path, "w", encoding="utf-8") as f:
    f.write(new_ada)

print("Replacement done!")
