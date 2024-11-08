import boto3
import configparser
import os
import json
import subprocess
from botocore.exceptions import ClientError, ProfileNotFound
from datetime import datetime, timezone

current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, 'test.json')


aws_credentials_path = os.path.expanduser("~/.aws/credentials")

def get_sso_session_for_profile(profile):
    config_path = os.path.expanduser("~/.aws/config")
    config = configparser.ConfigParser()
    config.read(config_path)

    profile_key = f"profile {profile}"
    return config[profile_key].get("sso_session") if profile_key in config else None

def check_and_renew_sso_session(profile):
    """
    Verifica si la sesión SSO está activa para el perfil, y si no, la renueva.
    """
    sso_session = get_sso_session_for_profile(profile)
    if not sso_session:
        print(f"No se encontró un sso-session para el perfil '{profile}'.")
        return False

    try:
        session = boto3.Session(profile_name=profile)
        sts_client = session.client('sts')
        sts_client.get_caller_identity()
        print(f"Sesión SSO '{sso_session}' activa.")
        return True
    except Exception as e:
        print(f"La sesión SSO '{sso_session}' ha expirado o no es válida. Renovando...")
        subprocess.run(['aws', 'sso', 'login', '--sso-session', sso_session])
        print(f"Sesión SSO '{sso_session}' renovada.")
        return True

def is_valid_credentials(profile_name):
    """
    Verifica si las credenciales de un perfil específico son válidas mediante una llamada a STS.
    """
    try:
        session = boto3.Session(profile_name=profile_name)
        session.client('sts').get_caller_identity()
        return True
    except ClientError:
        print(f"Las credenciales para el perfil '{profile_name}' han expirado o son inválidas.")
        return False

def update_credentials(profile_name, role_arn, session_name, region):
    """
    Asume el rol y actualiza las credenciales del perfil en el archivo de credenciales de AWS.
    """
    try:
        base_session = boto3.Session(profile_name=base_profile)
        sts_client = base_session.client("sts")
        assumed_role = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name
        )


        credentials = assumed_role["Credentials"]


        config.set(profile_name, "aws_access_key_id", credentials["AccessKeyId"])
        config.set(profile_name, "aws_secret_access_key", credentials["SecretAccessKey"])
        config.set(profile_name, "aws_session_token", credentials["SessionToken"])
        config.set(profile_name, "region", region)
        config.set(profile_name, "expiration", credentials["Expiration"].isoformat())

        print(f"Perfil '{profile_name}' actualizado exitosamente.")
        return True
    except ClientError as e:
        print(f"Error al asumir el rol para '{profile_name}': {e}")
        return False

# Cargar la configuración de las cuentas desde el archivo JSON
with open(json_path, "r") as file:
    accounts = json.load(file)


base_profile = "devops"


if not check_and_renew_sso_session(base_profile):
    print(f"No se pudo autenticar el perfil base '{base_profile}'. Abortando...")
    exit(1)


config = configparser.ConfigParser()
config.read(aws_credentials_path)


for account in accounts:
    profile_name = account["profile"]
    account_id = account["account"]
    region = account["region"]
    role_name = account["role"]
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"


    if not is_valid_credentials(profile_name):
        if update_credentials(profile_name, role_arn, profile_name, region):
            print(f"Credenciales actualizadas para el perfil '{profile_name}'.")
        else:
            print(f"No se pudieron actualizar las credenciales para el perfil '{profile_name}'.")
    else:
        print(f"Las credenciales para el perfil '{profile_name}' son válidas; no se requiere actualización.")


with open(aws_credentials_path, "w") as configfile:
    config.write(configfile)