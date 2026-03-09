"""
Bybit Broker Adapter
====================

Adapter for Bybit Spot and Derivatives trading.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import hashlib
import hmac
import time
import httpx

from .base_adapter import (
    BaseBrokerAdapter,
    BrokerCredentials,
    BrokerStatus,
    OrderSide,
    OrderType,
    OrderStatus,
    TimeInForce,
    Order,
    Position,
    Balance,
    Ticker,
    ConnectionError,
    AuthenticationError,
    OrderError,
    InsufficientFundsError,
    RateLimitError
)


class BybitAdapter(BaseBrokerAdapter):
    """
    Bybit broker adapter.
    
    Supports:
    - Spot trading
    - Linear perpetuals (USDT)
    - Inverse perpetuals
    """
    
    BASE_URL = "https://api.bybit.com"
    TESTNET_URL = "https://api-testnet.bybit.com"
    
    def __init__(self, credentials: BrokerCredentials, category: str = "linear"):
        """
        Initialize Bybit adapter.
        
        Args:
            credentials: API credentials
            category: Trading category - "spot", "linear", "inverse"
        """
        super().__init__(credentials)
        self.category = category
        self._client: Optional[httpx.AsyncClient] = None
        self._base_url = self.TESTNET_URL if credentials.testnet else self.BASE_URL
        self._recv_window = 5000
    
    @property
    def broker_name(self) -> str:
        return f"bybit_{self.category}"
    
    @property
    def supports_futures(self) -> bool:
        return self.category in ["linear", "inverse"]
    
    @property
    def supports_margin(self) -> bool:
        return True
    
    def _sign(self, timestamp: int, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for Bybit V5 API"""
        param_str = str(timestamp) + self.credentials.api_key + str(self._recv_window)
        
        if params:
            # Sort params and create query string
            sorted_params = sorted(params.items())
            param_str += "&".join([f"{k}={v}" for k, v in sorted_params])
        
        signature = hmac.new(
            self.credentials.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _get_headers(self, timestamp: int, signature: str) -> Dict[str, str]:
        """Get request headers with authentication"""
        return {
            "X-BAPI-API-KEY": self.credentials.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": str(timestamp),
            "X-BAPI-RECV-WINDOW": str(self._recv_window),
            "Content-Type": "application/json"
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """Make API request"""
        self._increment_request_count()
        
        if not self._client:
            raise ConnectionError("Not connected. Call connect() first.")
        
        params = params or {}
        url = f"{self._base_url}{endpoint}"
        
        timestamp = int(time.time() * 1000)
        
        if signed:
            signature = self._sign(timestamp, params)
            headers = self._get_headers(timestamp, signature)
        else:
            headers = {"Content-Type": "application/json"}
        
        try:
            if method == "GET":
                response = await self._client.get(url, params=params, headers=headers)
            elif method == "POST":
                response = await self._client.post(url, json=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            data = response.json()
            
            # Check for Bybit API errors
            ret_code = data.get("retCode", 0)
            
            if ret_code != 0:
                ret_msg = data.get("retMsg", "Unknown error")
                
                if ret_code == 10001:  # Rate limit
                    raise RateLimitError(ret_msg, str(ret_code))
                elif ret_code in [10003, 10004, 10005]:  # Auth errors
                    raise AuthenticationError(ret_msg, str(ret_code))
                elif ret_code == 110007:  # Insufficient balance
                    raise InsufficientFundsError(ret_msg, str(ret_code))
                elif ret_code in [110001, 110003]:  # Order errors
                    raise OrderError(ret_msg, str(ret_code))
                else:
                    raise OrderError(ret_msg, str(ret_code))
            
            return data.get("result", data)
            
        except httpx.RequestError as e:
            self.last_error = str(e)
            raise ConnectionError(f"Request failed: {e}")
    
    # ===========================================
    # Connection
    # ===========================================
    
    async def connect(self) -> bool:
        """Connect to Bybit API"""
        self.status = BrokerStatus.CONNECTING
        
        try:
            self._client = httpx.AsyncClient(timeout=30.0)
            
            # Test connection
            response = await self._client.get(f"{self._base_url}/v5/market/time")
            data = response.json()
            
            if data.get("retCode") != 0:
                raise ConnectionError("Failed to connect to Bybit API")
            
            # Verify API key
            await self.get_balance()
            
            self.status = BrokerStatus.CONNECTED
            self.connected_at = datetime.now(timezone.utc)
            return True
            
        except Exception as e:
            self.status = BrokerStatus.ERROR
            self.last_error = str(e)
            raise
    
    async def disconnect(self) -> bool:
        """Disconnect from Bybit"""
        if self._client:
            await self._client.aclose()
            self._client = None
        
        self.status = BrokerStatus.DISCONNECTED
        self.connected_at = None
        return True
    
    async def is_connected(self) -> bool:
        """Check connection status"""
        return self.status == BrokerStatus.CONNECTED and self._client is not None
    
    # ===========================================
    # Account
    # ===========================================
    
    async def get_balance(self, asset: Optional[str] = None) -> List[Balance]:
        """Get account balances"""
        account_type = "UNIFIED" if self.category != "spot" else "SPOT"
        
        params = {"accountType": account_type}
        if asset:
            params["coin"] = asset
        
        data = await self._request("GET", "/v5/account/wallet-balance", params=params, signed=True)
        
        balances = []
        
        for account in data.get("list", []):
            for coin in account.get("coin", []):
                if asset and coin["coin"] != asset:
                    continue
                
                free = float(coin.get("availableToWithdraw", 0))
                total = float(coin.get("walletBalance", 0))
                locked = total - free
                
                if total > 0 or asset:
                    balances.append(Balance(
                        asset=coin["coin"],
                        free=free,
                        locked=max(0, locked),
                        total=total,
                        usd_value=float(coin.get("usdValue", 0))
                    ))
        
        return balances
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get open positions"""
        params = {"category": self.category}
        if symbol:
            params["symbol"] = symbol
        
        data = await self._request("GET", "/v5/position/list", params=params, signed=True)
        
        positions = []
        
        for item in data.get("list", []):
            size = float(item.get("size", 0))
            if size == 0:
                continue
            
            positions.append(Position(
                symbol=item["symbol"],
                side=item.get("side", "Buy").upper(),
                size=size,
                entry_price=float(item.get("avgPrice", 0)),
                current_price=float(item.get("markPrice", 0)),
                unrealized_pnl=float(item.get("unrealisedPnl", 0)),
                realized_pnl=float(item.get("cumRealisedPnl", 0)),
                leverage=float(item.get("leverage", 1)),
                liquidation_price=float(item.get("liqPrice", 0)) or None
            ))
        
        return positions
    
    # ===========================================
    # Market Data
    # ===========================================
    
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker for symbol"""
        params = {"category": self.category, "symbol": symbol}
        
        data = await self._request("GET", "/v5/market/tickers", params=params)
        
        if not data.get("list"):
            raise OrderError(f"Symbol not found: {symbol}")
        
        item = data["list"][0]
        
        return Ticker(
            symbol=symbol,
            bid=float(item.get("bid1Price", 0)),
            ask=float(item.get("ask1Price", 0)),
            last=float(item.get("lastPrice", 0)),
            volume_24h=float(item.get("turnover24h", 0)),
            change_24h=float(item.get("price24hPcnt", 0)),
            high_24h=float(item.get("highPrice24h", 0)),
            low_24h=float(item.get("lowPrice24h", 0))
        )
    
    async def get_tickers(self, symbols: Optional[List[str]] = None) -> List[Ticker]:
        """Get multiple tickers"""
        params = {"category": self.category}
        
        data = await self._request("GET", "/v5/market/tickers", params=params)
        
        tickers = []
        
        for item in data.get("list", []):
            if symbols and item["symbol"] not in symbols:
                continue
            
            tickers.append(Ticker(
                symbol=item["symbol"],
                bid=float(item.get("bid1Price", 0)),
                ask=float(item.get("ask1Price", 0)),
                last=float(item.get("lastPrice", 0)),
                volume_24h=float(item.get("turnover24h", 0)),
                change_24h=float(item.get("price24hPcnt", 0)),
                high_24h=float(item.get("highPrice24h", 0)),
                low_24h=float(item.get("lowPrice24h", 0))
            ))
        
        return tickers
    
    # ===========================================
    # Orders
    # ===========================================
    
    def _map_order_type(self, order_type: OrderType) -> str:
        """Map internal order type to Bybit format"""
        mapping = {
            OrderType.MARKET: "Market",
            OrderType.LIMIT: "Limit"
        }
        return mapping.get(order_type, "Market")
    
    def _map_order_status(self, status: str) -> OrderStatus:
        """Map Bybit order status to internal format"""
        mapping = {
            "Created": OrderStatus.NEW,
            "New": OrderStatus.NEW,
            "PartiallyFilled": OrderStatus.PARTIALLY_FILLED,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELED,
            "Rejected": OrderStatus.REJECTED,
            "Deactivated": OrderStatus.EXPIRED
        }
        return mapping.get(status, OrderStatus.NEW)
    
    def _parse_order(self, data: Dict[str, Any]) -> Order:
        """Parse Bybit order response"""
        return Order(
            id=data.get("orderLinkId") or data.get("orderId", ""),
            broker_order_id=data.get("orderId", ""),
            symbol=data.get("symbol", ""),
            side=OrderSide.BUY if data.get("side", "").lower() == "buy" else OrderSide.SELL,
            order_type=OrderType.LIMIT if data.get("orderType", "").lower() == "limit" else OrderType.MARKET,
            quantity=float(data.get("qty", 0)),
            price=float(data.get("price", 0)) or None,
            stop_price=float(data.get("triggerPrice", 0)) or None,
            status=self._map_order_status(data.get("orderStatus", "New")),
            filled_quantity=float(data.get("cumExecQty", 0)),
            avg_fill_price=float(data.get("avgPrice", 0)),
            created_at=datetime.fromtimestamp(int(data.get("createdTime", 0)) / 1000, tz=timezone.utc) if data.get("createdTime") else datetime.now(timezone.utc),
            updated_at=datetime.fromtimestamp(int(data.get("updatedTime", 0)) / 1000, tz=timezone.utc) if data.get("updatedTime") else datetime.now(timezone.utc)
        )
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_order_id: Optional[str] = None
    ) -> Order:
        """Place order on Bybit"""
        params = {
            "category": self.category,
            "symbol": symbol,
            "side": "Buy" if side == OrderSide.BUY else "Sell",
            "orderType": self._map_order_type(order_type),
            "qty": str(quantity)
        }
        
        if client_order_id:
            params["orderLinkId"] = client_order_id
        
        if order_type == OrderType.LIMIT and price:
            params["price"] = str(price)
            params["timeInForce"] = time_in_force.value
        
        if stop_price:
            params["triggerPrice"] = str(stop_price)
        
        data = await self._request("POST", "/v5/order/create", params=params, signed=True)
        
        return self._parse_order(data)
    
    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """Cancel order on Bybit"""
        params = {
            "category": self.category,
            "symbol": symbol
        }
        
        if order_id:
            params["orderId"] = order_id
        elif client_order_id:
            params["orderLinkId"] = client_order_id
        else:
            raise OrderError("Either order_id or client_order_id required")
        
        data = await self._request("POST", "/v5/order/cancel", params=params, signed=True)
        
        return self._parse_order(data)
    
    async def get_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """Get order from Bybit"""
        params = {
            "category": self.category,
            "symbol": symbol
        }
        
        if order_id:
            params["orderId"] = order_id
        elif client_order_id:
            params["orderLinkId"] = client_order_id
        
        data = await self._request("GET", "/v5/order/realtime", params=params, signed=True)
        
        if not data.get("list"):
            raise OrderError(f"Order not found")
        
        return self._parse_order(data["list"][0])
    
    async def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[Order]:
        """Get orders from Bybit"""
        params = {
            "category": self.category,
            "limit": limit
        }
        
        if symbol:
            params["symbol"] = symbol
        
        data = await self._request("GET", "/v5/order/realtime", params=params, signed=True)
        
        orders = [self._parse_order(item) for item in data.get("list", [])]
        
        if status:
            orders = [o for o in orders if o.status == status]
        
        return orders
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Cancel all open orders"""
        params = {"category": self.category}
        
        if symbol:
            params["symbol"] = symbol
        
        data = await self._request("POST", "/v5/order/cancel-all", params=params, signed=True)
        
        cancelled = []
        for item in data.get("list", []):
            cancelled.append(self._parse_order(item))
        
        return cancelled
