"""
Broker Adapters (T1)
====================

Concrete broker adapter implementations.

Supported:
- Mock (testing)
- Binance (Spot + Futures)
- Bybit (Spot + Linear)
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import asyncio
import random
import time
import hashlib
import hmac

from ..trading_types import (
    Exchange,
    MarketMode,
    ConnectionStatus,
    ConnectionHealth,
    ExchangeConnection,
    AccountState,
    AssetBalance,
    PositionSummary,
    PositionSide,
    ConnectionHealthRecord,
    ConnectionValidationResult
)
from .broker_base import BrokerAdapter


# ===========================================
# Mock Adapter (for testing)
# ===========================================

class MockBrokerAdapter(BrokerAdapter):
    """
    Mock broker adapter for testing.
    
    Simulates exchange responses without real API calls.
    """
    
    def __init__(
        self,
        connection: ExchangeConnection,
        api_key: str,
        api_secret: str,
        passphrase: str = None,
        initial_balance: float = 100000.0
    ):
        super().__init__(connection, api_key, api_secret, passphrase)
        
        # Simulated state
        self._initial_balance = initial_balance
        self._balances: Dict[str, AssetBalance] = {
            "USDT": AssetBalance(asset="USDT", free=initial_balance, locked=0.0, usd_value=initial_balance),
            "BTC": AssetBalance(asset="BTC", free=0.0, locked=0.0, usd_value=0.0)
        }
        self._positions: List[PositionSummary] = []
        self._open_orders = 0
    
    @property
    def exchange(self) -> Exchange:
        return Exchange.BINANCE  # Mock pretends to be Binance
    
    @property
    def supported_modes(self) -> List[MarketMode]:
        return [MarketMode.SPOT, MarketMode.FUTURES]
    
    async def validate_connection(self) -> ConnectionValidationResult:
        """Simulate validation"""
        self._increment_request()
        await asyncio.sleep(0.1)
        
        return ConnectionValidationResult(
            valid=True,
            exchange=self.exchange.value,
            can_read=True,
            can_trade=True,
            can_withdraw=False,
            supported_modes=self.supported_modes,
            warnings=["This is a mock adapter for testing"],
            errors=[]
        )
    
    async def connect(self) -> bool:
        """Simulate connection"""
        self._increment_request()
        await asyncio.sleep(0.1)
        
        self._connected = True
        self.connection.status = ConnectionStatus.CONNECTED
        self.connection.health = ConnectionHealth.HEALTHY
        
        return True
    
    async def disconnect(self) -> bool:
        """Simulate disconnection"""
        self._connected = False
        self.connection.status = ConnectionStatus.DISCONNECTED
        return True
    
    async def fetch_account_state(self) -> AccountState:
        """Get simulated account state"""
        self._increment_request()
        
        balances = await self.fetch_balances()
        positions = await self.fetch_positions()
        
        equity = sum(b.usd_value for b in balances)
        
        return AccountState(
            connection_id=self.connection.connection_id,
            exchange=self.exchange.value,
            mode=self.connection.selected_mode,
            equity_usd=equity,
            balances=balances,
            open_positions=len(positions),
            open_orders=self._open_orders,
            can_read=True,
            can_trade=True,
            can_withdraw=False
        )
    
    async def fetch_balances(self) -> List[AssetBalance]:
        """Get simulated balances"""
        self._increment_request()
        return [b for b in self._balances.values() if b.total > 0]
    
    async def fetch_positions(self) -> List[PositionSummary]:
        """Get simulated positions"""
        self._increment_request()
        return self._positions.copy()
    
    async def fetch_open_orders_count(self) -> int:
        """Get simulated open orders count"""
        self._increment_request()
        return self._open_orders
    
    async def health_check(self) -> ConnectionHealthRecord:
        """Perform simulated health check"""
        self._increment_request()
        
        start = time.time()
        await asyncio.sleep(0.05)  # Simulate latency
        ping_ms = (time.time() - start) * 1000
        
        return ConnectionHealthRecord(
            connection_id=self.connection.connection_id,
            ping_ms=ping_ms,
            account_fetch_ok=True,
            balance_fetch_ok=True,
            positions_fetch_ok=True,
            health=ConnectionHealth.HEALTHY,
            reason=None
        )
    
    # Mock-specific methods
    def set_balance(self, asset: str, free: float, locked: float = 0.0):
        """Set mock balance"""
        usd_value = free + locked if asset == "USDT" else 0.0
        self._balances[asset] = AssetBalance(
            asset=asset, free=free, locked=locked, usd_value=usd_value
        )
    
    def add_position(self, position: PositionSummary):
        """Add mock position"""
        self._positions.append(position)


# ===========================================
# Binance Adapter
# ===========================================

class BinanceBrokerAdapter(BrokerAdapter):
    """
    Binance broker adapter.
    
    Supports Spot and USDT-M Futures.
    """
    
    SPOT_BASE = "https://api.binance.com"
    SPOT_TESTNET = "https://testnet.binance.vision"
    FUTURES_BASE = "https://fapi.binance.com"
    FUTURES_TESTNET = "https://testnet.binancefuture.com"
    
    def __init__(
        self,
        connection: ExchangeConnection,
        api_key: str,
        api_secret: str,
        passphrase: str = None,
        use_futures: bool = False,
        testnet: bool = True
    ):
        super().__init__(connection, api_key, api_secret, passphrase)
        self.use_futures = use_futures
        self.testnet = testnet
        
        # Set base URL
        if use_futures:
            self._base_url = self.FUTURES_TESTNET if testnet else self.FUTURES_BASE
        else:
            self._base_url = self.SPOT_TESTNET if testnet else self.SPOT_BASE
        
        self._client = None
    
    @property
    def exchange(self) -> Exchange:
        return Exchange.BINANCE
    
    @property
    def supported_modes(self) -> List[MarketMode]:
        return [MarketMode.SPOT, MarketMode.FUTURES]
    
    def _sign(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature"""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self._api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _request(self, method: str, endpoint: str, params: dict = None, signed: bool = False):
        """Make API request"""
        import httpx
        
        self._increment_request()
        
        if not self._client:
            self._client = httpx.AsyncClient(timeout=30.0)
        
        params = params or {}
        
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)
        
        headers = {"X-MBX-APIKEY": self._api_key}
        url = f"{self._base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = await self._client.get(url, params=params, headers=headers)
            else:
                response = await self._client.post(url, params=params, headers=headers)
            
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def validate_connection(self) -> ConnectionValidationResult:
        """Validate Binance connection"""
        errors = []
        warnings = []
        
        try:
            # Test account endpoint
            if self.use_futures:
                data = await self._request("GET", "/fapi/v2/balance", signed=True)
            else:
                data = await self._request("GET", "/api/v3/account", signed=True)
            
            if "error" in data or "code" in data:
                errors.append(data.get("msg", data.get("error", "Unknown error")))
                return ConnectionValidationResult(
                    valid=False,
                    exchange=self.exchange.value,
                    errors=errors
                )
            
            # Check permissions
            can_trade = data.get("canTrade", False) if not self.use_futures else True
            
            if self.testnet:
                warnings.append("Using testnet - not for real trading")
            
            return ConnectionValidationResult(
                valid=True,
                exchange=self.exchange.value,
                can_read=True,
                can_trade=can_trade,
                can_withdraw=False,
                supported_modes=self.supported_modes,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            return ConnectionValidationResult(
                valid=False,
                exchange=self.exchange.value,
                errors=[str(e)]
            )
    
    async def connect(self) -> bool:
        """Connect to Binance"""
        import httpx
        
        try:
            self._client = httpx.AsyncClient(timeout=30.0)
            
            # Test time endpoint
            endpoint = "/fapi/v1/time" if self.use_futures else "/api/v3/time"
            response = await self._client.get(f"{self._base_url}{endpoint}")
            
            if response.status_code == 200:
                self._connected = True
                self.connection.status = ConnectionStatus.CONNECTED
                return True
            
            self.connection.status = ConnectionStatus.ERROR
            return False
            
        except Exception:
            self.connection.status = ConnectionStatus.ERROR
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from Binance"""
        if self._client:
            await self._client.aclose()
            self._client = None
        
        self._connected = False
        self.connection.status = ConnectionStatus.DISCONNECTED
        return True
    
    async def fetch_account_state(self) -> AccountState:
        """Fetch Binance account state"""
        balances = await self.fetch_balances()
        positions = await self.fetch_positions()
        orders_count = await self.fetch_open_orders_count()
        
        equity = sum(b.usd_value for b in balances if b.asset == "USDT")
        
        return AccountState(
            connection_id=self.connection.connection_id,
            exchange=self.exchange.value,
            mode=self.connection.selected_mode,
            equity_usd=equity,
            balances=balances,
            open_positions=len(positions),
            open_orders=orders_count,
            can_read=True,
            can_trade=True,
            can_withdraw=False
        )
    
    async def fetch_balances(self) -> List[AssetBalance]:
        """Fetch Binance balances"""
        if self.use_futures:
            data = await self._request("GET", "/fapi/v2/balance", signed=True)
        else:
            data = await self._request("GET", "/api/v3/account", signed=True)
        
        balances = []
        
        if isinstance(data, list):  # Futures format
            for item in data:
                total = float(item.get("balance", 0))
                free = float(item.get("availableBalance", 0))
                if total > 0:
                    balances.append(AssetBalance(
                        asset=item["asset"],
                        free=free,
                        locked=total - free,
                        total=total,
                        usd_value=total if item["asset"] == "USDT" else 0.0
                    ))
        elif "balances" in data:  # Spot format
            for item in data["balances"]:
                free = float(item["free"])
                locked = float(item["locked"])
                if free + locked > 0:
                    balances.append(AssetBalance(
                        asset=item["asset"],
                        free=free,
                        locked=locked,
                        usd_value=(free + locked) if item["asset"] == "USDT" else 0.0
                    ))
        
        return balances
    
    async def fetch_positions(self) -> List[PositionSummary]:
        """Fetch Binance positions"""
        if not self.use_futures:
            return []  # Spot doesn't have positions in this sense
        
        data = await self._request("GET", "/fapi/v2/positionRisk", signed=True)
        
        positions = []
        if isinstance(data, list):
            for item in data:
                size = float(item.get("positionAmt", 0))
                if size != 0:
                    positions.append(PositionSummary(
                        connection_id=self.connection.connection_id,
                        asset=item["symbol"].replace("USDT", ""),
                        mode=MarketMode.FUTURES,
                        side=PositionSide.LONG if size > 0 else PositionSide.SHORT,
                        quantity=abs(size),
                        avg_entry=float(item.get("entryPrice", 0)),
                        mark_price=float(item.get("markPrice", 0)),
                        unrealized_pnl=float(item.get("unRealizedProfit", 0)),
                        leverage=float(item.get("leverage", 1))
                    ))
        
        return positions
    
    async def fetch_open_orders_count(self) -> int:
        """Fetch open orders count"""
        endpoint = "/fapi/v1/openOrders" if self.use_futures else "/api/v3/openOrders"
        data = await self._request("GET", endpoint, signed=True)
        
        if isinstance(data, list):
            return len(data)
        return 0
    
    async def health_check(self) -> ConnectionHealthRecord:
        """Health check for Binance"""
        start = time.time()
        
        try:
            endpoint = "/fapi/v1/time" if self.use_futures else "/api/v3/time"
            response = await self._client.get(f"{self._base_url}{endpoint}") if self._client else None
            
            ping_ms = (time.time() - start) * 1000
            
            # Check account
            account_ok = False
            balance_ok = False
            
            try:
                await self.fetch_account_state()
                account_ok = True
                balance_ok = True
            except Exception:
                pass
            
            health = ConnectionHealth.HEALTHY
            reason = None
            
            if not account_ok:
                health = ConnectionHealth.DEGRADED
                reason = "Account fetch failed"
            
            if ping_ms > 1000:
                health = ConnectionHealth.DEGRADED
                reason = f"High latency: {ping_ms:.0f}ms"
            
            return ConnectionHealthRecord(
                connection_id=self.connection.connection_id,
                ping_ms=ping_ms,
                account_fetch_ok=account_ok,
                balance_fetch_ok=balance_ok,
                positions_fetch_ok=True,
                health=health,
                reason=reason
            )
            
        except Exception as e:
            return ConnectionHealthRecord(
                connection_id=self.connection.connection_id,
                health=ConnectionHealth.UNHEALTHY,
                reason=str(e)
            )


# ===========================================
# Bybit Adapter
# ===========================================

class BybitBrokerAdapter(BrokerAdapter):
    """
    Bybit broker adapter.
    
    Supports Spot and Linear perpetuals.
    """
    
    BASE_URL = "https://api.bybit.com"
    TESTNET_URL = "https://api-testnet.bybit.com"
    
    def __init__(
        self,
        connection: ExchangeConnection,
        api_key: str,
        api_secret: str,
        passphrase: str = None,
        category: str = "linear",
        testnet: bool = True
    ):
        super().__init__(connection, api_key, api_secret, passphrase)
        self.category = category
        self.testnet = testnet
        self._base_url = self.TESTNET_URL if testnet else self.BASE_URL
        self._client = None
        self._recv_window = 5000
    
    @property
    def exchange(self) -> Exchange:
        return Exchange.BYBIT
    
    @property
    def supported_modes(self) -> List[MarketMode]:
        return [MarketMode.SPOT, MarketMode.FUTURES]
    
    def _sign(self, timestamp: int, params: Dict[str, Any]) -> str:
        """Generate Bybit V5 signature"""
        param_str = str(timestamp) + self._api_key + str(self._recv_window)
        if params:
            sorted_params = sorted(params.items())
            param_str += "&".join([f"{k}={v}" for k, v in sorted_params])
        
        return hmac.new(
            self._api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _request(self, method: str, endpoint: str, params: dict = None, signed: bool = False):
        """Make Bybit API request"""
        import httpx
        
        self._increment_request()
        
        if not self._client:
            self._client = httpx.AsyncClient(timeout=30.0)
        
        params = params or {}
        timestamp = int(time.time() * 1000)
        
        headers = {"Content-Type": "application/json"}
        
        if signed:
            signature = self._sign(timestamp, params)
            headers.update({
                "X-BAPI-API-KEY": self._api_key,
                "X-BAPI-SIGN": signature,
                "X-BAPI-TIMESTAMP": str(timestamp),
                "X-BAPI-RECV-WINDOW": str(self._recv_window)
            })
        
        url = f"{self._base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = await self._client.get(url, params=params, headers=headers)
            else:
                response = await self._client.post(url, json=params, headers=headers)
            
            data = response.json()
            return data.get("result", data)
            
        except Exception as e:
            return {"error": str(e)}
    
    async def validate_connection(self) -> ConnectionValidationResult:
        """Validate Bybit connection"""
        try:
            account_type = "UNIFIED" if self.category != "spot" else "SPOT"
            data = await self._request(
                "GET", "/v5/account/wallet-balance",
                params={"accountType": account_type},
                signed=True
            )
            
            if "error" in data:
                return ConnectionValidationResult(
                    valid=False,
                    exchange=self.exchange.value,
                    errors=[data.get("error", "Unknown error")]
                )
            
            warnings = []
            if self.testnet:
                warnings.append("Using testnet - not for real trading")
            
            return ConnectionValidationResult(
                valid=True,
                exchange=self.exchange.value,
                can_read=True,
                can_trade=True,
                can_withdraw=False,
                supported_modes=self.supported_modes,
                warnings=warnings,
                errors=[]
            )
            
        except Exception as e:
            return ConnectionValidationResult(
                valid=False,
                exchange=self.exchange.value,
                errors=[str(e)]
            )
    
    async def connect(self) -> bool:
        """Connect to Bybit"""
        import httpx
        
        try:
            self._client = httpx.AsyncClient(timeout=30.0)
            response = await self._client.get(f"{self._base_url}/v5/market/time")
            
            if response.status_code == 200:
                self._connected = True
                self.connection.status = ConnectionStatus.CONNECTED
                return True
            
            self.connection.status = ConnectionStatus.ERROR
            return False
            
        except Exception:
            self.connection.status = ConnectionStatus.ERROR
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from Bybit"""
        if self._client:
            await self._client.aclose()
            self._client = None
        
        self._connected = False
        self.connection.status = ConnectionStatus.DISCONNECTED
        return True
    
    async def fetch_account_state(self) -> AccountState:
        """Fetch Bybit account state"""
        balances = await self.fetch_balances()
        positions = await self.fetch_positions()
        orders_count = await self.fetch_open_orders_count()
        
        equity = sum(b.usd_value for b in balances)
        
        return AccountState(
            connection_id=self.connection.connection_id,
            exchange=self.exchange.value,
            mode=self.connection.selected_mode,
            equity_usd=equity,
            balances=balances,
            open_positions=len(positions),
            open_orders=orders_count,
            can_read=True,
            can_trade=True,
            can_withdraw=False
        )
    
    async def fetch_balances(self) -> List[AssetBalance]:
        """Fetch Bybit balances"""
        account_type = "UNIFIED" if self.category != "spot" else "SPOT"
        data = await self._request(
            "GET", "/v5/account/wallet-balance",
            params={"accountType": account_type},
            signed=True
        )
        
        balances = []
        
        for account in data.get("list", []):
            for coin in account.get("coin", []):
                total = float(coin.get("walletBalance", 0))
                free = float(coin.get("availableToWithdraw", 0))
                
                if total > 0:
                    balances.append(AssetBalance(
                        asset=coin["coin"],
                        free=free,
                        locked=max(0, total - free),
                        total=total,
                        usd_value=float(coin.get("usdValue", 0))
                    ))
        
        return balances
    
    async def fetch_positions(self) -> List[PositionSummary]:
        """Fetch Bybit positions"""
        data = await self._request(
            "GET", "/v5/position/list",
            params={"category": self.category},
            signed=True
        )
        
        positions = []
        
        for item in data.get("list", []):
            size = float(item.get("size", 0))
            if size != 0:
                positions.append(PositionSummary(
                    connection_id=self.connection.connection_id,
                    asset=item["symbol"].replace("USDT", ""),
                    mode=MarketMode.FUTURES if self.category != "spot" else MarketMode.SPOT,
                    side=PositionSide.LONG if item.get("side", "").upper() == "BUY" else PositionSide.SHORT,
                    quantity=size,
                    avg_entry=float(item.get("avgPrice", 0)),
                    mark_price=float(item.get("markPrice", 0)),
                    unrealized_pnl=float(item.get("unrealisedPnl", 0)),
                    realized_pnl=float(item.get("cumRealisedPnl", 0)),
                    leverage=float(item.get("leverage", 1))
                ))
        
        return positions
    
    async def fetch_open_orders_count(self) -> int:
        """Fetch open orders count"""
        data = await self._request(
            "GET", "/v5/order/realtime",
            params={"category": self.category},
            signed=True
        )
        
        return len(data.get("list", []))
    
    async def health_check(self) -> ConnectionHealthRecord:
        """Health check for Bybit"""
        start = time.time()
        
        try:
            response = await self._client.get(f"{self._base_url}/v5/market/time") if self._client else None
            ping_ms = (time.time() - start) * 1000
            
            account_ok = False
            balance_ok = False
            
            try:
                await self.fetch_account_state()
                account_ok = True
                balance_ok = True
            except Exception:
                pass
            
            health = ConnectionHealth.HEALTHY
            reason = None
            
            if not account_ok:
                health = ConnectionHealth.DEGRADED
                reason = "Account fetch failed"
            
            if ping_ms > 1000:
                health = ConnectionHealth.DEGRADED
                reason = f"High latency: {ping_ms:.0f}ms"
            
            return ConnectionHealthRecord(
                connection_id=self.connection.connection_id,
                ping_ms=ping_ms,
                account_fetch_ok=account_ok,
                balance_fetch_ok=balance_ok,
                positions_fetch_ok=True,
                health=health,
                reason=reason
            )
            
        except Exception as e:
            return ConnectionHealthRecord(
                connection_id=self.connection.connection_id,
                health=ConnectionHealth.UNHEALTHY,
                reason=str(e)
            )
