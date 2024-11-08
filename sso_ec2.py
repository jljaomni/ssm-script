import boto3
import subprocess
import argparse
import readchar
from rich.console import Console
from rich.table import Table
import os
import configparser

def check_credentials(profile):
    """
    Verifica si las credenciales de AWS para el perfil están activas. 
    Si están vencidas o no son válidas, ejecuta auth.py para renovarlas.
    """
    try:
        session = boto3.Session(profile_name=profile)
        sts_client = session.client('sts')
        sts_client.get_caller_identity()  # Intento de operación simple
        print(f"Las credenciales para el perfil '{profile}' están activas.")
    except Exception as e:
        print(f"Las credenciales para el perfil '{profile}' han expirado o no son válidas. Renovando...")       
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sso_auth_path = os.path.join(current_dir, 'aws_auth.py')
        subprocess.run(['python3', sso_auth_path])
        print(f"Credenciales para el perfil '{profile}' renovadas.")


def get_instance_name(tags):
    for tag in tags:
        if tag['Key'] == 'Name':
            return tag['Value']
    return 'No name'


def list_instances(profile):
    session = boto3.Session(profile_name=profile)
    ec2_client = session.client('ec2')
    response = ec2_client.describe_instances()

    print("Showing instances...")

    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            instance_type = instance['InstanceType']  # Added instance type
            state = instance['State']['Name']
            tags = instance.get('Tags', [])
            name = get_instance_name(tags)
            public_ip = instance.get('PublicIpAddress', 'No public IP')
            instances.append({
                'InstanceId': instance_id,
                'Name': name,
                'InstanceType': instance_type,  # Store instance type
                'State': state,
                'PublicIp': public_ip
            })
    return instances


def create_table(instances, selected):
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Instance ID", style="dim", width=22)
    table.add_column("Name", width=30)
    table.add_column("Instance Type", width=15)  # Added instance type column
    table.add_column("Status", width=10)
    table.add_column("Public IP", width=15)
    print("Navigate and connect to an EC2 instance using AWS SSM.")

    for idx, instance in enumerate(instances):
        status_color = "green" if instance['State'] == "running" else "red"
        if idx == selected:
            table.add_row(
                instance['InstanceId'], 
                instance['Name'], 
                instance['InstanceType'], 
                f"[{status_color}]{instance['State']}[/{status_color}]",
                instance['PublicIp'],
                style="on purple"  # background for the selected row
            )
        else:
            table.add_row(
                instance['InstanceId'], 
                instance['Name'], 
                instance['InstanceType'], 
                f"[{status_color}]{instance['State']}[/{status_color}]", 
                instance['PublicIp']
            )
    return table

# connect to the selected instance using SSM
def connect_instance(instance, profile):
    instance_id = instance['InstanceId']
    print(f"Connecting to instance {instance['Name']} ({instance_id})...")

    subprocess.run([
        'aws', 'ssm', 'start-session',
        '--target', instance_id,
        '--profile', profile
    ])


def main(profile):
    console = Console()

    check_credentials(profile)

    instances = list_instances(profile)

    selected = 0  
    total_instances = len(instances)

    def show_table():
        os.system('clear')  
        table = create_table(instances, selected)
        console.print(table)

    show_table()

    while True:
        key = readchar.readkey()
        
        if key == readchar.key.UP:
            selected = (selected - 1) % total_instances
            show_table()
        elif key == readchar.key.DOWN:
            selected = (selected + 1) % total_instances
            show_table()
        elif key == readchar.key.ENTER:
            break
        elif key == readchar.key.ESC:
            print("Exiting...")
            return

    # Connect to the selected instance
    selected_instance = instances[selected]
    connect_instance(selected_instance, profile)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Navigate and connect to an EC2 instance using AWS SSM.")
    parser.add_argument('--profile', type=str, required=True, help="The AWS profile to use.")
    args = parser.parse_args()

    # Run the main function
    main(args.profile)