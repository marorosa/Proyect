#!/usr/bin/env python
"""Script para crear un funcionario en la base de datos"""
import os
from pathlib import Path
from datetime import datetime
import bcrypt
from sqlmodel import Session, create_engine, select
from autenticacion.usuario_model import Usuario
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar base de datos
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = BASE_DIR / "reflex.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

print(f"Conectando a base de datos: {DATABASE_URL}")

engine = create_engine(DATABASE_URL, echo=False)

# Crear tablas si no existen
from autenticacion.usuario_model import Usuario, Solicitud
from sqlmodel import SQLModel
SQLModel.metadata.create_all(engine)

def crear_funcionario(email: str, contraseña: str, nombres: str = None, apellidos: str = None):
    """Crear un funcionario en la base de datos"""
    try:
        with Session(engine) as session:
            # Verificar si el usuario ya existe
            statement = select(Usuario).where(Usuario.email == email)
            usuario_existente = session.exec(statement).first()
            
            if usuario_existente:
                print(f"❌ El usuario {email} ya existe en la base de datos")
                return False
            
            # Hash de la contraseña
            contraseña_hasheada = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Crear nuevo usuario funcionario
            nuevo_funcionario = Usuario(
                email=email,
                Contraseña=contraseña_hasheada,
                rol="funcionario",
                is_active=True,
                Fecha_de_creacion=datetime.now(),
                nombres=nombres or email.split('@')[0],
                apellidos=apellidos or "Funcionario"
            )
            
            session.add(nuevo_funcionario)
            session.commit()
            session.refresh(nuevo_funcionario)
            
            print(f"✅ Funcionario creado exitosamente!")
            print(f"   Email: {email}")
            print(f"   Rol: funcionario")
            print(f"   ID: {nuevo_funcionario.id}")
            return True
            
    except Exception as e:
        print(f"❌ Error al crear funcionario: {str(e)}")
        return False

if __name__ == "__main__":
    # Datos del funcionario
    email = "funcionario@gmail.com"
    contraseña = "Funcionario@2024"
    nombres = "Juan"
    apellidos = "Pérez"
    
    print("=" * 60)
    print("CREAR FUNCIONARIO - PQRS")
    print("=" * 60)
    print()
    
    crear_funcionario(email, contraseña, nombres, apellidos)
    
    print()
    print("=" * 60)
