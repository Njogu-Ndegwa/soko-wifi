import paramiko
from routeros_api import connect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import socket
from sshtunnel import SSHTunnelForwarder

class MikrotikConnection:
    def __init__(self):
        self.connection = None
        self.tunnel = None
        
    def create_ssh_tunnel(self):
        """Create SSH tunnel to MikroTik device"""
        try:
            self.tunnel = SSHTunnelForwarder(
                ssh_address_or_host=('105.163.2.223', 22),  # Replace with your MikroTik's public IP
                ssh_username='api-user',  # SSH username
                ssh_password='12345678',  # SSH password (or use ssh_pkey for key-based auth)
                remote_bind_address=('127.0.0.1', 8728),  # MikroTik API port
                local_bind_address=('127.0.0.1', 8729)    # Local port to forward to
            )
            self.tunnel.start()
            return True
        except Exception as e:
            print(f"Tunnel creation error: {str(e)}")
            return False
        
    def connect(self):
        """Connect to MikroTik through SSH tunnel"""
        try:
            # First create the SSH tunnel
            if not self.create_ssh_tunnel():
                raise Exception("Failed to create SSH tunnel")
                
            # Connect through the tunnel
            self.connection = connect(
                username='admin',  # MikroTik API username
                password='12345678',  # MikroTik API password
                host='127.0.0.1',  # Connect to local tunnel endpoint
                port=self.tunnel.local_bind_port  # Use tunnel port
            )
            return True
        except Exception as e:
            if self.tunnel:
                self.tunnel.close()
            print(f"Connection error: {str(e)}")
            return False
            
    def get_connection(self):
        if not self.connection:
            self.connect()
        return self.connection
        
    def cleanup(self):
        """Clean up connections"""
        if self.connection:
            self.connection.close()
        if self.tunnel:
            self.tunnel.close()

class MikrotikViewSet(APIView):
    def __init__(self):
        self.mikrotik = MikrotikConnection()
        
    def get(self, request):
        """Get system information from MikroTik"""
        connection = self.mikrotik.get_connection()
        print(connection, "------Connection------")
        if not connection:
            return Response(
                {"error": "Could not establish secure connection to MikroTik device"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
        try:
            api = connection.get_api()
            resources = api.get_resource('/system/resource')
            result = resources.get()
            
            return Response({
                "system_info": result[0],
            })
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        finally:
            self.mikrotik.cleanup()
            
    def post(self, request):
        """Execute commands on MikroTik"""
        connection = self.mikrotik.get_connection()
        if not connection:
            return Response(
                {"error": "Could not establish secure connection to MikroTik device"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
        command = request.data.get('command')
        if not command:
            return Response(
                {"error": "Command is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            api = connection.get_api()
            resource = api.get_resource(command)
            result = resource.get()
            
            return Response({
                "result": result
            })
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        finally:
            self.mikrotik.cleanup()