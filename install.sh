#!/bin/bash

# Variables de configuración
REPO_URL="https://github.com/jljaomni/ssm-script"
DEST_DIR="$HOME/.sso"
AWS_CONFIG_DIR="$HOME/.aws"
AWS_CONFIG_FILE="$AWS_CONFIG_DIR/config"
CONFIG_JSON_FILE="sso_config.json"  # Asegúrate de que el archivo JSON de configuración tenga este nombre
BASHRC_FILE="$HOME/.bashrc"

# Actualizar el sistema e instalar jq si no está presente
echo "Actualizando la lista de paquetes e instalando jq..."
sudo apt-get update -y
sudo apt-get install -y jq

# Crear directorios necesarios
mkdir -p "$DEST_DIR"
mkdir -p "$AWS_CONFIG_DIR"

# Descargar y copiar los archivos del repositorio al directorio destino
echo "Descargando archivos del repositorio..."
curl -L "$REPO_URL/archive/main.zip" -o /tmp/repo.zip
unzip -q /tmp/repo.zip -d /tmp/

# Especificar el nombre exacto del directorio extraído
EXTRACTED_DIR="/tmp/ssm-script-main"

# Verificar que el directorio extraído existe antes de copiar
if [ ! -d "$EXTRACTED_DIR" ]; then
  echo "Error: No se encontró el directorio extraído."
  exit 1
fi

# Copiar los archivos al directorio destino con el flag -f para sobrescribir sin preguntar
cp -Rf "$EXTRACTED_DIR/"* "$DEST_DIR/"
rm -rf /tmp/repo.zip "$EXTRACTED_DIR"

# Verificar que el archivo JSON existe en el destino
if [ ! -f "$DEST_DIR/$CONFIG_JSON_FILE" ]; then
  echo "Error: No se encontró el archivo de configuración $CONFIG_JSON_FILE en $DEST_DIR."
  exit 1
fi

# Instalar dependencias de Python
echo "Instalando dependencias de Python..."
python3 -m pip install --user boto3 subprocess argparse readchar rich

# Solicitar al usuario el nombre de la sesión SSO
echo -n "Ingrese el nombre de la sesión SSO: "
read -r SSO_SESSION_NAME

# Crear o actualizar el archivo de configuración de AWS con los perfiles SSO
echo "Actualizando la configuración de AWS para SSO..."

# Escribir la sesión SSO en el archivo de configuración
cat <<EOL > "$AWS_CONFIG_FILE"
[sso-session $SSO_SESSION_NAME]
sso_start_url = https://omnipro.awsapps.com/start/#
sso_region = us-east-1
sso_registration_scopes = sso:account:access
EOL

# Leer perfiles del archivo JSON y agregarlos al archivo de configuración
for row in $(jq -c '.[]' "$DEST_DIR/$CONFIG_JSON_FILE"); do
    PROFILE_NAME=$(echo $row | jq -r '.profile')
    SSO_ACCOUNT_ID=$(echo $row | jq -r '.sso_account_id')
    SSO_ROLE_NAME=$(echo $row | jq -r '.sso_role_name')
    REGION=$(echo $row | jq -r '.region')
    OUTPUT=$(echo $row | jq -r '.output')

    cat <<EOL >> "$AWS_CONFIG_FILE"

[profile $PROFILE_NAME]
sso_session = $SSO_SESSION_NAME
sso_account_id = $SSO_ACCOUNT_ID
sso_role_name = $SSO_ROLE_NAME
region = $REGION
output = $OUTPUT
EOL
done

echo "Configuración de SSO completada."

# Agregar funciones y alias al archivo .bashrc
echo "Agregando funciones y alias al archivo .bashrc..."

# Verificar si las funciones y el alias ya existen en .bashrc para evitar duplicados
if ! grep -q "alias aws_profiles=" "$BASHRC_FILE"; then
    echo "alias aws_profiles=\"aws configure list-profiles\"" >> "$BASHRC_FILE"
fi

if ! grep -q "function auth_aws()" "$BASHRC_FILE"; then
    cat <<'EOL' >> "$BASHRC_FILE"

# Función para ejecutar el script auth_aws.py
function auth_aws() {
    python3 "$HOME/.sso/aws_auth.py"
}
EOL
fi

if ! grep -q "function aws_ec2()" "$BASHRC_FILE"; then
    cat <<'EOL' >> "$BASHRC_FILE"

# Función para ejecutar el script aws_ec2.py
function aws_ec2() {
    python3 "$HOME/.sso/sso_ec2.py"
}
EOL
fi

# Recargar .bashrc para aplicar cambios
echo "Recargando .bashrc..."
source "$BASHRC_FILE"

echo "Instalación completada. Puedes usar 'auth_aws', 'aws_ec2', y 'aws_profiles' desde la terminal."