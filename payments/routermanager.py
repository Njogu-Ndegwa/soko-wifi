import requests
from background_task import background


class RouterManager:
    """Handles communication with the TP-Link router"""
    def __init__(self, router_ip, username, password):
        self.router_ip = router_ip
        self.username = username
        self.password = password
        self.base_url = f"http://{router_ip}/cgi-bin/luci/api/"
        self.session = None

    def login(self):
        """Login to router and get session token"""
        try:
            response = requests.post(
                f"{self.base_url}login",
                json={
                    "username": self.username,
                    "password": self.password
                }
            )
            if response.ok:
                self.session = response.json().get('token')
                return True
        except Exception as e:
            print(f"Router login failed: {e}")
        return False

    def add_mac_to_whitelist(self, mac_address):
        """Add MAC address to router's whitelist"""
        if not self.session and not self.login():
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}access_control/whitelist",
                headers={"Authorization": f"Bearer {self.session}"},
                json={"mac": mac_address}
            )
            return response.ok
        except Exception as e:
            print(f"Failed to whitelist MAC: {e}")
            return False
        
    @background()
    def remove_mac_from_whitelist(self, mac_address):
        """Remove MAC address from router's whitelist"""
        if not self.session and not self.login():
            return False
        
        try:
            response = requests.delete(
                f"{self.base_url}access_control/whitelist",
                headers={"Authorization": f"Bearer {self.session}"},
                json={"mac": mac_address}
            )
            return response.ok
        except Exception as e:
            print(f"Failed to remove MAC from whitelist: {e}")
            return False